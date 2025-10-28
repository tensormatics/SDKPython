import logging
import os

from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core.schemas import DatasetConfig
from labellerr.core.datasets import create_dataset, LabellerrDataset
from labellerr.core.projects import (
    create_project,
    create_annotation_guideline,
    LabellerrProject,
)
from labellerr.core.files import LabellerrFile

# Set logging level to DEBUG
logging.basicConfig(level=logging.DEBUG)

load_dotenv()

client = LabellerrClient(
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET"),
    client_id=os.getenv("CLIENT_ID"),
)
# response = create_annotation_guideline(client=client, questions=[], template_name="Test Template", data_type="image")
# print(response)
# file = LabellerrFile(
#     client=client,
#     file_id="6a17c668-1dd8-4d4f-b935-a629091859f7",
#     dataset_id="ec541bdc-d190-4618-aedf-bb0cf45c1787",
# )
# print(file.metadata)
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
# print(project.attached_datasets)

# print (autolabel.train(training_request=TrainingRequest(model_id="yolov11", job_name="Ximi SDK Test", slice_id='34m28HW1i6c4wwxLDfQh')))
# print(autolabel.list_training_jobs())

# dataset = create_dataset(client=client, dataset_config=DatasetConfig(dataset_name="Dataset new Ximi", data_type="image"), folder_to_upload="images")
# print(dataset.dataset_data)

# dataset = LabellerrDataset(client=client, dataset_id="137a7b2f-942f-478d-a135-94ad2e11fcca")
# print (dataset.fetch_files())

# Create dataset using aws and gcs

# Bulk assign files to a new status
# project = LabellerrProject()
# project.bulk_assign_files(client_id=client.client_id, project_id=project.project_id, file_ids=file_ids, new_status="completed")

# project = LabellerrProject(client=client, project_id="aimil_reasonable_locust_75218")
# print(project.attached_datasets)
# print(project.attach_dataset_to_project(dataset_id="137a7b2f-942f-478d"))

# dataset = LabellerrDataset(client=client, dataset_id="1db5342a-8d43-4f16-9765-3f09dd3f245c")
# print(dataset.enable_multimodal_indexing(is_multimodal=False))

# file = LabellerrFile(client=client, dataset_id='137a7b2f-942f-478d-a135-94ad2e11fcca', file_id="8fb00e0d-456c-49c7-94e2-cca50b4acee7")
# print(file.file_data)

# project = LabellerrProject(client=client, project_id="aimil_reasonable_locust_75218")
# res = project.upload_preannotations(
#     annotation_format="coco_json", annotation_file="horses_coco.json"
# )
# print(res)

print(LabellerrProject.list_all_projects(client=client))
