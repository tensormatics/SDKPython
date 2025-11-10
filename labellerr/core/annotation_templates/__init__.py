from .base import LabellerrAnnotationTemplate
from ..schemas.annotation_templates import CreateTemplateParams, QuestionType, Option
from .. import constants
from ..client import LabellerrClient
import uuid

__all__ = [
    "LabellerrAnnotationTemplate",
]

object_types = [
    QuestionType.bounding_box,
    QuestionType.polygon,
    QuestionType.polyline,
    QuestionType.dot,
]


def create_template(
    client: LabellerrClient, params: CreateTemplateParams
) -> LabellerrAnnotationTemplate:
    """Create an annotation template"""
    unique_id = str(uuid.uuid4())
    for question in params.questions:
        if question.question_type in object_types and not question.color:
            raise ValueError(
                "Color is required for bounding box, polygon, polyline, and dot questions"
            )

        if question.question_type in object_types:
            question.options = [Option(option_name=question.color)]

    # Convert questions to the expected format
    questions_data = []
    for question in params.questions:
        question_dict = question.model_dump()
        # Convert enum to string value
        question_dict["option_type"] = question.question_type.value
        # Remove question_type as it's now option_type
        question_dict.pop("question_type", None)
        questions_data.append(question_dict)

    payload = {"templateName": params.template_name, "questions": questions_data}
    url = (
        f"{constants.BASE_URL}/annotations/create_template?client_id={client.client_id}&data_type={params.data_type.value}"
        f"&uuid={unique_id}"
    )

    response = client.make_request(
        "POST",
        url,
        extra_headers={"content-type": "application/json"},
        json=payload,
        request_id=unique_id,
    )
    return LabellerrAnnotationTemplate(
        client=client,
        annotation_template_id=response.get("response", None).get("template_id"),
    )
