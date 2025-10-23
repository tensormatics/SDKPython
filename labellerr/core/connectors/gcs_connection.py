from .connections import LabellerrConnection, LabellerrConnectionMeta
from ..client import LabellerrClient

class GCSConnection(LabellerrConnection):
    @staticmethod
    def create_connection(client: "LabellerrClient", connection_config: dict) -> "GCSConnection":
        pass
    def test_connection(self):
        print("Testing GCS connection!")
        return True


LabellerrConnectionMeta.register("gcs", GCSConnection)
