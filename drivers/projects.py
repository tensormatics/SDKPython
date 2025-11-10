# from labellerr.core.projects import LabellerrProject
# from labellerr.core.annotation_templates import LabellerrAnnotationTemplate
import logging
import os
from dotenv import load_dotenv
from labellerr.client import LabellerrClient

# from labellerr.core.schemas.annotation_templates import CreateTemplateParams, AnnotationQuestion, QuestionType
# from labellerr.core.annotation_templates import create_template
# from labellerr.core.schemas.projects import CreateProjectParams, RotationConfig
# from labellerr.core.projects import create_project
# from labellerr.core.datasets import LabellerrDataset


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

# project = LabellerrProject(client=client, project_id="rafaela_youngest_pike_23125")
# res = project.upload_preannotation(annotation_format="coco_json", annotation_file="/Users/Ximi-Hoque/Downloads/export_to_annotate_05_15.json").result()
# print(res)

# annotation_template = LabellerrAnnotationTemplate(client=client, annotation_template_id="00016829-9051-46b1-96c6-3ec6763c342a")
# print(annotation_template.annotation_template_data)

# res = create_template(client, CreateTemplateParams(template_name="test_template_1", data_type="image",
# questions=[
#     AnnotationQuestion(question_number=1,
#     question="test_question",
#     question_id="test_question_id",
#     question_type=QuestionType.bounding_box,
#     required=True,
#     color="#FF4500",
#     )]))
# print(res)

# project = create_project(client,
# CreateProjectParams(
#     project_name="test_project_via_sdk",
#     data_type="image",
#     rotations=RotationConfig(annotation_rotation_count=1, review_rotation_count=1, client_review_rotation_count=1),
#     use_ai=False),
#     datasets=[LabellerrDataset(client=client, dataset_id="ca298293-7f5e-4bdd-801f-8863a5ba458b")],
#     annotation_template=res
# )
# print (project.project_data)
# project = LabellerrProject(client=client, project_id="dinnie_confidential_lynx_20766")
# print(project.project_data)
