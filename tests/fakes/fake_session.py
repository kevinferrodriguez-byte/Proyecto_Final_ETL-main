import requests


class FakeSession:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []
        self.opened = 0
        self.closed = False

    def install(self, monkeypatch):
        monkeypatch.setattr(requests, "Session", self.open)

    def open(self):
        self.opened += 1
        return self

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        pending = self.routes.get(url)
        if not pending:
            raise AssertionError(f"Solicitud no prevista o repetida: {url}")
        event = pending.pop(0)
        if isinstance(event, BaseException):
            raise event
        return event

    def close(self):
        self.closed = True

    def calls_to(self, url):
        return [call for call in self.calls if call["url"] == url]
