from abc import ABC, abstractmethod
class BaseConnector(ABC):
    @abstractmethod
    def connect(self):
        raise NotImplementedError