"""Automatización del pipeline ETL con la librería `schedule`.

`schedule` ejecuta trabajos periódicos dentro de un proceso de Python: se declara la frecuencia
(`schedule.every().monday.at("06:00").do(trabajo)`) y un bucle llama a `run_pending()`, que lanza los trabajos
cuya hora ha llegado. No es un servicio del sistema operativo: el proceso debe seguir abierto (ver programar.py).

La frecuencia, la hora y el tramo de etapas se leen de `config/config.yaml › programacion`. Cada ejecución queda
registrada en una línea JSON de `logs/programacion.jsonl` (inicio, fin, estado, run_id del pipeline y error), y un
fallo no detiene el programador: se registra y se reintenta en la siguiente ejecución programada.
"""

from datetime import datetime, timezone
from pathlib import Path
import json
import time

import schedule

FREQUENCIES = ("diaria", "semanal", "cada_minutos", "cada_segundos")
WEEKDAYS = {"lunes": "monday", "martes": "tuesday", "miercoles": "wednesday", "miércoles": "wednesday", "jueves": "thursday",
            "viernes": "friday", "sabado": "saturday", "sábado": "saturday", "domingo": "sunday"}


class ProgramadorETL:
    def __init__(self, config, ejecutar=None, scheduler=None):
        self.config = config
        self.ajustes = config["programacion"]
        self.scheduler = scheduler or schedule.Scheduler()
        self.ejecutar = ejecutar or self._ejecutar_pipeline
        self.registro = Path(self.ajustes["registro"])
        self.ejecuciones = []

    def programar(self):
        """Declara el trabajo según la configuración y lo devuelve (útil para mostrar `next_run`)."""
        frecuencia = self.ajustes["frecuencia"]
        if frecuencia not in FREQUENCIES:
            raise ValueError(f"programacion.frecuencia '{frecuencia}' no válida; use una de: {', '.join(FREQUENCIES)}.")
        if frecuencia == "diaria":
            trabajo = self.scheduler.every().day.at(self.ajustes["hora"])
        elif frecuencia == "semanal":
            dia = WEEKDAYS.get(str(self.ajustes["dia"]).lower())
            if dia is None:
                raise ValueError(f"programacion.dia '{self.ajustes['dia']}' no válido; use un día de la semana en español.")
            trabajo = getattr(self.scheduler.every(), dia).at(self.ajustes["hora"])
        elif frecuencia == "cada_minutos":
            trabajo = self.scheduler.every(int(self.ajustes["intervalo"])).minutes
        else:
            trabajo = self.scheduler.every(int(self.ajustes["intervalo"])).seconds
        return trabajo.do(self.ejecutar_trabajo).tag("pipeline_etl")

    def ejecutar_trabajo(self):
        """Ejecuta el pipeline una vez y registra el resultado; nunca propaga el error al bucle de `schedule`."""
        inicio = datetime.now(timezone.utc)
        entrada = {"inicio_utc": self._iso(inicio), "desde": self.ajustes["desde"], "hasta": self.ajustes["hasta"]}
        try:
            resultado = self.ejecutar(self.ajustes["desde"], self.ajustes["hasta"])
            entrada.update({"estado": "completada", "run_id": (resultado or {}).get("run_id"), "error": None})
        except Exception as error:  # el programador debe seguir vivo ante cualquier fallo del trabajo
            entrada.update({"estado": "fallida", "run_id": None, "error": f"{type(error).__name__}: {error}"})
        entrada["fin_utc"] = self._iso(datetime.now(timezone.utc))
        entrada["duracion_s"] = round((datetime.now(timezone.utc) - inicio).total_seconds(), 3)
        self.ejecuciones.append(entrada)
        self.registro.parent.mkdir(parents=True, exist_ok=True)
        with self.registro.open("a", encoding="utf-8") as file:
            file.write(json.dumps(entrada, ensure_ascii=False) + "\n")
        return entrada

    def iniciar(self, max_ejecuciones=None, espera_s=1, limite_s=None, reloj=time.monotonic, dormir=time.sleep):
        """Bucle de `schedule`: comprueba cada `espera_s` segundos si toca ejecutar.

        `max_ejecuciones` y `limite_s` permiten acotar el bucle (demostraciones y pruebas); en producción se omiten.
        """
        comienzo = reloj()
        objetivo = len(self.ejecuciones) + max_ejecuciones if max_ejecuciones else None
        while True:
            self.scheduler.run_pending()
            if objetivo is not None and len(self.ejecuciones) >= objetivo:
                return self.ejecuciones
            if limite_s is not None and reloj() - comienzo >= limite_s:
                return self.ejecuciones
            dormir(espera_s)

    def detener(self):
        self.scheduler.clear("pipeline_etl")

    def _ejecutar_pipeline(self, desde, hasta):
        from src.pipeline import Pipeline

        return Pipeline(self.config).run(desde, hasta)

    def _iso(self, momento):
        return momento.isoformat(timespec="seconds").replace("+00:00", "Z")
