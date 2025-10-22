"""This module will contain all CRUD for projects. Example, create, list projects, get project, delete project, update project, etc."""

from abc import ABCMeta
from ..client import LabellerrClient
from .. import constants, client_utils
from ..exceptions import InvalidProjectError
import uuid
from ..exceptions import LabellerrError
import logging
import utils
from .. import schemas
import json


class LabellerrProjectMeta(ABCMeta):
    # Class-level registry for project types
    _registry = {}

    @classmethod
    def register(cls, data_type, project_class):
        """Register a project type handler"""
        cls._registry[data_type] = project_class

    @staticmethod
    def get_project(client: LabellerrClient, project_id: str):
        """Get project from Labellerr API"""
        # ------------------------------- [needs refactoring after we consolidate api_calls into one function ] ---------------------------------
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/projects/{project_id}?client_id={client.client_id}"
            f"&uuid={unique_id}"
        )
        headers = client_utils.build_headers(
            api_key=client.api_key,
            api_secret=client.api_secret,
            client_id=client.client_id,
            extra_headers={"content-type": "application/json"},
        )

        response = client_utils.request(
            "GET", url, headers=headers, request_id=unique_id
        )
        return response.get("response", None)
        # ------------------------------- [needs refactoring after we consolidate api_calls into one function ] ---------------------------------

    """Metaclass that combines ABC functionality with factory pattern"""

    def __call__(cls, client, project_id, **kwargs):
        # Only intercept calls to the base LabellerrProject class
        if cls.__name__ != "LabellerrProject":
            # For subclasses, use normal instantiation
            instance = cls.__new__(cls)
            if isinstance(instance, cls):
                instance.__init__(client, project_id, **kwargs)
            return instance
        project_data = cls.get_project(client, project_id)
        if project_data is None:
            raise InvalidProjectError(f"Project not found: {project_id}")
        data_type = project_data.get("data_type")
        if data_type not in constants.DATA_TYPES:
            raise InvalidProjectError(f"Data type not supported: {data_type}")

        project_class = cls._registry.get(data_type)
        if project_class is None:
            raise InvalidProjectError(f"Unknown data type: {data_type}")
        kwargs["project_data"] = project_data
        return project_class(client, project_id, **kwargs)


class LabellerrProject(metaclass=LabellerrProjectMeta):
    """Base class for all Labellerr projects with factory behavior"""

    def __init__(self, client: LabellerrClient, project_id: str, **kwargs):
        self.client = client
        self.project_id = project_id
        self.project_data = kwargs["project_data"]

    @property
    def data_type(self):
        return self.project_data.get("data_type")

    @property
    def attached_datasets(self):
        return self.project_data.get("attached_datasets")

    def initiate_create_project(self, payload):
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
                    if (
                        not isinstance(payload[param], str)
                        or not payload[param].strip()
                    ):
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
                        raise LabellerrError(
                            "option_type is required in annotation_guide"
                        )
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

            if (
                isinstance(payload.get("files_to_upload"), list)
                and len(payload["files_to_upload"]) == 0
            ):
                payload.pop("files_to_upload")

            if "rotation_config" not in payload:
                payload["rotation_config"] = {
                    "annotation_rotation_count": 1,
                    "review_rotation_count": 1,
                    "client_review_rotation_count": 1,
                }
            self.validate_rotation_config(payload["rotation_config"])

            if payload["data_type"] not in constants.DATA_TYPES:
                raise LabellerrError(
                    f"Invalid data_type. Must be one of {constants.DATA_TYPES}"
                )

            logging.info("Rotation configuration validated . . .")

            logging.info("Creating dataset . . .")
            dataset_response = self.create_dataset(
                {
                    "client_id": payload["client_id"],
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
                    dataset_status = self.client.get_dataset(
                        payload["client_id"], dataset_id
                    )

                    if isinstance(dataset_status, dict):

                        if "response" in dataset_status:
                            return (
                                dataset_status["response"].get("status_code", 200)
                                == 300
                            )
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
                annotation_template_id = self.create_annotation_guideline(
                    payload["client_id"],
                    payload["annotation_guide"],
                    payload["project_name"],
                    payload["data_type"],
                )
            logging.info(f"Annotation guidelines created {annotation_template_id}")

            project_response = self.create_project(
                project_name=payload["project_name"],
                data_type=payload["data_type"],
                client_id=payload["client_id"],
                attached_datasets=[dataset_id],
                annotation_template_id=annotation_template_id,
                rotations=payload["rotation_config"],
                use_ai=payload.get("use_ai", False),
                created_by=payload["created_by"],
            )

            return {
                "status": "success",
                "message": "Project created successfully",
                "project_id": project_response,
            }

        except LabellerrError:
            raise
        except Exception:
            logging.exception("Unexpected error in project creation")
            raise

    def create_project(
        self,
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
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={
                "Origin": constants.ALLOWED_ORIGINS,
                "Content-Type": "application/json",
            },
        )

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )
