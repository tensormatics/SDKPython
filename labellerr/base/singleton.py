import threading


class Singleton:
    __instance = None
    __lock = None

    def __new__(cls, *args, **kwargs):
        if cls.__lock is None:
            cls.__lock = threading.Lock()
        if cls.__instance is None:
            with cls.__lock:
                if cls.__instance is None:
                    cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, *args):
        if type(self) is Singleton:
            raise TypeError("Can't instantiate Singleton class")
