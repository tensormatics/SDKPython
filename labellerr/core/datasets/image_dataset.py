from .base import LabellerrDataset, LabellerrDatasetMeta


class ImageDataset(LabellerrDataset):
    def fetch_files(self):
        print("Yo I am gonna fetch some files!")


LabellerrDatasetMeta._register("image", ImageDataset)
