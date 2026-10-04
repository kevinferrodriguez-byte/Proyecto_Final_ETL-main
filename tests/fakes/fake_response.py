from requests.structures import CaseInsensitiveDict


class FakeResponse:
    def __init__(self, status_code, content, url, headers=None):
        self.status_code = status_code
        self.content = content
        self.url = url
        self.headers = CaseInsensitiveDict(headers or {})
