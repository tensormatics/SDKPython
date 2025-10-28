import json
import logging
import uuid

import requests

from labellerr import LabellerrClient

from .. import client_utils, constants, schemas, utils
from ..datasets import LabellerrDataset, create_dataset
from ..exceptions import LabellerrError
from .audio_project import AudioProject as LabellerrAudioProject
from .base import LabellerrProject
from .document_project import DocucmentProject as LabellerrDocumentProject
from .image_project import ImageProject as LabellerrImageProject
from .utils import validate_rotation_config
from .video_project import VideoProject as LabellerrVideoProject

__all__ = [
    "LabellerrImageProject",
    "LabellerrVideoProject",
    "LabellerrProject",
    "LabellerrDocumentProject",
    "LabellerrAudioProject",
]


def create_project(client: "LabellerrClient", payload: dict):
    """
    Orchestrates project creation by handling dataset creation, annotation guidelines,
    and final project setup.
    """

    try:
        # validate all the parameters
        required_params = [
            "data_type",
            "created_by",
            "project_name",
            # Either annotation_guide or annotation_template_id must be provided
            "autolabel",
        ]
        for param in required_params:
            if param not in payload:
                raise LabellerrError(f"Required parameter {param} is missing")

        # Validate created_by email format
        created_by = payload.get("created_by")
        if (
            not isinstance(created_by, str)
            or "@" not in created_by
            or "." not in created_by.split("@")[-1]
        ):
            raise LabellerrError("Please enter email id in created_by")

        # Ensure either annotation_guide or annotation_template_id is provided
        if not payload.get("annotation_guide") and not payload.get(
            "annotation_template_id"
        ):
            raise LabellerrError(
                "Please provide either annotation guide or annotation template id"
            )

        # If annotation_guide is provided, validate its entries
        if payload.get("annotation_guide"):
            for guide in payload["annotation_guide"]:
                if "option_type" not in guide:
                    raise LabellerrError("option_type is required in annotation_guide")
                if guide["option_type"] not in constants.OPTION_TYPE_LIST:
                    raise LabellerrError(
                        f"option_type must be one of {constants.OPTION_TYPE_LIST}"
                    )

        if "rotation_config" not in payload:
            payload["rotation_config"] = {
                "annotation_rotation_count": 1,
                "review_rotation_count": 1,
                "client_review_rotation_count": 1,
            }
        validate_rotation_config(payload["rotation_config"])

        if payload["data_type"] not in constants.DATA_TYPES:
            raise LabellerrError(
                f"Invalid data_type. Must be one of {constants.DATA_TYPES}"
            )

        logging.info("Rotation configuration validated . . .")

        # Handle dataset logic - either use existing datasets or create new ones
        if "datasets" in payload:
            # Use existing datasets
            datasets = payload["datasets"]
            if not isinstance(datasets, list) or len(datasets) == 0:
                raise LabellerrError("datasets must be a non-empty list of dataset IDs")

            # Validate that all datasets exist and have files
            logging.info("Validating existing datasets . . .")
            for dataset_id in datasets:
                try:
                    dataset = LabellerrDataset(client, dataset_id)
                    if dataset.files_count <= 0:
                        raise LabellerrError(f"Dataset {dataset_id} has no files")
                except Exception as e:
                    raise LabellerrError(
                        f"Dataset {dataset_id} does not exist or is invalid: {str(e)}"
                    )

            attached_datasets = datasets
            logging.info("All datasets validated successfully")
        else:
            # Create new dataset (existing logic)
            # Validate absence of dataset_name
            if "dataset_name" not in payload:
                dataset_name = payload.get("project_name")
                dataset_description = (
                    f"Dataset for Project - {payload.get('project_name')}"
                )

            if "folder_to_upload" in payload and "files_to_upload" in payload:
                raise LabellerrError(
                    "Cannot provide both files_to_upload and folder_to_upload"
                )

            if "folder_to_upload" not in payload and "files_to_upload" not in payload:
                raise LabellerrError(
                    "Either files_to_upload or folder_to_upload must be provided"
                )

            # Check for empty files_to_upload list
            if (
                isinstance(payload.get("files_to_upload"), list)
                and len(payload["files_to_upload"]) == 0
            ):
                raise LabellerrError("files_to_upload cannot be an empty list")

            # Check for empty/whitespace folder_to_upload
            if "folder_to_upload" in payload:
                folder_path = payload.get("folder_to_upload", "").strip()
                if not folder_path:
                    raise LabellerrError("Folder path does not exist")

            logging.info("Creating dataset . . .")

            dataset = create_dataset(
                client,
                schemas.DatasetConfig(
                    client_id=client.client_id,
                    dataset_name=dataset_name,
                    data_type=payload["data_type"],
                    dataset_description=dataset_description,
                    connector_type="local",
                ),
                files_to_upload=payload.get("files_to_upload"),
                folder_to_upload=payload.get("folder_to_upload"),
            )

            def dataset_ready():
                response = LabellerrDataset(
                    client, dataset.dataset_id
                )  # Fetch dataset again to get the status code
                return response.status_code == 300 and response.files_count > 0

            utils.poll(
                function=dataset_ready,
                condition=lambda x: x is True,
                interval=5,
            )

            attached_datasets = [dataset.dataset_id]
            logging.info("Dataset created and ready for use")

        if payload.get("annotation_template_id"):
            annotation_template_id = payload["annotation_template_id"]
        else:
            annotation_template_id = create_annotation_guideline(
                client,
                payload["annotation_guide"],
                payload["project_name"],
                payload["data_type"],
            )
        logging.info(f"Annotation guidelines created {annotation_template_id}")
        project_response = __create_project_api_call(
            client=client,
            project_name=payload["project_name"],
            data_type=payload["data_type"],
            client_id=client.client_id,
            attached_datasets=attached_datasets,
            annotation_template_id=annotation_template_id,
            rotations=payload["rotation_config"],
            use_ai=payload.get("use_ai", False),
            created_by=payload["created_by"],
        )
        return LabellerrProject(
            client, project_id=project_response["response"]["project_id"]
        )
    except LabellerrError:
        raise
    except Exception:
        logging.exception("Unexpected error in project creation")
        raise


def __create_project_api_call(
    client: "LabellerrClient",
    project_name,
    data_type,
    client_id,
    attached_datasets,
    annotation_template_id,
    rotations,
    use_ai=False,
    created_by=None,
):
    """
    Creates a project with the given configuration.

    :param project_name: Name of the project
    :param data_type: Type of data (image, video, etc.)
    :param client_id: ID of the client
    :param attached_datasets: List of dataset IDs to attach to the project
    :param annotation_template_id: ID of the annotation template
    :param rotations: Dictionary containing rotation configuration
    :param use_ai: Boolean flag for AI usage (default: False)
    :param created_by: Optional creator information
    :return: Project creation response
    :raises LabellerrError: If the creation fails
    """
    # Validate parameters using Pydantic
    params = schemas.CreateProjectParams(
        project_name=project_name,
        data_type=data_type,
        client_id=client_id,
        attached_datasets=attached_datasets,
        annotation_template_id=annotation_template_id,
        rotations=rotations,
        use_ai=use_ai,
        created_by=created_by,
    )
    unique_id = str(uuid.uuid4())
    url = f"{constants.BASE_URL}/projects/create?client_id={params.client_id}&uuid={unique_id}"

    payload = json.dumps(
        {
            "project_name": params.project_name,
            "attached_datasets": params.attached_datasets,
            "data_type": params.data_type,
            "annotation_template_id": str(params.annotation_template_id),
            "rotations": params.rotations.model_dump(),
            "use_ai": params.use_ai,
            "created_by": params.created_by,
        }
    )
    headers = client_utils.build_headers(
        api_key=client.api_key,
        api_secret=client.api_secret,
        client_id=params.client_id,
        extra_headers={
            "Origin": constants.ALLOWED_ORIGINS,
            "Content-Type": "application/json",
        },
    )

    return client.make_request(
        "POST", url, headers=headers, data=payload, request_id=unique_id
    )


def create_annotation_guideline(
    client: "LabellerrClient", questions, template_name, data_type
):
    unique_id = str(uuid.uuid4())
    url = f"{constants.BASE_URL}/annotations/create_template?data_type={data_type}&client_id={client.client_id}&uuid={unique_id}"

    guide_payload = json.dumps({"templateName": template_name, "questions": questions})

    try:
        response_data = client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=guide_payload,
        )
        return response_data["response"]["template_id"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to update project annotation guideline: {str(e)}")
        raise
