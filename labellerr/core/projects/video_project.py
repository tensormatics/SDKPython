from .base import LabellerrProject
from ..client import LabellerrClient


class VideoProject(LabellerrProject):
    """
    Class for handling video project operations and fetching multiple datasets.
    """
    @staticmethod
    def create_project(client: "LabellerrClient", payload: dict) -> "VideoProject":
        pass
