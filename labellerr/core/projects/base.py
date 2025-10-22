"""This module will contain all CRUD for projects. Example, create, list projects, get project, delete project, update project, etc."""

import concurrent
import json
import logging
import os
import uuid
from abc import ABCMeta
from datetime import time
from typing import TYPE_CHECKING, List

import requests

from .. import client_utils, constants, gcs, schemas, utils
from ..exceptions import InvalidProjectError, LabellerrError
from ..utils import validate_params

if TYPE_CHECKING:
    from ..client import LabellerrClient


class LabellerrProjectMeta(ABCMeta):
    # Class-level registry for project types
    _registry = {}

    @classmethod
    def register(cls, data_type, project_class):
        """Register a project type handler"""
        cls._registry[data_type] = project_class

    @staticmethod
    def get_project(client: "LabellerrClient", project_id: str):
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

    def __init__(self, client: "LabellerrClient", project_id: str, **kwargs):
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
            dataset_response = self.client.datasets.create_dataset(
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
                annotation_template_id = self.client.create_annotation_guideline(
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
            api_key=self.client.api_key,
            api_secret=self.client.api_secret,
            client_id=params.client_id,
            extra_headers={
                "Origin": constants.ALLOWED_ORIGINS,
                "Content-Type": "application/json",
            },
        )

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    def update_rotation_count(self):
        """
        Updates the rotation count for a project.

        :return: A dictionary indicating the success of the operation.
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/projects/rotations/add?project_id={self.project_id}&client_id={self.client.client_id}&uuid={unique_id}"

            headers = client_utils.build_headers(
                api_key=self.client.api_key,
                api_secret=self.client.api_secret,
                client_id=self.client.client_id,
                extra_headers={"content-type": "application/json"},
            )

            payload = json.dumps(self.rotation_config)
            logging.info(f"Update Rotation Count Payload: {payload}")

            response = requests.request("POST", url, headers=headers, data=payload)

            logging.info("Rotation configuration updated successfully.")
            client_utils.handle_response(response, unique_id)

            return {"msg": "project rotation configuration updated"}
        except LabellerrError as e:
            logging.error(f"Project rotation update config failed: {e}")
            raise

    def get_all_project_per_client_id(self, client_id):
        """
        Retrieves a list of projects associated with a client ID.

        :param client_id: The ID of the client.
        :return: A dictionary containing the list of projects.
        :raises LabellerrError: If the retrieval fails.
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/project_drafts/projects/detailed_list?client_id={client_id}&uuid={unique_id}"

            headers = client_utils.build_headers(
                api_key=self.client.api_key,
                api_secret=self.client.api_secret,
                client_id=client_id,
                extra_headers={"content-type": "application/json"},
            )

            response = requests.request("GET", url, headers=headers, data={})
            return client_utils.handle_response(response, unique_id)
        except Exception as e:
            logging.error(f"Failed to retrieve projects: {str(e)}")
            raise

    def _upload_preannotation_sync(
        self, project_id, client_id, annotation_format, annotation_file
    ):
        """
        Synchronous implementation of preannotation upload.

        :param project_id: The ID of the project.
        :param client_id: The ID of the client.
        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :return: The response from the API.
        :raises LabellerrError: If the upload fails.
        """
        try:
            # validate all the parameters
            required_params = {
                "project_id": project_id,
                "client_id": client_id,
                "annotation_format": annotation_format,
                "annotation_file": annotation_file,
            }
            client_utils.validate_required_params(
                required_params, list(required_params.keys())
            )
            client_utils.validate_annotation_format(annotation_format, annotation_file)

            request_uuid = str(uuid.uuid4())
            url = (
                f"{constants.BASE_URL}/actions/upload_answers?project_id={project_id}"
                f"&answer_format={annotation_format}&client_id={client_id}&uuid={request_uuid}"
            )
            file_name = client_utils.validate_file_exists(annotation_file)
            # get the direct upload url
            gcs_path = f"{project_id}/{annotation_format}-{file_name}"
            logging.info("Uploading your file to Labellerr. Please wait...")
            direct_upload_url = self.client.get_direct_upload_url(gcs_path, client_id)
            # Now let's wait for the file to be uploaded to the gcs
            gcs.upload_to_gcs_direct(direct_upload_url, annotation_file)
            payload = {}
            # with open(annotation_file, 'rb') as f:
            #     files = [
            #         ('file', (file_name, f, 'application/octet-stream'))
            #     ]
            #     response = requests.request("POST", url, headers={
            #         'client_id': client_id,
            #         'api_key': self.api_key,
            #         'api_secret': self.api_secret,
            #         'origin': constants.ALLOWED_ORIGINS,
            #         'source':'sdk',
            #         'email_id': self.api_key
            #     }, data=payload, files=files)
            url += "&gcs_path=" + gcs_path
            headers = client_utils.build_headers(
                api_key=self.client.api_key,
                api_secret=self.client.api_secret,
                client_id=client_id,
                extra_headers={"email_id": self.client.api_key},
            )
            response = requests.request("POST", url, headers=headers, data=payload)
            response_data = self.client._handle_upload_response(response, request_uuid)

            # read job_id from the response
            job_id = response_data["response"]["job_id"]
            self.client_id = client_id
            self.job_id = job_id
            self.project_id = project_id

            logging.info(f"Preannotation upload successful. Job ID: {job_id}")

            # Use max_retries=10 with 5-second intervals = 50 seconds max (fits within typical test timeouts)
            future = self.preannotation_job_status_async(
                max_retries=10, retry_interval=5
            )
            return future.result()
        except Exception as e:
            logging.error(f"Failed to upload preannotation: {str(e)}")
            raise

    def upload_preannotation_by_project_id_async(
        self, project_id, client_id, annotation_format, annotation_file
    ):
        """
        Asynchronously uploads preannotation data to a project.

        :param project_id: The ID of the project.
        :param client_id: The ID of the client.
        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :return: A Future object that will contain the response from the API.
        :raises LabellerrError: If the upload fails.
        """

        def upload_and_monitor():
            try:
                # validate all the parameters
                required_params = [
                    "project_id",
                    "client_id",
                    "annotation_format",
                    "annotation_file",
                ]
                for param in required_params:
                    if param not in locals():
                        raise LabellerrError(f"Required parameter {param} is missing")

                if annotation_format not in constants.ANNOTATION_FORMAT:
                    raise LabellerrError(
                        f"Invalid annotation_format. Must be one of {constants.ANNOTATION_FORMAT}"
                    )

                request_uuid = str(uuid.uuid4())
                url = (
                    f"{constants.BASE_URL}/actions/upload_answers?"
                    f"project_id={project_id}&answer_format={annotation_format}&client_id={client_id}&uuid={request_uuid}"
                )

                # validate if the file exist then extract file name from the path
                if os.path.exists(annotation_file):
                    file_name = os.path.basename(annotation_file)
                else:
                    raise LabellerrError("File not found")

                # Check if the file extension is .json when annotation_format is coco_json
                if annotation_format == "coco_json":
                    file_extension = os.path.splitext(annotation_file)[1].lower()
                    if file_extension != ".json":
                        raise LabellerrError(
                            "For coco_json annotation format, the file must have a .json extension"
                        )
                # get the direct upload url
                gcs_path = f"{project_id}/{annotation_format}-{file_name}"
                logging.info("Uploading your file to Labellerr. Please wait...")
                direct_upload_url = self.client.get_direct_upload_url(
                    gcs_path, client_id
                )
                # Now let's wait for the file to be uploaded to the gcs
                gcs.upload_to_gcs_direct(direct_upload_url, annotation_file)
                payload = {}
                # with open(annotation_file, 'rb') as f:
                #     files = [
                #         ('file', (file_name, f, 'application/octet-stream'))
                #     ]
                #     response = requests.request("POST", url, headers={
                #         'client_id': client_id,
                #         'api_key': self.api_key,
                #         'api_secret': self.api_secret,
                #         'origin': constants.ALLOWED_ORIGINS,
                #         'source':'sdk',
                #         'email_id': self.api_key
                #     }, data=payload, files=files)
                url += "&gcs_path=" + gcs_path
                headers = client_utils.build_headers(
                    api_key=self.client.api_key,
                    api_secret=self.client.api_secret,
                    client_id=client_id,
                    extra_headers={"email_id": self.client.api_key},
                )
                response = requests.request("POST", url, headers=headers, data=payload)
                response_data = self.client._handle_upload_response(
                    response, request_uuid
                )

                # read job_id from the response
                job_id = response_data["response"]["job_id"]
                self.client_id = client_id
                self.job_id = job_id
                self.project_id = project_id

                logging.info(f"Pre annotation upload successful. Job ID: {job_id}")

                # Now monitor the status
                headers = client_utils.build_headers(
                    api_key=self.client.api_key,
                    api_secret=self.client.api_secret,
                    client_id=self.client_id,
                    extra_headers={"Origin": constants.ALLOWED_ORIGINS},
                )
                status_url = f"{constants.BASE_URL}/actions/upload_answers_status?project_id={self.project_id}&job_id={self.job_id}&client_id={self.client_id}"
                while True:
                    try:
                        response = requests.request(
                            "GET", status_url, headers=headers, data={}
                        )
                        status_data = response.json()

                        logging.debug(f"Status data: {status_data}")

                        # Check if job is completed
                        if status_data.get("response", {}).get("status") == "completed":
                            return status_data

                        logging.info("Syncing status after 5 seconds . . .")
                        time.sleep(5)

                    except Exception as e:
                        logging.error(
                            f"Failed to get preannotation job status: {str(e)}"
                        )
                        raise

            except Exception as e:
                logging.exception(f"Failed to upload preannotation: {str(e)}")
                raise

        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(upload_and_monitor)

    def preannotation_job_status_async(self, max_retries=60, retry_interval=5):
        """
        Get the status of a preannotation job asynchronously with timeout protection.

        Args:
            max_retries: Maximum number of retries before timing out (default: 60 retries = 5 minutes)
            retry_interval: Seconds to wait between retries (default: 5 seconds)

        Returns:
            concurrent.futures.Future: A future that will contain the final job status

        Raises:
            LabellerrError: If max retries exceeded or job status check fails
        """

        def check_status():
            headers = client_utils.build_headers(
                api_key=self.client.api_key,
                api_secret=self.client.api_secret,
                client_id=self.client_id,
                extra_headers={"Origin": constants.ALLOWED_ORIGINS},
            )
            url = f"{constants.BASE_URL}/actions/upload_answers_status?project_id={self.project_id}&job_id={self.job_id}&client_id={self.client_id}"
            payload = {}
            retry_count = 0

            while retry_count < max_retries:
                try:
                    response = requests.request(
                        "GET", url, headers=headers, data=payload
                    )
                    response_data = response.json()

                    # Check if job is completed
                    if response_data.get("response", {}).get("status") == "completed":
                        logging.info(
                            f"Pre-annotation job completed after {retry_count} retries"
                        )
                        return response_data

                    retry_count += 1
                    if retry_count < max_retries:
                        logging.info(
                            f"Retry {retry_count}/{max_retries}: Job not complete, retrying after {retry_interval} seconds..."
                        )
                        time.sleep(retry_interval)
                    else:
                        # Max retries exceeded
                        total_wait_time = max_retries * retry_interval
                        raise LabellerrError(
                            f"Pre-annotation job did not complete after {max_retries} retries "
                            f"({total_wait_time} seconds). Job ID: {self.job_id}. "
                            f"Last status: {response_data.get('response', {}).get('status', 'unknown')}"
                        )

                except LabellerrError:
                    # Re-raise LabellerrError without wrapping
                    raise
                except Exception as e:
                    logging.error(f"Failed to get preannotation job status: {str(e)}")
                    raise LabellerrError(
                        f"Failed to get preannotation job status: {str(e)}"
                    )
            return None

        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(check_status)

    def upload_preannotation_by_project_id(
        self, project_id, client_id, annotation_format, annotation_file
    ):
        """
        Uploads preannotation data to a project.

        :param project_id: The ID of the project.
        :param client_id: The ID of the client.
        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :return: The response from the API.
        :raises LabellerrError: If the upload fails.
        """
        try:
            # validate all the parameters
            required_params = [
                "project_id",
                "client_id",
                "annotation_format",
                "annotation_file",
            ]
            for param in required_params:
                if param not in locals():
                    raise LabellerrError(f"Required parameter {param} is missing")

            if annotation_format not in constants.ANNOTATION_FORMAT:
                raise LabellerrError(
                    f"Invalid annotation_format. Must be one of {constants.ANNOTATION_FORMAT}"
                )

            request_uuid = str(uuid.uuid4())
            url = (
                f"{constants.BASE_URL}/actions/upload_answers?project_id={project_id}"
                f"&answer_format={annotation_format}&client_id={client_id}&uuid={request_uuid}"
            )

            # validate if the file exist then extract file name from the path
            if os.path.exists(annotation_file):
                file_name = os.path.basename(annotation_file)
            else:
                raise LabellerrError("File not found")

            payload = {}
            with open(annotation_file, "rb") as f:
                files = [("file", (file_name, f, "application/octet-stream"))]
                headers = client_utils.build_headers(
                    api_key=self.client.api_key,
                    api_secret=self.client.api_secret,
                    client_id=client_id,
                    extra_headers={"email_id": self.client.api_key},
                )
                response = requests.request(
                    "POST", url, headers=headers, data=payload, files=files
                )
            response_data = self.client._handle_upload_response(response, request_uuid)
            logging.debug(f"response_data: {response_data}")

            # read job_id from the response
            job_id = response_data["response"]["job_id"]
            self.client_id = client_id
            self.job_id = job_id
            self.project_id = project_id

            logging.info(f"Preannotation upload successful. Job ID: {job_id}")

            # Use max_retries=10 with 5-second intervals = 50 seconds max (fits within typical test timeouts)
            future = self.preannotation_job_status_async(
                max_retries=10, retry_interval=5
            )
            return future.result()
        except Exception as e:
            logging.error(f"Failed to upload preannotation: {str(e)}")
            raise

    def create_local_export(self, project_id, client_id, export_config):
        """
        Creates a local export with the given configuration.

        :param project_id: The ID of the project.
        :param client_id: The ID of the client.
        :param export_config: Export configuration dictionary.
        :return: The response from the API.
        :raises LabellerrError: If the export creation fails.
        """
        # Validate parameters using Pydantic
        schemas.CreateLocalExportParams(
            project_id=project_id,
            client_id=client_id,
            export_config=export_config,
        )
        # Validate export config using client_utils
        client_utils.validate_export_config(export_config)

        unique_id = client_utils.generate_request_id()
        export_config.update({"export_destination": "local", "question_ids": ["all"]})

        payload = json.dumps(export_config)
        headers = client_utils.build_headers(
            api_key=self.client.api_key,
            api_secret=self.client.api_secret,
            extra_headers={
                "Origin": constants.ALLOWED_ORIGINS,
                "Content-Type": "application/json",
            },
        )

        return client_utils.request(
            "POST",
            f"{constants.BASE_URL}/sdk/export/files?project_id={project_id}&client_id={client_id}",
            headers=headers,
            data=payload,
            request_id=unique_id,
        )

    @validate_params(project_id=str, report_ids=list, client_id=str)
    def check_export_status(
        self, project_id: str, report_ids: List[str], client_id: str
    ):
        request_uuid = client_utils.generate_request_id()
        try:
            if not project_id:
                raise LabellerrError("project_id cannot be null")
            if not report_ids:
                raise LabellerrError("report_ids cannot be empty")

            # Construct URL
            url = f"{constants.BASE_URL}/exports/status?project_id={project_id}&uuid={request_uuid}&client_id={client_id}"

            # Headers
            headers = client_utils.build_headers(
                api_key=self.client.api_key,
                api_secret=self.client.api_secret,
                client_id=client_id,
                extra_headers={"Content-Type": "application/json"},
            )

            payload = json.dumps({"report_ids": report_ids})

            response = requests.post(url, headers=headers, data=payload)
            result = client_utils.handle_response(response, request_uuid)

            # Now process each report_id
            for status_item in result.get("status", []):
                if (
                    status_item.get("is_completed")
                    and status_item.get("export_status") == "Created"
                ):
                    # Download URL if job completed
                    download_url = (  # noqa E999 todo check use of that
                        self.client.fetch_download_url(
                            project_id=project_id,
                            uuid=request_uuid,
                            export_id=status_item["report_id"],
                            client_id=client_id,
                        )
                    )

            return json.dumps(result, indent=2)

        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to check export status: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error checking export status: {str(e)}")
            raise

    def list_file(
        self, client_id, project_id, search_queries, size=10, next_search_after=None
    ):
        # Validate parameters using Pydantic
        params = schemas.ListFileParams(
            client_id=client_id,
            project_id=project_id,
            search_queries=search_queries,
            size=size,
            next_search_after=next_search_after,
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/search/project_files?project_id={params.project_id}&client_id={params.client_id}&uuid={unique_id}"

        headers = client_utils.build_headers(
            api_key=self.client.api_key,
            api_secret=self.client.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps(
            {
                "search_queries": params.search_queries,
                "size": params.size,
                "next_search_after": params.next_search_after,
            }
        )

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    def bulk_assign_files(self, client_id, project_id, file_ids, new_status):
        # Validate parameters using Pydantic
        params = schemas.BulkAssignFilesParams(
            client_id=client_id,
            project_id=project_id,
            file_ids=file_ids,
            new_status=new_status,
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/actions/files/bulk_assign?project_id={params.project_id}&uuid={unique_id}&client_id={params.client_id}"

        headers = client_utils.build_headers(
            api_key=self.client.api_key,
            api_secret=self.client.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps(
            {
                "file_ids": params.file_ids,
                "new_status": params.new_status,
            }
        )

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    def validate_rotation_config(self, rotation_config):
        """
        Validates a rotation configuration.

        :param rotation_config: A dictionary containing the configuration for the rotations.
        :raises LabellerrError: If the configuration is invalid.
        """
        client_utils.validate_rotation_config(rotation_config)
