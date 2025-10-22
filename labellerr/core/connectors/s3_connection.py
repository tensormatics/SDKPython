from .connections import LabellerrConnection, LabellerrConnectionMeta


class S3Connection(LabellerrConnection):
    def test_connection(self):
        print("Testing S3 connection!")
        return True


LabellerrConnectionMeta.register("s3", S3Connection)
