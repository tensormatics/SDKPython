from ..schemas import DataSetDataType
from .base import LabellerrDataset, LabellerrDatasetMeta


class AudioDataSet(LabellerrDataset):
    def fetch_files(self):
        print("Yo I am gonna fetch some files!")


LabellerrDatasetMeta._register(DataSetDataType.audio, AudioDataSet)
