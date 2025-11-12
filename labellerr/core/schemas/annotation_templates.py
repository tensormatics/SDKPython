from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
from ..schemas import DatasetDataType


class QuestionType(str, Enum):
    bounding_box = "BoundingBox"
    polygon = "polygon"
    polyline = "polyline"
    dot = "dot"
    input = "input"
    radio = "radio"
    boolean = "boolean"
    select = "select"
    dropdown = "dropdown"
    stt = "stt"
    imc = "imc"


class Option(BaseModel):
    option_name: str


class AnnotationQuestion(BaseModel):
    """Question structure for annotation templates."""

    question_number: int
    question: str
    question_id: str
    question_type: QuestionType
    required: bool
    options: Optional[List[Option]] = []
    color: Optional[str] = None


class CreateTemplateParams(BaseModel):
    """Parameters for creating an annotation template."""

    template_name: str
    data_type: DatasetDataType
    questions: List[AnnotationQuestion]
