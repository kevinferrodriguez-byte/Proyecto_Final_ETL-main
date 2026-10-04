from email.utils import parsedate_to_datetime
from datetime import timezone, datetime
from src.logger import get_logger
import requests
import time


class HttpClient:
    def __init__(self, config):
        self.timeout_seconds = config["timeout_seconds"]
        self.max_attempts = config["max_retries"] + 1
        self.retry_backoff_seconds = config["retry_backoff_seconds"]
        self.retry_statuses = frozenset(config["retry_on_status"])
        self.session = requests.Session()
        self.closed = False
        self.logger = get_logger(__name__)

    def get(self, url, params=None):
        if self.closed:
            raise RuntimeError(f"La conexión HTTP ya está cerrada; no se puede solicitar {url}. Cree un extractor nuevo.")
        for attempt in range(1, self.max_attempts + 1):
            is_last_attempt = attempt == self.max_attempts
            try:
                response = self.session.get(url, params=params, timeout=self.timeout_seconds)
            except requests.Timeout as error:
                if is_last_attempt:
                    raise self._fail(TimeoutError(f"La solicitud a {url} agotó {self.max_attempts} intentos por tiempo de espera de {self.timeout_seconds} s. Revise la conectividad o aumente request.timeout_seconds.")) from error
                self._wait(f"Tiempo de espera agotado en {url}", attempt, self.retry_backoff_seconds)
                continue
            except requests.RequestException as error:
                raise self._fail(ConnectionError(f"No fue posible conectar con {url}: {error}. Revise la conectividad o la URL base configurada.")) from error

            status_code = response.status_code
            if status_code in self.retry_statuses:
                if is_last_attempt:
                    raise self._fail(RuntimeError(f"HTTP {status_code} persistente en {url} tras {self.max_attempts} intentos. El servicio no está disponible; reintente más tarde."))
                self._wait(f"HTTP {status_code} en {url}", attempt, self._wait_seconds(response))
                continue
            if 400 <= status_code < 500:
                raise self._fail(ValueError(f"HTTP {status_code} en {response.url or url}. La solicitud no es válida: revise el identificador de tabla y los filtros en config/config.yaml."))
            if not 200 <= status_code < 300:
                raise self._fail(RuntimeError(f"HTTP {status_code} inesperado en {url}."))
            return response

    def close(self):
        """Cierra la sesión HTTP (libera las conexiones abiertas del pool). Es idempotente."""
        if not self.closed:
            self.session.close()
            self.closed = True

    def _wait(self, reason, attempt, seconds):
        self.logger.warn(f"{reason} (intento {attempt}/{self.max_attempts}); nuevo intento en {seconds:.1f} s.")
        time.sleep(seconds)

    def _fail(self, error):
        self.logger.error(str(error))
        return error

    def _wait_seconds(self, response):
        retry_after = response.headers.get("Retry-After")
        if response.status_code != 429 or not retry_after:
            return self.retry_backoff_seconds
        try:
            return max(float(retry_after), 0.0)
        except ValueError:
            pass
        try:
            retry_at = parsedate_to_datetime(retry_after)
        except (TypeError, ValueError, IndexError):
            return self.retry_backoff_seconds
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max((retry_at - datetime.now(timezone.utc)).total_seconds(), 0.0)
