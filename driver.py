from labellerr.client import LabellerrClient
from labellerr.core.datasets import LabellerrDataset
from labellerr.core.autolabel import LabellerrAutoLabel
from labellerr.core.autolabel.typings import TrainingRequest
from dotenv import load_dotenv
import os

load_dotenv()

client = LabellerrClient(api_key=os.getenv("API_KEY"), api_secret=os.getenv("API_SECRET"), client_id=os.getenv("CLIENT_ID"))

dataset = LabellerrDataset(client=client, dataset_id="6d04253c-0895-4c5c-aa91-825df42ce986")

# autolabel = LabellerrAutoLabel(client=client)


# print (autolabel.train(training_request=TrainingRequest(model_id="yolov11", job_name="Ximi SDK Test", slice_id='34m28HW1i6c4wwxLDfQh')))
# print(autolabel.list_training_jobs())