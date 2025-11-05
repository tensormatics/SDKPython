import logging
import os
from dotenv import load_dotenv
from labellerr.client import LabellerrClient

# from labellerr.core.connectors import (
#     LabellerrConnection,
#     list_connections,
#     delete_connection,
#     create_connection,
#     AWSConnectionParams,
#     LabellerrGCSConnection,
# )
# from labellerr.core.schemas import (
#     ConnectionType,
#     ConnectorType,
#     DatasetDataType,
#     GCSConnectionTestParams,
#     GCSConnectionParams,
# )

# Set logging level to DEBUG
logging.basicConfig(level=logging.DEBUG)

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
CLIENT_ID = os.getenv("CLIENT_ID")

if not all([API_KEY, API_SECRET, CLIENT_ID]):
    raise ValueError(
        "API_KEY, API_SECRET, and CLIENT_ID must be set in environment variables"
    )

# Initialize client
client = LabellerrClient(
    api_key=API_KEY,
    api_secret=API_SECRET,
    client_id=CLIENT_ID,
)

# response = LabellerrGCSConnection.test_connection(client=client, params=GCSConnectionTestParams(
#     svc_account_json='labellerr-dev.json',
#     path="gs://aws-labellerr-public-datasets/coco2017",
#     connection_type=ConnectionType._IMPORT,
#     data_type=DatasetDataType.video,
# ))
# print(response)

# response = create_connection(client=client, connector_type=ConnectorType._GCS, params=GCSConnectionParams(
#     svc_account_json='labellerr-dev.json',
#     path="gs://aws-labellerr-public-datasets/coco2017",
#     connection_type=ConnectionType._IMPORT,
#     data_type=DatasetDataType.image, name="GCS Import Test", description="GCS Import Test"))
# print(response)
# connection = LabellerrConnection(client=client, connection_id='8c3dc4b4-e701-4d22-add3-28abc33e13ef')
# response = connection.test(path="gs://aws-labellerr-public-datasets/coco2017", connection_type=ConnectionType._IMPORT, data_type=DatasetDataType.image)
# print(response)
# connection = create_connection(client=client, connector_type=ConnectorType._S3, params=AWSConnectionParams(
#     aws_access_key=os.getenv("AWS_KEY"),
#     aws_secrets_key=os.getenv("AWS_SECRET"),
#     s3_path="s3://amazon-s3-sync-test/labellerr-processed/videos/", # this path is not part of the connection but needed to test the connection on the desired path.
#     # This can be dynamically changed while using the connection for creating datasets.
#     connection_type=ConnectionType._IMPORT,
#     name="Amazon S3 Import Test",
#     description="Amazon S3 Import Test",
# ))
# print(f"Connection created: {connection.connection_id}")
# connection = LabellerrConnection(client=client, connection_id='2a30c044-57f7-42c7-8290-bab3bbac0ebc')
# print('connection type', connection.connection_type)

# print (connection.test(s3_path="s3://amazon-s3-sync-test/labellerr-processed/videos/datasets/", connection_type=ConnectionType._IMPORT))
