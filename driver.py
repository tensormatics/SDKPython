import os

from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core import schemas
from labellerr.core.datasets import LabellerrDataset, create_dataset
from labellerr.core.projects import LabellerrProject, create_project
import logging

# Set logging level to DEBUG
logging.basicConfig(level=logging.DEBUG)

load_dotenv()

client = LabellerrClient(
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET"),
    client_id=os.getenv("CLIENT_ID"),
)

dataset = LabellerrDataset(
    client=client, dataset_id="b51cf22c-cc57-45dd-a6d5-f2d18ab679a1"
)

# response = create_dataset(
#     client=client,
#     dataset_config=schemas.DatasetConfig(
#         client_id=os.getenv("CLIENT_ID"),
#         dataset_name="Dataset new Ximi",
#         data_type="image",
#     ),
#     folder_to_upload="images",
# )
# print(response.dataset_data)
# autolabel = LabellerrAutoLabel(client=client)
project = create_project(
    client=client,
    payload={
        "project_name": "Project new Ximi",
        "data_type": "image",
        "folder_to_upload": "images_single",
        "annotation_template_id": "c87ef749-cab7-457a-94d7-e733d6107c6f",
        "rotations": {
            "annotation_rotation_count": 1,
            "review_rotation_count": 1,
            "client_review_rotation_count": 1,
        },
        "use_ai": False,
        "created_by": "dev@labellerr.com",
        "autolabel": False,
    },
)
print(project.project_data)

# print (autolabel.train(training_request=TrainingRequest(model_id="yolov11", job_name="Ximi SDK Test", slice_id='34m28HW1i6c4wwxLDfQh')))
# print(autolabel.list_training_jobs())
