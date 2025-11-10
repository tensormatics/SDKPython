# from labellerr.core.datasets import (
#     create_dataset_from_local,
#     create_dataset_from_connection,
# )
import logging
import os
from dotenv import load_dotenv
from labellerr.client import LabellerrClient
from labellerr.core.schemas import DatasetConfig
from labellerr.core.datasets import LabellerrDataset

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
dataset_config = DatasetConfig(
    dataset_name="test_dataset_from_local SDK",
    dataset_description="test dataset description",
    data_type="image",
)
# dataset = create_dataset_from_local(
#     client=client,
#     dataset_config=dataset_config,
#     folder_to_upload='images_single',
# )
dataset = LabellerrDataset(
    client=client, dataset_id="455e3d45-55f9-436d-98c2-07a514b7894e"
)
print(dataset.files_count)
