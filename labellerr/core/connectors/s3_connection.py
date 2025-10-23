from .connections import LabellerrConnection, LabellerrConnectionMeta
from ..client import LabellerrClient

class S3Connection(LabellerrConnection):
    @staticmethod
    def create_connection(client: "LabellerrClient", connection_config: dict) -> "S3Connection":
        pass
    def test_connection(self):
        print("Testing S3 connection!")
        return True


LabellerrConnectionMeta.register("s3", S3Connection)
