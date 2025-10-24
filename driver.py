import os

from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core import schemas
from labellerr.core.datasets import LabellerrDataset, create_dataset

load_dotenv()

client = LabellerrClient(
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET"),
    client_id=os.getenv("CLIENT_ID"),
)

dataset = LabellerrDataset(
    client=client, dataset_id="6d04253c-0895-4c5c-aa91-825df42ce986"
)

response = create_dataset(
    client=client,
    dataset_config=schemas.DatasetConfig(
        client_id=os.getenv("CLIENT_ID"),
        dataset_name="Dataset new Ximi",
        data_type="image",
    ),
    folder_to_upload="images",
)
print(response.dataset_data)
# autolabel = LabellerrAutoLabel(client=client)


# print (autolabel.train(training_request=TrainingRequest(model_id="yolov11", job_name="Ximi SDK Test", slice_id='34m28HW1i6c4wwxLDfQh')))
# print(autolabel.list_training_jobs())
