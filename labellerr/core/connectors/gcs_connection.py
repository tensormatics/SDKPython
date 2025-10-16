from .connections import LabellerrConnection, LabellerrConnectionMeta

class GCSConnection(LabellerrConnection):
    def test_connection(self):
        print("Testing GCS connection!")
        return True


LabellerrConnectionMeta.register('gcs', GCSConnection)
