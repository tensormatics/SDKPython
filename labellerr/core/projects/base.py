"""This module will contain all CRUD for projects. Example, create, list projects, get project, delete project, update project, etc."""

import concurrent.futures
import json
import logging
import os
import uuid
from abc import ABCMeta
from typing import TYPE_CHECKING, Dict, List

import requests

from .. import client_utils, constants, gcs, schemas
from ..exceptions import InvalidProjectError, LabellerrError
from ..utils import poll, validate_params

if TYPE_CHECKING:
    from ..client import LabellerrClient


class LabellerrProjectMeta(ABCMeta):
    # Class-level registry for project types
    _registry: Dict[str, type] = {}

    @classmethod
    def _register(cls, data_type, project_class):
        """Register a project type handler"""
        cls._registry[data_type] = project_class

    @staticmethod
    def get_project(client: "LabellerrClient", project_id: str):
        """Get project from Labellerr API"""
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/projects/project/{project_id}?client_id={client.client_id}"
            f"&uuid={unique_id}"
        )

        response = client.make_request(
            "GET",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
        )
        return response.get("response", None)

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

    def detach_dataset_from_project(self, dataset_id=None, dataset_ids=None):
        """
        Detaches one or more datasets from an existing project.

        :param dataset_id: The ID of a single dataset to detach (for backward compatibility)
        :param dataset_ids: List of dataset IDs to detach (for batch operations)
        :return: Dictionary containing detachment status
        :raises LabellerrError: If the operation fails or if neither dataset_id nor dataset_ids is provided
        """
        # Handle both single and batch operations
        if dataset_id is None and dataset_ids is None:
            raise LabellerrError("Either dataset_id or dataset_ids must be provided")

        if dataset_id is not None and dataset_ids is not None:
            raise LabellerrError(
                "Cannot provide both dataset_id and dataset_ids. Use dataset_ids for batch operations."
            )

        # Convert single dataset_id to list for uniform processing
        if dataset_id is not None:
            dataset_ids = [dataset_id]

        # Validate parameters using Pydantic for each dataset
        validated_dataset_ids = []
        for ds_id in dataset_ids:
            params = schemas.DetachDatasetParams(
                client_id=self.client.client_id,
                project_id=self.project_id,
                dataset_id=ds_id,
            )
            validated_dataset_ids.append(str(params.dataset_id))

        # Use the first params validation for client_id and project_id
        params = schemas.DetachDatasetParams(
            client_id=self.client.client_id,
            project_id=self.project_id,
            dataset_id=dataset_ids[0],
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/actions/jobs/delete_datasets_from_project?project_id={self.project_id}&uuid={unique_id}"

        payload = json.dumps({"attached_datasets": validated_dataset_ids})

        return self.client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )

    def attach_dataset_to_project(self, dataset_id=None, dataset_ids=None):
        """
        Attaches one or more datasets to an existing project.

        :param dataset_id: The ID of a single dataset to attach (for backward compatibility)
        :param dataset_ids: List of dataset IDs to attach (for batch operations)
        :return: Dictionary containing attachment status
        :raises LabellerrError: If the operation fails or if neither dataset_id nor dataset_ids is provided
        """
        # Handle both single and batch operations
        if dataset_id is None and dataset_ids is None:
            raise LabellerrError("Either dataset_id or dataset_ids must be provided")

        if dataset_id is not None and dataset_ids is not None:
            raise LabellerrError(
                "Cannot provide both dataset_id and dataset_ids. Use dataset_ids for batch operations."
            )

        # Convert single dataset_id to list for uniform processing
        if dataset_id is not None:
            dataset_ids = [dataset_id]

        # Validate parameters using Pydantic for each dataset
        validated_dataset_ids = []
        for ds_id in dataset_ids:
            params = schemas.AttachDatasetParams(
                client_id=self.client.client_id,
                project_id=self.project_id,
                dataset_id=ds_id,
            )
            validated_dataset_ids.append(str(params.dataset_id))

        # Use the first params validation for client_id and project_id
        params = schemas.AttachDatasetParams(
            client_id=self.client.client_id,
            project_id=self.project_id,
            dataset_id=dataset_ids[0],
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/actions/jobs/add_datasets_to_project?project_id={params.project_id}&uuid={unique_id}&client_id={params.client_id}"

        payload = json.dumps({"attached_datasets": validated_dataset_ids})

        return self.client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )

    def update_rotation_count(self, rotation_config):
        """
        Updates the rotation count for a project.

        :return: A dictionary indicating the success of the operation.
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/projects/rotations/add?project_id={self.project_id}&client_id={self.client.client_id}&uuid={unique_id}"

            payload = json.dumps(rotation_config)
            logging.info(f"Update Rotation Count Payload: {payload}")

            self.client.make_request(
                "POST",
                url,
                extra_headers={"content-type": "application/json"},
                request_id=unique_id,
                data=payload,
            )

            logging.info("Rotation configuration updated successfully.")

            return {"msg": "project rotation configuration updated"}
        except LabellerrError as e:
            logging.error(f"Project rotation update config failed: {e}")
            raise

    @staticmethod
    def list_all_projects(client: "LabellerrClient"):
        """
        Retrieves a list of projects associated with a client ID.

        :param client: The client instance.
        :return: A dictionary containing the list of projects.
        :raises LabellerrError: If the retrieval fails.
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/project_drafts/projects/detailed_list?client_id={client.client_id}&uuid={unique_id}"

            return client.make_request(
                "GET",
                url,
                extra_headers={"content-type": "application/json"},
                request_id=unique_id,
            )
        except Exception as e:
            logging.error(f"Failed to retrieve projects: {str(e)}")
            raise

    def _upload_preannotation_sync(
        self,
        project_id,
        client_id,
        annotation_format,
        annotation_file,
        conf_bucket=None,
    ):
        """
        Synchronous implementation of preannotation upload.

        :param project_id: The ID of the project.
        :param client_id: The ID of the client.
        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :param conf_bucket: Confidence bucket [low, medium, high]
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
            url = f"{constants.BASE_URL}/actions/upload_answers?project_id={project_id}&answer_format={annotation_format}&client_id={client_id}&uuid={request_uuid}"
            if conf_bucket:
                assert conf_bucket in [
                    "low",
                    "medium",
                    "high",
                ], "Invalid confidence bucket value. Must be one of [low, medium, high]"
                url += f"&conf_bucket={conf_bucket}"
            file_name = client_utils.validate_file_exists(annotation_file)
            # get the direct upload url
            gcs_path = f"{project_id}/{annotation_format}-{file_name}"
            logging.info("Uploading your file to Labellerr. Please wait...")
            direct_upload_url = self.get_direct_upload_url(gcs_path, client_id)
            # Now let's wait for the file to be uploaded to the gcs
            gcs.upload_to_gcs_direct(direct_upload_url, annotation_file)
            payload = {}
            url += "&gcs_path=" + gcs_path

            response = self.client.make_request(
                "POST",
                url,
                extra_headers={"email_id": self.client.api_key},
                request_id=request_uuid,
                handle_response=False,
                data=payload,
            )
            response_data = self.client.handle_upload_response(response, request_uuid)

            # read job_id from the response
            job_id = response_data["response"]["job_id"]
            self.client_id = client_id

            logging.info(f"Preannotation upload successful. Job ID: {job_id}")

            # Use max_retries=10 with 5-second intervals = 50 seconds max (fits within typical test timeouts)
            future = self.preannotation_job_status_async(project_id, job_id)
            return future.result()
        except Exception as e:
            logging.error(f"Failed to upload preannotation: {str(e)}")
            raise

    def upload_preannotation_async(
        self, annotation_format, annotation_file, conf_bucket=None
    ):
        """
        Asynchronously uploads preannotation data to a project.

        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :param conf_bucket: Confidence bucket [low, medium, high]
        :return: A Future object that will contain the response from the API.
        :raises LabellerrError: If the upload fails.

        """

        def upload_and_monitor():
            try:
                # validate all the parameters
                required_params = [
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
                    f"project_id={self.project_id}&answer_format={annotation_format}&client_id={self.client.client_id}&uuid={request_uuid}"
                )
                if conf_bucket:
                    assert conf_bucket in [
                        "low",
                        "medium",
                        "high",
                    ], "Invalid confidence bucket value. Must be one of [low, medium, high]"
                    url += f"&conf_bucket={conf_bucket}"
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
                gcs_path = f"{self.project_id}/{annotation_format}-{file_name}"
                logging.info("Uploading your file to Labellerr. Please wait...")
                direct_upload_url = self.get_direct_upload_url(
                    gcs_path, self.client.client_id
                )
                # Now let's wait for the file to be uploaded to the gcs
                gcs.upload_to_gcs_direct(direct_upload_url, annotation_file)
                payload = {}
                url += "&gcs_path=" + gcs_path

                response = self.client.make_request(
                    "POST",
                    url,
                    extra_headers={"email_id": self.client.api_key},
                    request_id=request_uuid,
                    handle_response=False,
                    data=payload,
                )
                response_data = self.client.handle_upload_response(
                    response, request_uuid
                )

                # read job_id from the response
                job_id = response_data["response"]["job_id"]

                logging.info(f"Pre annotation upload successful. Job ID: {job_id}")

                # Now monitor the status
                status_url = f"{constants.BASE_URL}/actions/upload_answers_status?project_id={self.project_id}&job_id={job_id}&client_id={self.client.client_id}"

                def check_job_status():
                    status_data = self.client.make_request(
                        "GET",
                        status_url,
                        extra_headers={"Origin": constants.ALLOWED_ORIGINS},
                    )
                    logging.debug(f"Status data: {status_data}")
                    return status_data

                def is_job_completed(status_data):
                    return status_data.get("response", {}).get("status") == "completed"

                def on_success(status_data):
                    logging.info("Pre-annotation job completed.")

                def on_exception(e):
                    logging.error(f"Failed to get preannotation job status: {str(e)}")
                    raise LabellerrError(
                        f"Failed to get preannotation job status: {str(e)}"
                    )

                result = poll(
                    function=check_job_status,
                    condition=is_job_completed,
                    interval=5.0,
                    on_success=on_success,
                    on_exception=on_exception,
                )

                return result

            except Exception as e:
                logging.exception(f"Failed to upload preannotation: {str(e)}")
                raise

        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(upload_and_monitor)

    def preannotation_job_status_async(self, job_id):
        """
        Get the status of a preannotation job asynchronously with timeout protection.

        Args:
            job_id: The job ID to check status for
            max_retries: Maximum number of retries before timing out (default: 60 retries = 5 minutes)
            retry_interval: Seconds to wait between retries (default: 5 seconds)

        Returns:
            concurrent.futures.Future: A future that will contain the final job status

        Raises:
            LabellerrError: If max retries exceeded or job status check fails
        """

        def check_status():
            url = f"{constants.BASE_URL}/actions/upload_answers_status?project_id={self.project_id}&job_id={job_id}&client_id={self.client.client_id}"

            def get_job_status():
                response_data = self.client.make_request(
                    "GET",
                    url,
                    client_id=self.client.client_id,
                    extra_headers={"Origin": constants.ALLOWED_ORIGINS},
                )

                # Log current status for visibility
                current_status = response_data.get("response", {}).get(
                    "status", "unknown"
                )
                logging.info(f"Pre-annotation job status: {current_status}")

                # Check if job failed and raise error immediately
                if current_status == "failed":
                    raise LabellerrError("Internal server error: ", response_data)

                return response_data

            def is_job_completed(response_data):
                return response_data.get("response", {}).get("status") == "completed"

            def on_success(response_data):
                logging.info("Pre-annotation job completed successfully!")

            def on_exception(e):
                logging.exception(f"Failed to get preannotation job status: {str(e)}")
                raise LabellerrError(
                    f"Failed to get preannotation job status: {str(e)}"
                )

            return poll(
                function=get_job_status,
                condition=is_job_completed,
                on_success=on_success,
                on_exception=on_exception,
            )

        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(check_status)

    def upload_preannotations(
        self, annotation_format, annotation_file, conf_bucket=None
    ):
        """
        Uploads preannotation data to a project.

        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :param conf_bucket: Confidence bucket [low, medium, high]
        :return: The response from the API.
        :raises LabellerrError: If the upload fails.
        """
        try:
            # validate all the parameters
            required_params = [
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
            url = f"{constants.BASE_URL}/actions/upload_answers?project_id={self.project_id}&answer_format={annotation_format}&client_id={self.client.client_id}&uuid={request_uuid}"
            if conf_bucket:
                assert conf_bucket in [
                    "low",
                    "medium",
                    "high",
                ], "Invalid confidence bucket value. Must be one of [low, medium, high]"
                url += f"&conf_bucket={conf_bucket}"
            # validate if the file exist then extract file name from the path
            if os.path.exists(annotation_file):
                file_name = os.path.basename(annotation_file)
            else:
                raise LabellerrError("File not found")

            payload = {}
            with open(annotation_file, "rb") as f:
                files = [("file", (file_name, f, "application/octet-stream"))]
                response = self.client.make_request(
                    "POST",
                    url,
                    extra_headers={"email_id": self.client.api_key},
                    request_id=request_uuid,
                    handle_response=False,
                    data=payload,
                    files=files,
                )
            response_data = self.client.handle_upload_response(response, request_uuid)

            # read job_id from the response
            job_id = response_data["response"]["job_id"]

            logging.info(f"Preannotation job started successfully. Job ID: {job_id}")

            # Use max_retries=10 with 5-second intervals = 50 seconds max (fits within typical test timeouts)
            future = self.preannotation_job_status_async(job_id)
            return future.result()
        except Exception as e:
            logging.error(f"Failed to upload preannotation: {str(e)}")
            raise

    def create_local_export(self, export_config):
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
            project_id=self.project_id,
            client_id=self.client.client_id,
            export_config=export_config,
        )
        # Validate export config using client_utils
        client_utils.validate_export_config(export_config)

        unique_id = client_utils.generate_request_id()
        export_config.update({"export_destination": "local", "question_ids": ["all"]})

        payload = json.dumps(export_config)

        return self.client.make_request(
            "POST",
            f"{constants.BASE_URL}/sdk/export/files?project_id={self.project_id}&client_id={self.client.client_id}",
            extra_headers={
                "Origin": constants.ALLOWED_ORIGINS,
                "Content-Type": "application/json",
            },
            request_id=unique_id,
            data=payload,
        )

    @validate_params(report_ids=list)
    def check_export_status(self, report_ids: List[str]):
        request_uuid = client_utils.generate_request_id()
        try:
            if not report_ids:
                raise LabellerrError("report_ids cannot be empty")

            # Construct URL
            url = f"{constants.BASE_URL}/exports/status?project_id={self.project_id}&uuid={request_uuid}&client_id={self.client.client_id}"

            payload = json.dumps({"report_ids": report_ids})

            result = self.client.make_request(
                "POST",
                url,
                extra_headers={"Content-Type": "application/json"},
                request_id=request_uuid,
                data=payload,
            )

            # Now process each report_id
            for status_item in result.get("status", []):
                if (
                    status_item.get("is_completed")
                    and status_item.get("export_status") == "Created"
                ):
                    # Download URL if job completed
                    download_url = (  # noqa E999 todo check use of that
                        self.__fetch_exports_download_url(
                            project_id=self.project_id,
                            uuid=request_uuid,
                            export_id=status_item["report_id"],
                            client_id=self.client.client_id,
                        )
                    )

            return json.dumps(result, indent=2)

        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to check export status: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error checking export status: {str(e)}")
            raise

    def list_files(self, search_queries, size=10, next_search_after=None):
        # Validate parameters using Pydantic
        params = schemas.ListFileParams(
            client_id=self.client.client_id,
            project_id=self.project_id,
            search_queries=search_queries,
            size=size,
            next_search_after=next_search_after,
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/search/project_files?project_id={params.project_id}&client_id={params.client_id}&uuid={unique_id}"

        payload = json.dumps(
            {
                "search_queries": params.search_queries,
                "size": params.size,
                "next_search_after": params.next_search_after,
            }
        )

        return self.client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )

    def bulk_assign_files(self, file_ids, new_status, assign_to=None):
        # Validate parameters using Pydantic
        params = schemas.BulkAssignFilesParams(
            client_id=self.client.client_id,
            project_id=self.project_id,
            file_ids=file_ids,
            new_status=new_status,
            assign_to=assign_to,
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/actions/files/bulk_assign?project_id={params.project_id}&uuid={unique_id}&client_id={params.client_id}"

        payload = {
            "file_ids": params.file_ids,
            "new_status": params.new_status,
        }
        if assign_to:
            payload["assign_to"] = assign_to

        return self.client.make_request(
            "POST",
            url,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=json.dumps(payload),
        )

    def __fetch_exports_download_url(self, project_id, uuid, export_id, client_id):
        try:
            url = f"{constants.BASE_URL}/exports/download?project_id={project_id}&uuid={uuid}&report_id={export_id}&client_id={client_id}"
            response = self.client.make_request(
                "GET",
                url,
                client_id=client_id,
                extra_headers={"Content-Type": "application/json"},
                request_id=uuid,
            )
            return response.get("response")
        except Exception as e:
            raise LabellerrError(f"Failed to download export: {str(e)}")
