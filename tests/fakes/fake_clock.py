class FakeClock:
    def __init__(self, moment):
        self.moment = moment

    def now(self, tz=None):
        return self.moment
