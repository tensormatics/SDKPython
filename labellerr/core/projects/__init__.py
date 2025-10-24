import json
import logging
import uuid

import requests

from labellerr import LabellerrClient
from labellerr.core import utils

from .. import constants
from ..datasets import LabellerrDataset, create_dataset
from ..exceptions import LabellerrError
from .base import LabellerrProject
from .image_project import ImageProject as LabellerrImageProject
from .utils import validate_rotation_config
from .video_project import VideoProject as LabellerrVideoProject

__all__ = ["LabellerrImageProject", "LabellerrVideoProject", "LabellerrProject"]


def create_project(client: "LabellerrClient", payload: dict):
    """
    Orchestrates project creation by handling dataset creation, annotation guidelines,
    and final project setup.
    """

    try:
        # validate all the parameters
        required_params = [
            "client_id",
            "dataset_name",
            "dataset_description",
            "data_type",
            "created_by",
            "project_name",
            # Either annotation_guide or annotation_template_id must be provided
            "autolabel",
        ]
        for param in required_params:
            if param not in payload:
                raise LabellerrError(f"Required parameter {param} is missing")

            if param == "client_id":
                if not isinstance(payload[param], str) or not payload[param].strip():
                    raise LabellerrError("client_id must be a non-empty string")

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

        # Create DataSets instance for API operations

        logging.info("Creating dataset . . .")
        dataset_response = create_dataset(
            {
                "client_id": payload["client_id"],
                "dataset_config": payload["dataset_config"],
                "dataset_name": payload["dataset_name"],
                "data_type": payload["data_type"],
                "dataset_description": payload["dataset_description"],
            },
            files_to_upload=payload.get("files_to_upload"),
            folder_to_upload=payload.get("folder_to_upload"),
        )

        dataset_id = dataset_response["dataset_id"]

        def dataset_ready():
            try:
                dataset_status = LabellerrDataset.get_dataset(
                    payload["client_id"], dataset_id
                )

                if isinstance(dataset_status, dict):

                    if "response" in dataset_status:
                        return dataset_status["response"].get("status_code", 200) == 300
                    else:

                        return True
                return False
            except Exception as e:
                logging.error(f"Error checking dataset status: {e}")
                return False

        utils.poll(
            function=dataset_ready,
            condition=lambda x: x is True,
            interval=5,
            timeout=60,
        )

        logging.info("Dataset created and ready for use")

        if payload.get("annotation_template_id"):
            annotation_template_id = payload["annotation_template_id"]
        else:
            annotation_template_id = create_annotation_guideline(
                payload["client_id"],
                payload["annotation_guide"],
                payload["project_name"],
                payload["data_type"],
            )
        logging.info(f"Annotation guidelines created {annotation_template_id}")
        # TODO : add api call
        project_response = create_project(
            project_name=payload["project_name"],
            data_type=payload["data_type"],
            client_id=payload["client_id"],
            attached_datasets=[dataset_id],
            annotation_template_id=annotation_template_id,
            rotations=payload["rotation_config"],
            use_ai=payload.get("use_ai", False),
            created_by=payload["created_by"],
        )

        return LabellerrProject(client, project_id=project_response["project_id"])
    except LabellerrError:
        raise
    except Exception:
        logging.exception("Unexpected error in project creation")
        raise


def create_annotation_guideline(self, client_id, questions, template_name, data_type):
    unique_id = str(uuid.uuid4())
    url = f"{constants.BASE_URL}/annotations/create_template?data_type={data_type}&client_id={client_id}&uuid={unique_id}"

    guide_payload = json.dumps({"templateName": template_name, "questions": questions})

    try:
        response_data = self.client.make_request(
            "POST",
            url,
            client_id=client_id,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=guide_payload,
        )
        return response_data["response"]["template_id"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to update project annotation guideline: {str(e)}")
        raise
