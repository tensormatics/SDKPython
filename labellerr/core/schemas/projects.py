"""
Schema models for project operations.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class RotationConfig(BaseModel):
    """Rotation configuration model."""

    annotation_rotation_count: int = Field(ge=1)
    review_rotation_count: int = Field(ge=1)
    client_review_rotation_count: int = Field(ge=1)


class Question(BaseModel):
    """Question structure for annotation templates."""

    option_type: Literal[
        "input",
        "radio",
        "boolean",
        "select",
        "dropdown",
        "stt",
        "imc",
        "BoundingBox",
        "polygon",
        "dot",
        "audio",
    ]
    # Additional fields can be added as needed


class CreateProjectParams(BaseModel):
    """Parameters for creating a project."""

    project_name: str = Field(min_length=1)
    data_type: Literal["image", "video", "audio", "document", "text"]
    client_id: str = Field(min_length=1)
    attached_datasets: List[str] = Field(min_length=1)
    annotation_template_id: str
    rotations: RotationConfig
    use_ai: bool = False
    created_by: Optional[str] = None

    @field_validator("attached_datasets")
    @classmethod
    def validate_attached_datasets(cls, v):
        if not v:
            raise ValueError("must contain at least one dataset ID")
        for i, dataset_id in enumerate(v):
            if not isinstance(dataset_id, str) or not dataset_id.strip():
                raise ValueError(f"dataset_id at index {i} must be a non-empty string")
        return v


class CreateTemplateParams(BaseModel):
    """Parameters for creating an annotation template."""

    client_id: str = Field(min_length=1)
    data_type: Literal["image", "video", "audio", "document", "text"]
    template_name: str = Field(min_length=1)
    questions: List[Question] = Field(min_length=1)


class CreateLocalExportParams(BaseModel):
    """Parameters for creating a local export."""

    project_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    export_config: Dict[str, Any]

