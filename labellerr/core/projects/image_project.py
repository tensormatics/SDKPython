from .base import LabellerrProject, LabellerrProjectMeta
from ..client import LabellerrClient

class ImageProject(LabellerrProject):
    @staticmethod
    def create_project(client: "LabellerrClient", payload: dict) -> "ImageProject":
        pass
    def fetch_datasets(self):
        print("Yo I am gonna fetch some datasets!")


LabellerrProjectMeta.register("image", ImageProject)
