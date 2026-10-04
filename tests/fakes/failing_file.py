class FailingFile:
    def __init__(self, file):
        self.file = file

    def __enter__(self):
        return self

    def __exit__(self, error_type, error, traceback):
        self.file.close()
        return False

    def write(self, content):
        raise OSError("No queda espacio en el dispositivo")
