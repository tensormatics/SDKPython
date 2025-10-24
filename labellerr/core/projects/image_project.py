from typing import TYPE_CHECKING

from .base import LabellerrProject, LabellerrProjectMeta

if TYPE_CHECKING:
    from ..client import LabellerrClient


class ImageProject(LabellerrProject):

    @staticmethod
    def create_project(client: "LabellerrClient", payload: dict) -> "ImageProject":
        pass

    def fetch_datasets(self):
        print("Yo I am gonna fetch some datasets!")


LabellerrProjectMeta._register("image", ImageProject)
