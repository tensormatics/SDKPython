import logging
import os

from dotenv import load_dotenv

from labellerr.client import LabellerrClient
from labellerr.core.datasets import LabellerrDataset, create_dataset
from labellerr.core.files import LabellerrFile
from labellerr.core.projects import (
    LabellerrProject,
    LabellerrVideoProject,
    create_annotation_guideline,
    create_project,
)
from labellerr.core.schemas import DatasetConfig, KeyFrame

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

# if os.getenv("CREATE_DATASET", "").lower() == "true":
#     from labellerr import schemas
#     from labellerr.core.datasets import create_dataset

#     folder_to_upload = os.getenv("FOLDER_TO_UPLOAD", "images")
#     dataset_name = os.getenv("DATASET_NAME", "Dataset new Ximi")

#     print(f"\n=== Creating Dataset: {dataset_name} ===")
#     response = create_dataset(
#         client=client,
#         dataset_config=schemas.DatasetConfig(
#             client_id=CLIENT_ID,
#             dataset_name=dataset_name,
#             data_type="image",
#         ),
#         folder_to_upload=folder_to_upload,
#     )
#     print(f"Dataset created: {response.dataset_data}")

DATASET_ID = os.getenv("DATASET_ID")
if DATASET_ID:
    print(f"\n=== Working with Dataset: {DATASET_ID} ===")
    dataset = LabellerrDataset(client=client, dataset_id=DATASET_ID)
    print(f"Dataset loaded: {dataset.data_type}")

# if os.getenv("CREATE_PROJECT", "").lower() == "true":
#     project = create_project(
#         client=client,
#         payload={
#             "project_name": project_name,
#             "data_type": "image",
#             "folder_to_upload": folder_to_upload,
#             "annotation_template_id": annotation_template_id,
#             "rotations": {
#                 "annotation_rotation_count": 1,
#                 "review_rotation_count": 1,
#                 "client_review_rotation_count": 1,
#             },
#             "use_ai": False,
#             "created_by": os.getenv("CREATED_BY", "dev@labellerr.com"),
#             "autolabel": False,
#         },
#     )
#     print(f"Project created: {project.project_data}")

if os.getenv("SYNC_AWS", "").lower() == "true":
    aws_connection_id = os.getenv("AWS_CONNECTION_ID")
    aws_project_id = os.getenv("AWS_PROJECT_ID")
    aws_dataset_id = os.getenv("AWS_DATASET_ID", DATASET_ID)
    aws_s3_path = os.getenv("AWS_S3_PATH")
    aws_data_type = os.getenv("AWS_DATA_TYPE", "image")
    aws_email = os.getenv("AWS_EMAIL", "dev@labellerr.com")

    if not all([aws_connection_id, aws_project_id, aws_dataset_id, aws_s3_path]):
        raise ValueError(
            "AWS_CONNECTION_ID, AWS_PROJECT_ID, AWS_DATASET_ID, and AWS_S3_PATH "
            "must be set when SYNC_AWS=true"
        )

    if not aws_dataset_id:
        raise ValueError("DATASET_ID or AWS_DATASET_ID must be set when SYNC_AWS=true")

    print(f"\n=== Syncing Dataset from AWS S3: {aws_s3_path} ===")
    dataset = LabellerrDataset(client=client, dataset_id=aws_dataset_id)
    response = dataset.sync_datasets(
        project_id=aws_project_id,
        path=aws_s3_path,
        data_type=aws_data_type,
        email_id=aws_email,
        connection_id=aws_connection_id,
    )
    print(f"AWS S3 Sync Response: {response}")

if os.getenv("SYNC_GCS", "").lower() == "true":
    gcs_connection_id = os.getenv("GCS_CONNECTION_ID")
    gcs_project_id = os.getenv("GCS_PROJECT_ID")
    gcs_dataset_id = os.getenv("GCS_DATASET_ID", DATASET_ID)
    gcs_path = os.getenv("GCS_PATH")
    gcs_data_type = os.getenv("GCS_DATA_TYPE", "image")
    gcs_email = os.getenv("GCS_EMAIL", "dev@labellerr.com")

    if not all([gcs_connection_id, gcs_project_id, gcs_dataset_id, gcs_path]):
        raise ValueError(
            "GCS_CONNECTION_ID, GCS_PROJECT_ID, GCS_DATASET_ID, and GCS_PATH "
            "must be set when SYNC_GCS=true"
        )

    if not gcs_dataset_id:
        raise ValueError("DATASET_ID or GCS_DATASET_ID must be set when SYNC_GCS=true")

    print(f"\n=== Syncing Dataset from GCS: {gcs_path} ===")
    dataset = LabellerrDataset(client=client, dataset_id=gcs_dataset_id)
    response = dataset.sync_datasets(
        project_id=gcs_project_id,
        path=gcs_path,
        data_type=gcs_data_type,
        email_id=gcs_email,
        connection_id=gcs_connection_id,
    )
    print(f"GCS Sync Response: {response}")

print("\n=== Driver execution completed ===")

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

# print(LabellerrProject.list_all_projects(client=client))

# project: LabellerrVideoProject = LabellerrProject(client=client, project_id="pam_rear_worm_89383")
# print(project.add_keyframes(file_id="fd42f5da-7a0c-4d5d-be16-3a9c4fa078bf", keyframes=[KeyFrame(frame_number=1, is_manual=True, method="manual", source="manual")]))

# datasets = LabellerrDataset.get_all_datasets(
#     client=client, datatype="image", scope="project", page_size=-1
# )
# for dataset in datasets:
#     print('name', dataset.get("name"), 'id', dataset.get("dataset_id"))
