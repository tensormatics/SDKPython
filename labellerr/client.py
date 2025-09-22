# labellerr/client.py

import concurrent.futures
import json
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import wraps
from multiprocessing import cpu_count
from typing import List, Optional, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from . import constants, gcs, utils, client_utils
from .exceptions import LabellerrError

# python -m unittest discover -s tests --run
# python setup.py sdist bdist_wheel -- build
create_dataset_parameters = {}


@dataclass
class KeyFrame:
    """
    Represents a key frame with validation.
    """
    frame_number: int
    is_manual: bool = True
    method: str = "manual"
    source: str = "manual"

    def __post_init__(self):
        if not isinstance(self.frame_number, int):
            raise ValueError("frame_number must be an integer")
        if self.frame_number < 0:
            raise ValueError("frame_number must be non-negative")
        if not isinstance(self.is_manual, bool):
            raise ValueError("is_manual must be a boolean")
        if not isinstance(self.method, str):
            raise ValueError("method must be a string")
        if not isinstance(self.source, str):
            raise ValueError("source must be a string")


def validate_params(**validations):
    """
    Decorator to validate method parameters based on type specifications.

    Usage:
    @validate_params(project_id=str, file_id=str, keyFrames=list)
    def some_method(self, project_id, file_id, keyFrames):
        ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature to map args to parameter names
            import inspect
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # Validate each parameter
            for param_name, expected_type in validations.items():
                if param_name in bound.arguments:
                    value = bound.arguments[param_name]
                    if not isinstance(value, expected_type):
                        from .exceptions import LabellerrError
                        type_name = (
                            " or ".join(t.__name__ for t in expected_type)
                            if isinstance(expected_type, tuple)
                            else expected_type.__name__
                        )
                        raise LabellerrError(f"{param_name} must be a {type_name}")

            return func(*args, **kwargs)
        return wrapper
    return decorator


class LabellerrClient:
    """
    A client for interacting with the Labellerr API.
    """

    def __init__(
        self,
        api_key,
        api_secret,
        enable_connection_pooling=True,
        pool_connections=10,
        pool_maxsize=20,
    ):
        """
        Initializes the LabellerrClient with API credentials.

        :param api_key: The API key for authentication.
        :param api_secret: The API secret for authentication.
        :param enable_connection_pooling: Whether to enable connection pooling
        :param pool_connections: Number of connection pools to cache
        :param pool_maxsize: Maximum number of connections to save in the pool
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = constants.BASE_URL
        self._session = None
        self._enable_pooling = enable_connection_pooling
        self._pool_connections = pool_connections
        self._pool_maxsize = pool_maxsize

        if enable_connection_pooling:
            self._setup_session()

    def _setup_session(self):
        """
        Set up requests session with connection pooling for better performance.
        """
        self._session = requests.Session()

        if HTTPAdapter and Retry:
            # Configure retry strategy
            retry_strategy = Retry(
                total=3,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=[
                    "HEAD",
                    "GET",
                    "PUT",
                    "DELETE",
                    "OPTIONS",
                    "TRACE",
                    "POST",
                ],
                backoff_factor=1,
            )

            # Configure connection pooling
            adapter = HTTPAdapter(
                pool_connections=self._pool_connections,
                pool_maxsize=self._pool_maxsize,
                max_retries=retry_strategy,
            )

            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)

    def _make_request(self, method, url, **kwargs):
        """
        Make HTTP request using session if available, otherwise use requests directly.
        """
        # Set default timeout if not provided
        kwargs.setdefault("timeout", (30, 300))  # connect, read

        if self._session:
            return self._session.request(method, url, **kwargs)
        else:
            return requests.request(method, url, **kwargs)

    def close(self):
        """
        Close the session and cleanup resources.
        """
        if self._session:
            self._session.close()
            self._session = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def _build_headers(self, client_id=None, extra_headers=None):
        """
        Builds standard headers for API requests.

        :param client_id: Optional client ID to include in headers
        :param extra_headers: Optional dictionary of additional headers
        :return: Dictionary of headers
        """
        return client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            source="sdk",
            client_id=client_id,
            extra_headers=extra_headers
        )

    def _handle_response(self, response, request_id=None, success_codes=None):
        """
        Standardized response handling with consistent error patterns.

        :param response: requests.Response object
        :param request_id: Optional request tracking ID
        :param success_codes: Optional list of success status codes (default: [200, 201])
        :return: JSON response data for successful requests
        :raises LabellerrError: For non-successful responses
        """
        if success_codes is None:
            success_codes = [200, 201]

        if response.status_code in success_codes:
            try:
                return response.json()
            except ValueError:
                # Handle cases where response is successful but not JSON
                raise LabellerrError(f"Expected JSON response but got: {response.text}")
        elif 400 <= response.status_code < 500:
            try:
                error_data = response.json()
                raise LabellerrError(
                    {"error": error_data, "code": response.status_code}
                )
            except ValueError:
                raise LabellerrError(
                    {"error": response.text, "code": response.status_code}
                )
        else:
            raise LabellerrError(
                {
                    "status": "internal server error",
                    "message": "Please contact support with the request tracking id",
                    "request_id": request_id or str(uuid.uuid4()),
                }
            )

    def _handle_upload_response(self, response, request_id=None):
        """
        Specialized error handling for upload operations that may have different success patterns.

        :param response: requests.Response object
        :param request_id: Optional request tracking ID
        :return: JSON response data for successful requests
        :raises LabellerrError: For non-successful responses
        """
        try:
            response_data = response.json()
        except ValueError:
            raise LabellerrError(f"Failed to parse response: {response.text}")

        if response.status_code not in [200, 201]:
            if response.status_code >= 400 and response.status_code < 500:
                raise LabellerrError(
                    {"error": response_data, "code": response.status_code}
                )
            elif response.status_code >= 500:
                raise LabellerrError(
                    {
                        "status": "internal server error",
                        "message": "Please contact support with the request tracking id",
                        "request_id": request_id or str(uuid.uuid4()),
                        "error": response_data,
                    }
                )
        return response_data

    def _handle_gcs_response(self, response, operation_name="GCS operation"):
        """
        Specialized error handling for Google Cloud Storage operations.

        :param response: requests.Response object
        :param operation_name: Name of the operation for error messages
        :return: True for successful operations
        :raises LabellerrError: For non-successful responses
        """
        expected_codes = [200, 201] if operation_name == "upload" else [200]

        if response.status_code in expected_codes:
            return True
        else:
            raise LabellerrError(
                f"{operation_name} failed: {response.status_code} - {response.text}"
            )

    def get_direct_upload_url(self, file_name, client_id, purpose="pre-annotations"):
        """
        Get the direct upload URL for the given file names.

        :param file_names: The list of file names.
        :param client_id: The ID of the client.
        :return: The response from the API.
        """
        url = f"{constants.BASE_URL}/connectors/direct-upload-url?client_id={client_id}&purpose={purpose}&file_name={file_name}"
        headers = self._build_headers(client_id=client_id)

        response = self._make_request("GET", url, headers=headers)

        try:
            response_data = self._handle_response(response, success_codes=[200])
            return response_data["response"]
        except Exception as e:
            logging.exception(f"Error getting direct upload url: {response.text} {e}")
            raise

    def connect_local_files(self, client_id, file_names, connection_id=None):
        """
        Connects local files to the API.

        :param client_id: The ID of the client.
        :param file_names: The list of file names.
        :return: The response from the API.
        """
        url = f"{constants.BASE_URL}/connectors/connect/local?client_id={client_id}"
        headers = self._build_headers(client_id=client_id)

        body = {"file_names": file_names}
        if connection_id is not None:
            body["temporary_connection_id"] = connection_id

        response = self._make_request("POST", url, headers=headers, json=body)
        return self._handle_response(response)

    def __process_batch(self, client_id, files_list, connection_id=None):
        """
        Processes a batch of files.
        """
        # Prepare files for upload
        files = {}
        for file_path in files_list:
            file_name = os.path.basename(file_path)
            files[file_name] = file_path

        response = self.connect_local_files(
            client_id, list(files.keys()), connection_id
        )
        resumable_upload_links = response["response"]["resumable_upload_links"]
        for file_name in resumable_upload_links.keys():
            gcs.upload_to_gcs_resumable(
                resumable_upload_links[file_name], files[file_name]
            )

        return response

    @validate_params(client_id=str, files_list=(str, list))
    def upload_files(self, client_id: str, files_list: Union[str, List[str]]):
        """
        Uploads files to the API.

        :param client_id: The ID of the client.
        :param files_list: The list of files to upload or a comma-separated string of file paths.
        :return: The response from the API.
        :raises LabellerrError: If the upload fails.
        """
        try:
            # Convert string input to list if necessary
            if isinstance(files_list, str):
                files_list = files_list.split(",")
                files_list = files_list.split(",")
            elif not isinstance(files_list, list):
                raise LabellerrError(
                    "files_list must be either a list or a comma-separated string"
                )

            if len(files_list) == 0:
                raise LabellerrError("No files to upload")

            # Validate files exist
            for file_path in files_list:
                if not os.path.exists(file_path):
                    raise LabellerrError(f"File does not exist: {file_path}")
                if not os.path.isfile(file_path):
                    raise LabellerrError(f"Path is not a file: {file_path}")

            response = self.__process_batch(client_id, files_list)
            connection_id = response["response"]["temporary_connection_id"]
            return connection_id

        except Exception as e:
            logging.error(f"Failed to upload files : {str(e)}")
            raise LabellerrError(f"Failed to upload files : {str(e)}")

    def get_dataset(self, workspace_id, dataset_id):
        """
        Retrieves a dataset from the Labellerr API.

        :param workspace_id: The ID of the workspace.
        :param dataset_id: The ID of the dataset.
        :param project_id: The ID of the project.
        :return: The dataset as JSON.
        """
        url = f"{constants.BASE_URL}/datasets/{dataset_id}?client_id={workspace_id}&uuid={str(uuid.uuid4())}"
        headers = self._build_headers(
            extra_headers={"Origin": constants.ALLOWED_ORIGINS}
        )

        response = self._make_request("GET", url, headers=headers)
        return self._handle_response(response)

    def update_rotation_count(self):
        """
        Updates the rotation count for a project.

        :return: A dictionary indicating the success of the operation.
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/projects/rotations/add?project_id={self.project_id}&client_id={self.client_id}&uuid={unique_id}"

            headers = self._build_headers(
                client_id=self.client_id,
                extra_headers={"content-type": "application/json"},
            )

            payload = json.dumps(self.rotation_config)
            logging.info(f"Update Rotation Count Payload: {payload}")

            response = requests.request("POST", url, headers=headers, data=payload)

            logging.info("Rotation configuration updated successfully.")
            self._handle_response(response, unique_id)

            return {"msg": "project rotation configuration updated"}
        except LabellerrError as e:
            logging.error(f"Project rotation update config failed: {e}")
            raise

    def create_dataset(
        self, dataset_config, files_to_upload=None, folder_to_upload=None
    ):
        """
        Creates an empty dataset.

        :param dataset_config: A dictionary containing the configuration for the dataset.
        :return: A dictionary containing the response status and the ID of the created dataset.
        """

        try:
            # Validate data_type
            if dataset_config.get("data_type") not in constants.DATA_TYPES:
                raise LabellerrError(
                    f"Invalid data_type. Must be one of {constants.DATA_TYPES}"
                )

            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/datasets/create?client_id={dataset_config['client_id']}&uuid={unique_id}"
            headers = self._build_headers(
                client_id=dataset_config["client_id"],
                extra_headers={"content-type": "application/json"},
            )
            if files_to_upload is not None:
                try:
                    connection_id = self.upload_files(
                        client_id=dataset_config["client_id"],
                        files_list=files_to_upload,
                    )
                except Exception as e:
                    raise LabellerrError(f"Failed to upload files to dataset: {str(e)}")

            elif folder_to_upload is not None:
                try:
                    result = self.upload_folder_files_to_dataset(
                        {
                            "client_id": dataset_config["client_id"],
                            "folder_path": folder_to_upload,
                            "data_type": dataset_config["data_type"],
                        }
                    )
                    connection_id = result["connection_id"]
                except Exception as e:
                    raise LabellerrError(
                        f"Failed to upload folder files to dataset: {str(e)}"
                    )
            payload = json.dumps(
                {
                    "dataset_name": dataset_config["dataset_name"],
                    "dataset_description": dataset_config.get(
                        "dataset_description", ""
                    ),
                    "data_type": dataset_config["data_type"],
                    "connection_id": connection_id,
                    "path": "local",
                    "client_id": dataset_config["client_id"],
                }
            )
            response = requests.request("POST", url, headers=headers, data=payload)
            response_data = self._handle_response(response, unique_id)
            dataset_id = response_data["response"]["dataset_id"]

            return {"response": "success", "dataset_id": dataset_id}

        except LabellerrError as e:
            logging.error(f"Failed to create dataset: {e}")
            raise

    @validate_params(client_id=str, datatype=str, project_id=str, scope=str)
    def get_all_dataset(self, client_id: str, datatype: str, project_id: str, scope: str):
        """
        Retrieves a dataset by its ID.

        :param client_id: The ID of the client.
        :param datatype: The type of data for the dataset.
        :param project_id: The ID of the project.
        :param scope: The scope of the dataset.
        :return: The dataset as JSON.
        """
        # scope value should be in the list SCOPE_LIST
        if scope not in constants.SCOPE_LIST:
            raise LabellerrError(
                f"scope must be one of {', '.join(constants.SCOPE_LIST)}"
            )

        # get dataset
        try:
            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/datasets/list?client_id={client_id}&data_type={datatype}&permission_level={scope}&project_id={project_id}&uuid={unique_id}"
            headers = self._build_headers(
                client_id=client_id, extra_headers={"content-type": "application/json"}
            )

            response = requests.request("GET", url, headers=headers)
            return self._handle_response(response, unique_id)
        except LabellerrError as e:
            logging.error(f"Failed to retrieve dataset: {e}")
            raise

    def get_total_folder_file_count_and_total_size(self, folder_path, data_type):
        """
        Retrieves the total count and size of files in a folder using memory-efficient iteration.

        :param folder_path: The path to the folder.
        :param data_type: The type of data for the files.
        :return: The total count and size of the files.
        """
        total_file_count = 0
        total_file_size = 0
        files_list = []

        # Use os.scandir for better performance and memory efficiency
        def scan_directory(directory):
            nonlocal total_file_count, total_file_size
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if entry.is_file():
                            file_path = entry.path
                            # Check if the file extension matches based on datatype
                            if not any(
                                file_path.endswith(ext)
                                for ext in constants.DATA_TYPE_FILE_EXT[data_type]
                            ):
                                continue
                            try:
                                file_size = entry.stat().st_size
                                files_list.append(file_path)
                                total_file_count += 1
                                total_file_size += file_size
                            except OSError as e:
                                logging.error(f"Error reading {file_path}: {str(e)}")
                        elif entry.is_dir():
                            # Recursively scan subdirectories
                            scan_directory(entry.path)
            except OSError as e:
                logging.error(f"Error scanning directory {directory}: {str(e)}")

        scan_directory(folder_path)
        return total_file_count, total_file_size, files_list

    def get_total_file_count_and_total_size(self, files_list, data_type):
        """
        Retrieves the total count and size of files in a list.

        :param files_list: The list of file paths.
        :param data_type: The type of data for the files.
        :return: The total count and size of the files.
        """
        total_file_count = 0
        total_file_size = 0
        # for root, dirs, files in os.walk(folder_path):
        for file_path in files_list:
            if file_path is None:
                continue
            try:
                # check if the file extention matching based on datatype
                if not any(
                    file_path.endswith(ext)
                    for ext in constants.DATA_TYPE_FILE_EXT[data_type]
                ):
                    continue
                file_size = os.path.getsize(file_path)
                total_file_count += 1
                total_file_size += file_size
            except OSError as e:
                logging.error(f"Error reading {file_path}: {str(e)}")
            except Exception as e:
                logging.error(f"Unexpected error reading {file_path}: {str(e)}")

        return total_file_count, total_file_size, files_list

    def get_all_project_per_client_id(self, client_id):
        """
        Retrieves a list of projects associated with a client ID.

        :param client_id: The ID of the client.
        :return: A dictionary containing the list of projects.
        :raises LabellerrError: If the retrieval fails.
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/project_drafts/projects/detailed_list?client_id={client_id}&uuid={unique_id}"

            headers = self._build_headers(
                client_id=client_id, extra_headers={"content-type": "application/json"}
            )

            response = requests.request("GET", url, headers=headers, data={})
            return self._handle_response(response, unique_id)
        except Exception as e:
            logging.error(f"Failed to retrieve projects: {str(e)}")
            raise LabellerrError(f"Failed to retrieve projects: {str(e)}")

    def create_annotation_guideline(
        self, client_id, questions, template_name, data_type
    ):
        """
        Updates the annotation guideline for a project.

        :param config: A dictionary containing the project ID, data type, client ID, autolabel status, and the annotation guideline.
        :return: None
        :raises LabellerrError: If the update fails.
        """
        unique_id = str(uuid.uuid4())

        url = f"{constants.BASE_URL}/annotations/create_template?data_type={data_type}&client_id={client_id}&uuid={unique_id}"

        guide_payload = json.dumps(
            {"templateName": template_name, "questions": questions}
        )

        headers = self._build_headers(
            client_id=client_id, extra_headers={"content-type": "application/json"}
        )

        try:
            response = requests.request(
                "POST", url, headers=headers, data=guide_payload
            )
            response_data = self._handle_response(response, unique_id)
            return response_data["response"]["template_id"]
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to update project annotation guideline: {str(e)}")
            raise LabellerrError(
                f"Failed to update project annotation guideline: {str(e)}"
            )

    def validate_rotation_config(self, rotation_config):
        """
        Validates a rotation configuration.

        :param rotation_config: A dictionary containing the configuration for the rotations.
        :raises LabellerrError: If the configuration is invalid.
        """
        client_utils.validate_rotation_config(rotation_config)

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
            client_utils.validate_required_params(required_params, list(required_params.keys()))
            client_utils.validate_annotation_format(annotation_format, annotation_file)

            url = f"{self.base_url}/actions/upload_answers?project_id={project_id}&answer_format={annotation_format}&client_id={client_id}"
            file_name = client_utils.validate_file_exists(annotation_file)
            # get the direct upload url
            gcs_path = f"{project_id}/{annotation_format}-{file_name}"
            logging.info("Uploading your file to Labellerr. Please wait...")
            direct_upload_url = self.get_direct_upload_url(gcs_path, client_id)
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
            headers = self._build_headers(
                client_id=client_id, extra_headers={"email_id": self.api_key}
            )
            response = requests.request("POST", url, headers=headers, data=payload)
            response_data = self._handle_upload_response(response)

            # read job_id from the response
            job_id = response_data["response"]["job_id"]
            self.client_id = client_id
            self.job_id = job_id
            self.project_id = project_id

            logging.info(f"Preannotation upload successful. Job ID: {job_id}")
            return self.preannotation_job_status()
        except Exception as e:
            logging.error(f"Failed to upload preannotation: {str(e)}")
            raise LabellerrError(f"Failed to upload preannotation: {str(e)}")

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

                url = f"{self.base_url}/actions/upload_answers?project_id={project_id}&answer_format={annotation_format}&client_id={client_id}"

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
                direct_upload_url = self.get_direct_upload_url(gcs_path, client_id)
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
                headers = self._build_headers(
                    client_id=client_id, extra_headers={"email_id": self.api_key}
                )
                response = requests.request("POST", url, headers=headers, data=payload)
                response_data = self._handle_upload_response(response)

                # read job_id from the response
                job_id = response_data["response"]["job_id"]
                self.client_id = client_id
                self.job_id = job_id
                self.project_id = project_id

                logging.info(f"Preannotation upload successful. Job ID: {job_id}")

                # Now monitor the status
                headers = self._build_headers(
                    client_id=self.client_id,
                    extra_headers={"Origin": constants.ALLOWED_ORIGINS},
                )
                status_url = f"{self.base_url}/actions/upload_answers_status?project_id={self.project_id}&job_id={self.job_id}&client_id={self.client_id}"
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
                        raise LabellerrError(
                            f"Failed to get preannotation job status: {str(e)}"
                        )

            except Exception as e:
                logging.exception(f"Failed to upload preannotation: {str(e)}")
                raise LabellerrError(f"Failed to upload preannotation: {str(e)}")

        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(upload_and_monitor)

    def preannotation_job_status_async(self):
        """
        Get the status of a preannotation job asynchronously.

        Returns:
            concurrent.futures.Future: A future that will contain the final job status
        """

        def check_status():
            headers = self._build_headers(
                client_id=self.client_id,
                extra_headers={"Origin": constants.ALLOWED_ORIGINS},
            )
            url = f"{self.base_url}/actions/upload_answers_status?project_id={self.project_id}&job_id={self.job_id}&client_id={self.client_id}"
            payload = {}
            while True:
                try:
                    response = requests.request(
                        "GET", url, headers=headers, data=payload
                    )
                    response_data = response.json()

                    # Check if job is completed
                    if response_data.get("response", {}).get("status") == "completed":
                        return response_data

                    logging.info("retrying after 5 seconds . . .")
                    time.sleep(5)

                except Exception as e:
                    logging.error(f"Failed to get preannotation job status: {str(e)}")
                    raise LabellerrError(
                        f"Failed to get preannotation job status: {str(e)}"
                    )

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

            url = f"{self.base_url}/actions/upload_answers?project_id={project_id}&answer_format={annotation_format}&client_id={client_id}"

            # validate if the file exist then extract file name from the path
            if os.path.exists(annotation_file):
                file_name = os.path.basename(annotation_file)
            else:
                raise LabellerrError("File not found")

            payload = {}
            with open(annotation_file, "rb") as f:
                files = [("file", (file_name, f, "application/octet-stream"))]
                headers = self._build_headers(
                    client_id=client_id, extra_headers={"email_id": self.api_key}
                )
                response = requests.request(
                    "POST", url, headers=headers, data=payload, files=files
                )
            response_data = self._handle_upload_response(response)
            logging.debug(f"response_data: {response_data}")

            # read job_id from the response
            job_id = response_data["response"]["job_id"]
            self.client_id = client_id
            self.job_id = job_id
            self.project_id = project_id

            logging.info(f"Preannotation upload successful. Job ID: {job_id}")

            future = self.preannotation_job_status_async()
            return future.result()
        except Exception as e:
            logging.error(f"Failed to upload preannotation: {str(e)}")
            raise LabellerrError(f"Failed to upload preannotation: {str(e)}")

    def create_local_export(self, project_id, client_id, export_config):
        unique_id = client_utils.generate_request_id()

        if project_id is None:
            raise LabellerrError("project_id cannot be null")

        if client_id is None:
            raise LabellerrError("client_id cannot be null")

        if export_config is None:
            raise LabellerrError("export_config cannot be null")

        client_utils.validate_export_config(export_config)

        try:
            export_config.update(
                {"export_destination": "local", "question_ids": ["all"]}
            )
            payload = json.dumps(export_config)
            headers = self._build_headers(
                extra_headers={
                    "Origin": constants.ALLOWED_ORIGINS,
                    "Content-Type": "application/json",
                }
            )

            response = requests.post(
                f"{self.base_url}/sdk/export/files?project_id={project_id}&client_id={client_id}",
                headers=headers,
                data=payload,
            )

            return self._handle_response(response, unique_id)
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to create local export: {str(e)}")
            raise LabellerrError(f"Failed to create local export: {str(e)}")

    def fetch_download_url(
        self, project_id, uuid, export_id, client_id
    ):
        try:
            headers = self._build_headers(
                client_id=client_id, extra_headers={"Content-Type": "application/json"}
            )

            response = requests.get(
                url=f"{constants.BASE_URL}/exports/download",
                params={
                    "client_id": client_id,
                    "project_id": project_id,
                    "uuid": uuid,
                    "report_id": export_id,
                },
                headers=headers,
            )

            if response.ok:
                return json.dumps(response.json().get("response"), indent=2)
            else:
                raise LabellerrError(
                    f" Download request failed: {response.status_code} - {response.text}"
                )
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to download export: {str(e)}")
            raise LabellerrError(f"Failed to download export: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error in download_function: {str(e)}")
            raise LabellerrError(f"Unexpected error in download_function: {str(e)}")

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
            headers = self._build_headers(
                client_id=client_id, extra_headers={"Content-Type": "application/json"}
            )

            payload = json.dumps({"report_ids": report_ids})

            response = requests.post(url, headers=headers, data=payload)
            result = self._handle_response(response, request_uuid)

            # Now process each report_id
            for status_item in result.get("status", []):
                if (
                    status_item.get("is_completed")
                    and status_item.get("export_status") == "Created"
                ):
                    # Download URL if job completed
                    download_url = (  # noqa E999 todo check use of that
                        self.fetch_download_url(
                            project_id=project_id,
                            uuid=request_uuid,
                            export_id=status_item["report_id"],
                            client_id=client_id,
                        )
                    )

            return json.dumps(result, indent=2)

        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to check export status: {str(e)}")
            raise LabellerrError(f"Failed to check export status: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error checking export status: {str(e)}")
            raise LabellerrError(f"Unexpected error checking export status: {str(e)}")

    def create_project(
        self,
        project_name,
        data_type,
        client_id,
        dataset_id,
        annotation_template_id,
        rotation_config,
        created_by=None,
    ):
        """
        Creates a project with the given configuration.
        """
        url = f"{constants.BASE_URL}/projects/create?client_id={client_id}"

        payload = json.dumps(
            {
                "project_name": project_name,
                "attached_datasets": [dataset_id],
                "data_type": data_type,
                "annotation_template_id": annotation_template_id,
                "rotations": rotation_config,
                "created_by": created_by,
            }
        )

        headers = self._build_headers(
            extra_headers={
                "Origin": constants.ALLOWED_ORIGINS,
                "Content-Type": "application/json",
            }
        )

        # print(f"{payload}")

        response = requests.post(url, headers=headers, data=payload)
        response_data = response.json()

        # print(f"{response_data}")

        if "error" in response_data and response_data["error"]:
            error_details = response_data["error"]
            error_msg = (
                f"Validation Error: {response_data.get('message', 'Unknown error')}"
            )
            for error in error_details:
                error_msg += f"\n- Field '{error['field']}': {error['message']}"
            raise LabellerrError(error_msg)

        return response_data

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
                "annotation_guide",
                "autolabel",
            ]
            for param in required_params:
                if param not in payload:
                    raise LabellerrError(f"Required parameter {param} is missing")

                if param == "client_id" and not isinstance(payload[param], str):
                    raise LabellerrError("client_id must be a non-empty string")

                if param == "annotation_guide":
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
                    dataset_status = self.get_dataset(payload["client_id"], dataset_id)

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

            annotation_template_id = self.create_annotation_guideline(
                payload["client_id"],
                payload["annotation_guide"],
                payload["project_name"],
                payload["data_type"],
            )
            logging.info("Annotation guidelines created")

            project_response = self.create_project(
                project_name=payload["project_name"],
                data_type=payload["data_type"],
                client_id=payload["client_id"],
                dataset_id=dataset_id,
                annotation_template_id=annotation_template_id,
                rotation_config=payload["rotation_config"],
                created_by=payload["created_by"],
            )

            return {
                "status": "success",
                "message": "Project created successfully",
                "project_id": project_response,
            }

        except LabellerrError as e:
            logging.error(f"Project creation failed: {str(e)}")
            raise
        except Exception as e:
            logging.exception("Unexpected error in project creation")
            raise LabellerrError(f"Project creation failed: {str(e)}") from e

    def upload_folder_files_to_dataset(self, data_config):
        """
        Uploads local files from a folder to a dataset using parallel processing.

        :param data_config: A dictionary containing the configuration for the data.
        :return: A dictionary containing the response status and the list of successfully uploaded files.
        :raises LabellerrError: If there are issues with file limits, permissions, or upload process
        """
        try:
            # Validate required fields in data_config
            required_fields = ["client_id", "folder_path", "data_type"]
            missing_fields = [
                field for field in required_fields if field not in data_config
            ]
            if missing_fields:
                raise LabellerrError(
                    f"Missing required fields in data_config: {', '.join(missing_fields)}"
                )

            # Validate folder path exists and is accessible
            if not os.path.exists(data_config["folder_path"]):
                raise LabellerrError(
                    f"Folder path does not exist: {data_config['folder_path']}"
                )
            if not os.path.isdir(data_config["folder_path"]):
                raise LabellerrError(
                    f"Path is not a directory: {data_config['folder_path']}"
                )
            if not os.access(data_config["folder_path"], os.R_OK):
                raise LabellerrError(
                    f"No read permission for folder: {data_config['folder_path']}"
                )

            success_queue = []
            fail_queue = []

            try:
                # Get files from folder
                total_file_count, total_file_volumn, filenames = (
                    self.get_total_folder_file_count_and_total_size(
                        data_config["folder_path"], data_config["data_type"]
                    )
                )
            except Exception as e:
                raise LabellerrError(f"Failed to analyze folder contents: {str(e)}")

            # Check file limits
            if total_file_count > constants.TOTAL_FILES_COUNT_LIMIT_PER_DATASET:
                raise LabellerrError(
                    f"Total file count: {total_file_count} exceeds limit of {constants.TOTAL_FILES_COUNT_LIMIT_PER_DATASET} files"
                )
            if total_file_volumn > constants.TOTAL_FILES_SIZE_LIMIT_PER_DATASET:
                raise LabellerrError(
                    f"Total file size: {total_file_volumn/1024/1024:.1f}MB exceeds limit of {constants.TOTAL_FILES_SIZE_LIMIT_PER_DATASET/1024/1024:.1f}MB"
                )

            logging.info(f"Total file count: {total_file_count}")
            logging.info(f"Total file size: {total_file_volumn/1024/1024:.1f} MB")

            # Use generator for memory-efficient batch creation
            def create_batches():
                current_batch = []
                current_batch_size = 0

                for file_path in filenames:
                    try:
                        file_size = os.path.getsize(file_path)
                        if (
                            current_batch_size + file_size > constants.FILE_BATCH_SIZE
                            or len(current_batch) >= constants.FILE_BATCH_COUNT
                        ):
                            if current_batch:
                                yield current_batch
                            current_batch = [file_path]
                            current_batch_size = file_size
                        else:
                            current_batch.append(file_path)
                            current_batch_size += file_size
                    except OSError as e:
                        logging.error(f"Error accessing file {file_path}: {str(e)}")
                        fail_queue.append(file_path)
                    except Exception as e:
                        logging.error(
                            f"Unexpected error processing {file_path}: {str(e)}"
                        )
                        fail_queue.append(file_path)

                if current_batch:
                    yield current_batch

            # Convert generator to list for ThreadPoolExecutor
            batches = list(create_batches())

            if not batches:
                raise LabellerrError(
                    "No valid files found to upload in the specified folder"
                )

            logging.info(f"CPU count: {cpu_count()}, Batch Count: {len(batches)}")

            # Calculate optimal number of workers based on CPU count and batch count
            max_workers = min(
                cpu_count(),  # Number of CPU cores
                len(batches),  # Number of batches
                20,
            )
            connection_id = str(uuid.uuid4())
            # Process batches in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_batch = {
                    executor.submit(
                        self.__process_batch,
                        data_config["client_id"],
                        batch,
                        connection_id,
                    ): batch
                    for batch in batches
                }

                for future in as_completed(future_to_batch):
                    batch = future_to_batch[future]
                    try:
                        result = future.result()
                        if (
                            isinstance(result, dict)
                            and result.get("message") == "200: Success"
                        ):
                            success_queue.extend(batch)
                        else:
                            fail_queue.extend(batch)
                    except Exception as e:
                        logging.exception(e)
                        logging.error(f"Batch upload failed: {str(e)}")
                        fail_queue.extend(batch)

            if not success_queue and fail_queue:
                raise LabellerrError(
                    "All file uploads failed. Check individual file errors above."
                )

            return {
                "connection_id": connection_id,
                "success": success_queue,
                "fail": fail_queue,
            }

        except LabellerrError as e:
            raise e
        except Exception as e:
            raise LabellerrError(f"Failed to upload files: {str(e)}")


    @validate_params(client_id=str, project_id=str, file_id=str, key_frames=list)
    def link_key_frame(self, client_id: str, project_id: str, file_id: str, key_frames: List[KeyFrame]):
        """
        Links key frames to a file in a project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param file_id: The ID of the file
        :param key_frames: List of KeyFrame objects to link
        :return: Response from the API
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/actions/add_update_keyframes?client_id={client_id}&uuid={unique_id}"
            headers = self._build_headers(
                client_id=client_id,
                extra_headers={"content-type": "application/json"}
            )

            body = {
                "project_id": project_id,
                "file_id": file_id,
                "keyframes": [
                    kf.__dict__ if isinstance(kf, KeyFrame) else kf
                    for kf in key_frames
                ]
            }

            response = self._make_request("POST", url, headers=headers, json=body)
            return self._handle_response(response, unique_id)

        except LabellerrError as e:
            raise e
        except Exception as e:
            raise LabellerrError(f"Failed to link key frames: {str(e)}")

    @validate_params(client_id=str, project_id=str)
    def delete_key_frames(self, client_id: str, project_id: str):
        """
        Deletes key frames from a project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :return: Response from the API
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/actions/delete_keyframes?project_id={project_id}&uuid={unique_id}&client_id={client_id}"
            headers = self._build_headers(
                client_id=client_id,
                extra_headers={"content-type": "application/json"}
            )

            response = self._make_request("POST", url, headers=headers)
            return self._handle_response(response, unique_id)

        except LabellerrError as e:
            raise e
        except Exception as e:
            raise LabellerrError(f"Failed to delete key frames: {str(e)}")
