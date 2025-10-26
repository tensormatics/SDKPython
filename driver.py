import logging
import os

from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core.datasets import LabellerrDataset
from labellerr.core.projects import create_project, LabellerrProject
from labellerr.core.files import LabellerrFile

# Set logging level to DEBUG
logging.basicConfig(level=logging.DEBUG)

load_dotenv()

client = LabellerrClient(
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET"),
    client_id=os.getenv("CLIENT_ID"),
)
file = LabellerrFile(
    client=client,
    file_id="6a17c668-1dd8-4d4f-b935-a629091859f7",
    dataset_id="ec541bdc-d190-4618-aedf-bb0cf45c1787",
)
print(file.metadata)
# dataset = LabellerrDataset(
#     client=client, dataset_id="e6280472-e7f9-4f5f-a4e1-b546b41bd616"
# )

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
# project = create_project(
#     client=client,
#     payload={
#         "project_name": "Project new Ximi 3",
#         "data_type": "image",
#         "folder_to_upload": "images_single",
#         "annotation_template_id": "c87ef749-cab7-457a-94d7-e733d6107c6f",
#         "rotations": {
#             "annotation_rotation_count": 1,
#             "review_rotation_count": 1,
#             "client_review_rotation_count": 1,
#         },
#         "use_ai": False,
#         "created_by": "ximi.hoque@labellerr.com",
#         "autolabel": False,
#         # "datasets": [dataset.dataset_id],
#     },
# )
# project = LabellerrProject(client=client, project_id="gina_inland_clam_15425")
# print(project.project_data)

# print (autolabel.train(training_request=TrainingRequest(model_id="yolov11", job_name="Ximi SDK Test", slice_id='34m28HW1i6c4wwxLDfQh')))
# print(autolabel.list_training_jobs())
