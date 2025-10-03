# labellerr/client.py

import concurrent.futures
import json
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
from typing import Any, Dict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import client_utils, constants, gcs, utils
from .exceptions import LabellerrError
from .validators import (
    handle_api_errors,
    log_method_call,
    validate_client_id,
    validate_data_type,
    validate_dataset_ids,
    validate_file_list_or_string,
    validate_list_not_empty,
    validate_not_none,
    validate_questions_structure,
    validate_required,
    validate_rotations_structure,
    validate_scope,
    validate_string_type,
    validate_uuid_format,
)

create_dataset_parameters: Dict[str, Any] = {}


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

        if HTTPAdapter is not None and Retry is not None:
            # Configure retry strategy
            retry_kwargs = {
                "total": 3,
                "status_forcelist": [429, 500, 502, 503, 504],
                "backoff_factor": 1,
            }

            methods = [
                "HEAD",
                "GET",
                "PUT",
                "DELETE",
                "OPTIONS",
                "TRACE",
                "POST",
            ]

            try:
                # Prefer modern param if available
                retry_strategy = Retry(allowed_methods=methods, **retry_kwargs)
            except TypeError:
                # Fallback for older urllib3
                retry_strategy = Retry(**retry_kwargs)

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
            extra_headers=extra_headers,
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

    @validate_required(
        [
            "client_id",
            "aws_access_key",
            "aws_secrets_key",
            "s3_path",
            "data_type",
            "name",
        ]
    )
    def create_aws_connection(
        self,
        client_id: str,
        aws_access_key: str,
        aws_secrets_key: str,
        s3_path: str,
        data_type: str,
        name: str,
        description: str,
        connection_type: str = "import",
    ):
        """
        AWS S3 connector and, if valid, save the connection.
        :param client_id: The ID of the client.
        :param aws_access_key: The AWS access key.
        :param aws_secrets_key: The AWS secrets key.
        :param s3_path: The S3 path.
        :param data_type: The data type.
        :param name: The name of the connection.
        :param description: The description.
        :param connection_type: The connection type.

        """

        request_uuid = str(uuid.uuid4())
        test_connection_url = (
            f"{constants.BASE_URL}/connectors/connections/test"
            f"?client_id={client_id}&uuid={request_uuid}"
        )

        headers = self._build_headers(
            client_id=client_id,
            extra_headers={"email_id": self.api_key},
        )

        aws_credentials_json = json.dumps(
            {
                "access_key_id": aws_access_key,
                "secret_access_key": aws_secrets_key,
            }
        )

        test_request = {
            "credentials": aws_credentials_json,
            "connector": "aws",
            "path": s3_path,
            "connection_type": connection_type,
            "data_type": data_type,
        }

        test_resp = self._make_request(
            "POST", test_connection_url, headers=headers, data=test_request
        )
        self._handle_response(test_resp, request_uuid)

        create_url = (
            f"{constants.BASE_URL}/connectors/connections/create"
            f"?uuid={request_uuid}&client_id={client_id}"
        )

        create_request = {
            "client_id": client_id,
            "connector": "aws",
            "name": name,
            "description": description,
            "connection_type": connection_type,
            "data_type": data_type,
            "credentials": aws_credentials_json,
        }

        create_resp = self._make_request(
            "POST", create_url, headers=headers, data=create_request
        )

        return self._handle_response(create_resp, request_uuid)

    @validate_required(["client_id", "gcs_path", "data_type", "name"])
    def create_gcs_connection(
        self,
        client_id: str,
        gcs_cred_file: str,
        gcs_path: str,
        data_type: str,
        name: str,
        description: str,
        connection_type: str = "import",
        credentials: str = "svc_account_json",
    ):
        """
        Create/test a GCS connector connection (multipart/form-data)
        :param client_id: The ID of the client.
        :param gcs_cred_file: Path to the GCS service account JSON file.
        :param gcs_path: GCS path like gs://bucket/path
        :param data_type: Data type, e.g. "image", "video".
        :param name: Name of the connection
        :param description: Description of the connection
        :param connection_type: "import" or "export" (default: import)
        :param credentials: Credential type (default: svc_account_json)
        :return: Parsed JSON response
        """
        if not os.path.exists(gcs_cred_file):
            raise LabellerrError(f"GCS credential file not found: {gcs_cred_file}")

        request_uuid = str(uuid.uuid4())
        test_url = (
            f"{constants.BASE_URL}/connectors/connections/test"
            f"?client_id={client_id}&uuid={request_uuid}"
        )

        headers = self._build_headers(
            client_id=client_id,
            extra_headers={"email_id": self.api_key},
        )

        test_request = {
            "credentials": credentials,
            "connector": "gcs",
            "path": gcs_path,
            "connection_type": connection_type,
            "data_type": data_type,
        }

        with open(gcs_cred_file, "rb") as fp:
            test_files = {
                "attachment_files": (
                    os.path.basename(gcs_cred_file),
                    fp,
                    "application/json",
                )
            }
            test_resp = self._make_request(
                "POST", test_url, headers=headers, data=test_request, files=test_files
            )
        self._handle_response(test_resp, request_uuid)

        # If test passed, create/save the connection
        # use same uuid to track request
        create_url = (
            f"{constants.BASE_URL}/connectors/connections/create"
            f"?uuid={request_uuid}&client_id={client_id}"
        )

        create_request = {
            "client_id": client_id,
            "connector": "gcs",
            "name": name,
            "description": description,
            "connection_type": connection_type,
            "data_type": data_type,
            "credentials": credentials,
        }

        with open(gcs_cred_file, "rb") as fp:
            create_files = {
                "attachment_files": (
                    os.path.basename(gcs_cred_file),
                    fp,
                    "application/json",
                )
            }
            create_resp = self._make_request(
                "POST",
                create_url,
                headers=headers,
                data=create_request,
                files=create_files,
            )

        return self._handle_response(create_resp, request_uuid)

    def list_connection(self, client_id: str, connection_type: str):
        request_uuid = str(uuid.uuid4())
        list_connection_url = (
            f"{constants.BASE_URL}/connectors/connections/list"
            f"?client_id={client_id}&uuid={request_uuid}&connection_type={connection_type}"
        )

        headers = self._build_headers(
            client_id=client_id,
            extra_headers={"email_id": self.api_key},
        )

        list_connection_response = self._make_request(
            "GET", list_connection_url, headers=headers
        )

        return self._handle_response(list_connection_response, request_uuid)

    @validate_required(["client_id", "connection_id"])
    def delete_connection(self, client_id: str, connection_id: str):
        """
        Deletes a connector connection by ID.

        :param client_id: The ID of the client.
        :param connection_id: The ID of the connection to delete.
        :return: Parsed JSON response
        """
        request_uuid = str(uuid.uuid4())
        delete_url = (
            f"{constants.BASE_URL}/connectors/connections/delete"
            f"?client_id={client_id}&uuid={request_uuid}"
        )

        headers = self._build_headers(
            client_id=client_id,
            extra_headers={
                "content-type": "application/json",
                "email_id": self.api_key,
            },
        )

        payload = json.dumps({"connection_id": connection_id})

        delete_response = self._make_request(
            "POST", delete_url, headers=headers, data=payload
        )
        return self._handle_response(delete_response, request_uuid)

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

    # TODO: explore https://docs.pydantic.dev/latest/api/base_model/#pydantic.BaseModel and migrate these
    # Decorator for api error
    @validate_required(["client_id", "files_list"])
    @validate_client_id("client_id")
    @validate_file_list_or_string(["files_list"])
    @log_method_call(include_params=False)
    @handle_api_errors
    def upload_files(self, client_id, files_list):
        """
        Uploads files to the API.

        :param client_id: The ID of the client.
        :param files_list: The list of files to upload or a comma-separated string of file paths.
        :return: The connection ID from the API.
        :raises LabellerrError: If the upload fails.
        """
        response = self.__process_batch(client_id, files_list)
        connection_id = response["response"]["temporary_connection_id"]
        return connection_id

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
        self,
        dataset_config,
        files_to_upload=None,
        folder_to_upload=None,
        connector_config=None,
    ):
        """
        Creates a dataset with support for multiple data types and connectors.

        :param dataset_config: A dictionary containing the configuration for the dataset.
                              Required fields: client_id, dataset_name, data_type
                              Optional fields: dataset_description, connector_type
        :param files_to_upload: List of file paths to upload (for local connector)
        :param folder_to_upload: Path to folder to upload (for local connector)
        :param connector_config: Configuration for cloud connectors (GCP/AWS)
        :return: A dictionary containing the response status and the ID of the created dataset.
        """

        try:
            # Validate required fields
            required_fields = ["client_id", "dataset_name", "data_type"]
            for field in required_fields:
                if field not in dataset_config:
                    raise LabellerrError(
                        f"Required field '{field}' missing in dataset_config"
                    )

            # Validate data_type
            if dataset_config.get("data_type") not in constants.DATA_TYPES:
                raise LabellerrError(
                    f"Invalid data_type. Must be one of {constants.DATA_TYPES}"
                )

            connector_type = dataset_config.get("connector_type", "local")
            connection_id = None
            path = connector_type

            # Handle different connector types
            if connector_type == "local":
                if files_to_upload is not None:
                    try:
                        connection_id = self.upload_files(
                            client_id=dataset_config["client_id"],
                            files_list=files_to_upload,
                        )
                    except Exception as e:
                        raise LabellerrError(
                            f"Failed to upload files to dataset: {str(e)}"
                        )

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
                elif connector_config is None:
                    # Create empty dataset for local connector
                    connection_id = None

            elif connector_type in ["gcp", "aws"]:
                if connector_config is None:
                    raise LabellerrError(
                        f"connector_config is required for {connector_type} connector"
                    )

                try:
                    connection_id = self._setup_cloud_connector(
                        connector_type, dataset_config["client_id"], connector_config
                    )
                except Exception as e:
                    raise LabellerrError(
                        f"Failed to setup {connector_type} connector: {str(e)}"
                    )
            else:
                raise LabellerrError(f"Unsupported connector type: {connector_type}")

            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/datasets/create?client_id={dataset_config['client_id']}&uuid={unique_id}"
            headers = self._build_headers(
                client_id=dataset_config["client_id"],
                extra_headers={"content-type": "application/json"},
            )

            payload = json.dumps(
                {
                    "dataset_name": dataset_config["dataset_name"],
                    "dataset_description": dataset_config.get(
                        "dataset_description", ""
                    ),
                    "data_type": dataset_config["data_type"],
                    "connection_id": connection_id,
                    "path": path,
                    "client_id": dataset_config["client_id"],
                    "connector_type": connector_type,
                }
            )
            response = self._make_request("POST", url, headers=headers, data=payload)
            response_data = self._handle_response(response, unique_id)
            dataset_id = response_data["response"]["dataset_id"]

            return {"response": "success", "dataset_id": dataset_id}

        except LabellerrError as e:
            logging.error(f"Failed to create dataset: {e}")
            raise

    @validate_required(["client_id", "dataset_id"])
    @validate_client_id("client_id")
    @validate_uuid_format("dataset_id")
    @log_method_call(include_params=False)
    @handle_api_errors
    def delete_dataset(self, client_id, dataset_id):
        """
        Deletes a dataset from the system.

        :param client_id: The ID of the client
        :param dataset_id: The ID of the dataset to delete
        :return: Dictionary containing deletion status
        :raises LabellerrError: If the deletion fails
        """
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/datasets/{dataset_id}/delete?client_id={client_id}&uuid={unique_id}"
        headers = self._build_headers(
            client_id=client_id, extra_headers={"content-type": "application/json"}
        )

        response = self._make_request("DELETE", url, headers=headers)
        return self._handle_response(response, unique_id)

    @validate_required(["client_id", "dataset_id", "indexing_config"])
    @validate_client_id("client_id")
    @validate_uuid_format("dataset_id")
    @log_method_call(include_params=False)
    @handle_api_errors
    def enable_multimodal_indexing(self, client_id, dataset_id, indexing_config):
        """
        Enables multimodal indexing for an existing dataset.

        :param client_id: The ID of the client
        :param dataset_id: The ID of the dataset
        :param indexing_config: Configuration for multimodal indexing
                               Example: {"enabled": True, "modalities": ["text", "image"]}
        :return: Dictionary containing indexing status
        :raises LabellerrError: If the operation fails
        """
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/datasets/{dataset_id}/indexing?client_id={client_id}&uuid={unique_id}"
        headers = self._build_headers(
            client_id=client_id, extra_headers={"content-type": "application/json"}
        )

        payload = json.dumps(indexing_config)
        response = self._make_request("POST", url, headers=headers, data=payload)
        return self._handle_response(response, unique_id)

    @validate_required(["client_id", "project_id", "dataset_id"])
    @validate_client_id("client_id")
    @validate_uuid_format("project_id")
    @validate_uuid_format("dataset_id")
    @log_method_call(include_params=False)
    @handle_api_errors
    def attach_dataset_to_project(self, client_id, project_id, dataset_id):
        """
        Attaches a dataset to an existing project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param dataset_id: The ID of the dataset to attach
        :return: Dictionary containing attachment status
        :raises LabellerrError: If the operation fails
        """
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/projects/{project_id}/datasets/attach?client_id={client_id}&uuid={unique_id}"
        headers = self._build_headers(
            client_id=client_id, extra_headers={"content-type": "application/json"}
        )

        payload = json.dumps({"dataset_id": dataset_id})
        response = self._make_request("POST", url, headers=headers, data=payload)
        return self._handle_response(response, unique_id)

    @validate_required(["client_id", "project_id", "dataset_id"])
    @validate_client_id("client_id")
    @validate_uuid_format("project_id")
    @validate_uuid_format("dataset_id")
    @log_method_call(include_params=False)
    @handle_api_errors
    def detach_dataset_from_project(self, client_id, project_id, dataset_id):
        """
        Detaches a dataset from an existing project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param dataset_id: The ID of the dataset to detach
        :return: Dictionary containing detachment status
        :raises LabellerrError: If the operation fails
        """
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/projects/{project_id}/datasets/detach?client_id={client_id}&uuid={unique_id}"
        headers = self._build_headers(
            client_id=client_id, extra_headers={"content-type": "application/json"}
        )

        payload = json.dumps({"dataset_id": dataset_id})
        response = self._make_request("POST", url, headers=headers, data=payload)
        return self._handle_response(response, unique_id)

    @validate_required(["client_id", "datatype", "project_id", "scope"])
    @validate_string_type("client_id")
    @validate_string_type("datatype")
    @validate_string_type("project_id")
    @validate_scope("scope")
    @log_method_call(include_params=False)
    @handle_api_errors
    def get_all_dataset(self, client_id, datatype, project_id, scope):
        """
        Retrieves datasets by parameters.

        :param client_id: The ID of the client.
        :param datatype: The type of data for the dataset.
        :param project_id: The ID of the project.
        :param scope: The permission scope for the dataset.
        :return: The dataset list as JSON.
        """
        unique_id = str(uuid.uuid4())
        url = f"{self.base_url}/datasets/list?client_id={client_id}&data_type={datatype}&permission_level={scope}&project_id={project_id}&uuid={unique_id}"
        headers = self._build_headers(
            client_id=client_id, extra_headers={"content-type": "application/json"}
        )

        response = self._make_request("GET", url, headers=headers)
        return self._handle_response(response, unique_id)

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
            client_utils.validate_required_params(
                required_params, list(required_params.keys())
            )
            client_utils.validate_annotation_format(annotation_format, annotation_file)

            request_uuid = str(uuid.uuid4())
            url = f"{self.base_url}/actions/upload_answers?project_id={project_id}&answer_format={annotation_format}&client_id={client_id}&uuid={request_uuid}"
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
            response_data = self._handle_upload_response(response, request_uuid)

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

                request_uuid = str(uuid.uuid4())
                url = (
                    f"{self.base_url}/actions/upload_answers?"
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
                response_data = self._handle_upload_response(response, request_uuid)

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

            request_uuid = str(uuid.uuid4())
            url = f"{self.base_url}/actions/upload_answers?project_id={project_id}&answer_format={annotation_format}&client_id={client_id}&uuid={request_uuid}"

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
            response_data = self._handle_upload_response(response, request_uuid)
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

    @validate_required(["project_id", "client_id", "export_config"])
    @validate_not_none(["project_id", "client_id", "export_config"])
    @validate_string_type("project_id")
    @validate_client_id("client_id")
    @log_method_call(include_params=False)
    @handle_api_errors
    def create_local_export(self, project_id, client_id, export_config):
        """
        Creates a local export with the given configuration.

        :param project_id: The ID of the project.
        :param client_id: The ID of the client.
        :param export_config: Export configuration dictionary.
        :return: The response from the API.
        :raises LabellerrError: If the export creation fails.
        """
        # Validate export config using client_utils
        client_utils.validate_export_config(export_config)

        unique_id = client_utils.generate_request_id()
        export_config.update({"export_destination": "local", "question_ids": ["all"]})

        payload = json.dumps(export_config)
        headers = self._build_headers(
            extra_headers={
                "Origin": constants.ALLOWED_ORIGINS,
                "Content-Type": "application/json",
            }
        )

        response = self._make_request(
            "POST",
            f"{self.base_url}/sdk/export/files?project_id={project_id}&client_id={client_id}",
            headers=headers,
            data=payload,
        )

        return self._handle_response(response, unique_id)

    def fetch_download_url(self, project_id, uuid, export_id, client_id):
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

    def check_export_status(self, project_id, report_ids, client_id):
        request_uuid = client_utils.generate_request_id()
        try:
            if not project_id:
                raise LabellerrError("project_id cannot be null")
            if not report_ids or not isinstance(report_ids, list):
                raise LabellerrError("report_ids must be a non-empty list")

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

    @validate_required(
        [
            "project_name",
            "data_type",
            "client_id",
            "attached_datasets",
            "annotation_template_id",
            "rotations",
        ]
    )
    @validate_client_id("client_id")
    @validate_data_type("data_type")
    @validate_dataset_ids("attached_datasets")
    @validate_uuid_format("annotation_template_id")
    @validate_rotations_structure("rotations")
    @log_method_call(include_params=False)
    @handle_api_errors
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
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/projects/create?client_id={client_id}&uuid={unique_id}"

        payload = json.dumps(
            {
                "project_name": project_name,
                "attached_datasets": attached_datasets,
                "data_type": data_type,
                "annotation_template_id": annotation_template_id,
                "rotations": rotations,
                "use_ai": use_ai,
                "created_by": created_by,
            }
        )

        headers = self._build_headers(
            client_id=client_id,
            extra_headers={
                "Origin": constants.ALLOWED_ORIGINS,
                "Content-Type": "application/json",
            },
        )

        response = self._make_request("POST", url, headers=headers, data=payload)
        return self._handle_response(response, unique_id)

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

            if payload.get("annotation_template_id"):
                annotation_template_id = payload["annotation_template_id"]
            else:
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

    @validate_required(["client_id", "data_type", "template_name", "questions"])
    @validate_client_id("client_id")
    @validate_data_type("data_type")
    @validate_list_not_empty("questions")
    @validate_questions_structure()
    @log_method_call(include_params=False)
    @handle_api_errors
    def create_template(self, client_id, data_type, template_name, questions):
        """
        Creates an annotation template with the given configuration.

        :param client_id: The ID of the client.
        :param data_type: The type of data for the template (image, video, etc.).
        :param template_name: The name of the template.
        :param questions: List of questions/annotations for the template.
        :return: The response from the API containing template details.
        :raises LabellerrError: If the creation fails.
        """
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/annotations/create_template?client_id={client_id}&data_type={data_type}&uuid={unique_id}"

        headers = self._build_headers(
            client_id=client_id, extra_headers={"content-type": "application/json"}
        )

        payload = json.dumps({"templateName": template_name, "questions": questions})

        response = self._make_request("POST", url, headers=headers, data=payload)
        return self._handle_response(response, unique_id)

    @validate_required(
        ["client_id", "first_name", "last_name", "email_id", "projects", "roles"]
    )
    @validate_client_id("client_id")
    @validate_string_type("first_name")
    @validate_string_type("last_name")
    @validate_string_type("email_id")
    @validate_list_not_empty("projects")
    @validate_list_not_empty("roles")
    @log_method_call(include_params=False)
    @handle_api_errors
    def create_user(
        self,
        client_id,
        first_name,
        last_name,
        email_id,
        projects,
        roles,
        work_phone="",
        job_title="",
        language="en",
        timezone="GMT",
    ):
        """
        Creates a new user in the system.

        :param client_id: The ID of the client
        :param first_name: User's first name
        :param last_name: User's last name
        :param email_id: User's email address
        :param projects: List of project IDs to assign the user to
        :param roles: List of role objects with project_id and role_id
        :param work_phone: User's work phone number (optional)
        :param job_title: User's job title (optional)
        :param language: User's preferred language (default: "en")
        :param timezone: User's timezone (default: "GMT")
        :return: Dictionary containing user creation response
        :raises LabellerrError: If the creation fails
        """
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/register?client_id={client_id}&uuid={unique_id}"

        headers = self._build_headers(
            client_id=client_id,
            extra_headers={
                "content-type": "application/json",
                "accept": "application/json, text/plain, */*",
            },
        )

        payload = json.dumps(
            {
                "first_name": first_name,
                "last_name": last_name,
                "work_phone": work_phone,
                "job_title": job_title,
                "language": language,
                "timezone": timezone,
                "email_id": email_id,
                "projects": projects,
                "client_id": client_id,
                "roles": roles,
            }
        )

        response = self._make_request("POST", url, headers=headers, data=payload)
        return self._handle_response(response, unique_id)

    @validate_required(["client_id", "project_id", "email_id", "roles"])
    @validate_client_id("client_id")
    @validate_string_type("project_id")
    @validate_string_type("email_id")
    @validate_list_not_empty("roles")
    @log_method_call(include_params=False)
    @handle_api_errors
    def update_user_role(
        self,
        client_id,
        project_id,
        email_id,
        roles,
        first_name=None,
        last_name=None,
        work_phone="",
        job_title="",
        language="en",
        timezone="GMT",
        profile_image="",
    ):
        """
        Updates a user's role and profile information.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param email_id: User's email address
        :param roles: List of role objects with project_id and role_id
        :param first_name: User's first name (optional)
        :param last_name: User's last name (optional)
        :param work_phone: User's work phone number (optional)
        :param job_title: User's job title (optional)
        :param language: User's preferred language (default: "en")
        :param timezone: User's timezone (default: "GMT")
        :param profile_image: User's profile image (optional)
        :return: Dictionary containing update response
        :raises LabellerrError: If the update fails
        """
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/update?project_id={project_id}&uuid={unique_id}"

        headers = self._build_headers(
            client_id=client_id,
            extra_headers={
                "content-type": "application/json",
                "accept": "application/json, text/plain, */*",
            },
        )

        # Build the payload with all provided information
        payload_data = {
            "profile_image": profile_image,
            "work_phone": work_phone,
            "job_title": job_title,
            "language": language,
            "timezone": timezone,
            "email_id": email_id,
            "client_id": client_id,
            "roles": roles,
        }

        # Add optional fields if provided
        if first_name is not None:
            payload_data["first_name"] = first_name
        if last_name is not None:
            payload_data["last_name"] = last_name

        payload = json.dumps(payload_data)

        response = self._make_request("POST", url, headers=headers, data=payload)
        return self._handle_response(response, unique_id)

    @validate_required(["client_id", "project_id", "email_id", "user_id"])
    @validate_client_id("client_id")
    @validate_string_type("project_id")
    @validate_string_type("email_id")
    @validate_string_type("user_id")
    @log_method_call(include_params=False)
    @handle_api_errors
    def delete_user(
        self,
        client_id,
        project_id,
        email_id,
        user_id,
        first_name=None,
        last_name=None,
        is_active=1,
        role="Annotator",
        user_created_at=None,
        max_activity_created_at=None,
        image_url="",
        name=None,
        activity="No Activity",
        creation_date=None,
        status="Activated",
    ):
        """
        Deletes a user from the system.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param email_id: User's email address
        :param user_id: User's unique identifier
        :param first_name: User's first name (optional)
        :param last_name: User's last name (optional)
        :param is_active: User's active status (default: 1)
        :param role: User's role (default: "Annotator")
        :param user_created_at: User creation timestamp (optional)
        :param max_activity_created_at: Max activity timestamp (optional)
        :param image_url: User's profile image URL (optional)
        :param name: User's display name (optional)
        :param activity: User's activity status (default: "No Activity")
        :param creation_date: User creation date (optional)
        :param status: User's status (default: "Activated")
        :return: Dictionary containing deletion response
        :raises LabellerrError: If the deletion fails
        """
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/delete?client_id={client_id}&project_id={project_id}&uuid={unique_id}"

        headers = self._build_headers(
            client_id=client_id,
            extra_headers={
                "content-type": "application/json",
                "accept": "application/json, text/plain, */*",
            },
        )

        # Build the payload with all provided information
        payload_data = {
            "email_id": email_id,
            "is_active": is_active,
            "role": role,
            "user_id": user_id,
            "imageUrl": image_url,
            "email": email_id,
            "activity": activity,
            "status": status,
        }

        # Add optional fields if provided
        if first_name is not None:
            payload_data["first_name"] = first_name
        if last_name is not None:
            payload_data["last_name"] = last_name
        if user_created_at is not None:
            payload_data["user_created_at"] = user_created_at
        if max_activity_created_at is not None:
            payload_data["max_activity_created_at"] = max_activity_created_at
        if name is not None:
            payload_data["name"] = name
        if creation_date is not None:
            payload_data["creationDate"] = creation_date

        payload = json.dumps(payload_data)

        response = self._make_request("POST", url, headers=headers, data=payload)
        return self._handle_response(response, unique_id)

    @validate_required(["client_id", "project_id", "email_id"])
    @validate_client_id("client_id")
    @validate_string_type("project_id")
    @validate_string_type("email_id")
    @log_method_call(include_params=False)
    @handle_api_errors
    def add_user_to_project(self, client_id, project_id, email_id, role_id=None):
        """
        Adds a user to a project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param email_id: User's email address
        :param role_id: Optional role ID to assign to the user
        :return: Dictionary containing addition response
        :raises LabellerrError: If the addition fails
        """
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/annotations/add_user_to_project?client_id={client_id}&project_id={project_id}&uuid={unique_id}"

        headers = self._build_headers(
            client_id=client_id, extra_headers={"content-type": "application/json"}
        )

        payload_data = {"email_id": email_id, "uuid": unique_id}

        if role_id is not None:
            payload_data["role_id"] = role_id

        payload = json.dumps(payload_data)
        response = self._make_request("POST", url, headers=headers, data=payload)
        return self._handle_response(response, unique_id)

    @validate_required(["client_id", "project_id", "email_id"])
    @validate_client_id("client_id")
    @validate_string_type("project_id")
    @validate_string_type("email_id")
    @log_method_call(include_params=False)
    @handle_api_errors
    def remove_user_from_project(self, client_id, project_id, email_id):
        """
        Removes a user from a project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param email_id: User's email address
        :return: Dictionary containing removal response
        :raises LabellerrError: If the removal fails
        """
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/annotations/remove_user_from_project?client_id={client_id}&project_id={project_id}&uuid={unique_id}"

        headers = self._build_headers(
            client_id=client_id, extra_headers={"content-type": "application/json"}
        )

        payload_data = {"email_id": email_id, "uuid": unique_id}

        payload = json.dumps(payload_data)
        response = self._make_request("POST", url, headers=headers, data=payload)
        return self._handle_response(response, unique_id)

    @validate_required(["client_id", "project_id", "email_id", "new_role_id"])
    @validate_client_id("client_id")
    @validate_string_type("project_id")
    @validate_string_type("email_id")
    @validate_string_type("new_role_id")
    @log_method_call(include_params=False)
    @handle_api_errors
    def change_user_role(self, client_id, project_id, email_id, new_role_id):
        """
        Changes a user's role in a project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param email_id: User's email address
        :param new_role_id: The new role ID to assign to the user
        :return: Dictionary containing role change response
        :raises LabellerrError: If the role change fails
        """
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/annotations/change_user_role?client_id={client_id}&project_id={project_id}&uuid={unique_id}"

        headers = self._build_headers(
            client_id=client_id, extra_headers={"content-type": "application/json"}
        )

        payload_data = {
            "email_id": email_id,
            "new_role_id": new_role_id,
            "uuid": unique_id,
        }

        payload = json.dumps(payload_data)
        response = self._make_request("POST", url, headers=headers, data=payload)
        return self._handle_response(response, unique_id)

    @validate_required(["client_id", "project_id", "search_queries"])
    @validate_client_id("client_id")
    @validate_string_type("project_id")
    @log_method_call(include_params=False)
    @handle_api_errors
    def list_file(
        self, client_id, project_id, search_queries, size=10, next_search_after=None
    ):

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/search/project_files?project_id={project_id}&client_id={client_id}&uuid={unique_id}"

        headers = self._build_headers(
            client_id=client_id, extra_headers={"content-type": "application/json"}
        )

        payload = json.dumps(
            {
                "search_queries": search_queries,
                "size": size,
                "next_search_after": next_search_after,
            }
        )

        response = self._make_request("POST", url, headers=headers, data=payload)
        return self._handle_response(response, unique_id)

    @validate_required(["client_id", "project_id", "file_ids", "new_status"])
    @validate_client_id("client_id")
    @validate_string_type("project_id")
    @validate_list_not_empty("file_ids")
    @log_method_call(include_params=False)
    @handle_api_errors
    def bulk_assign_files(self, client_id, project_id, file_ids, new_status):
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/actions/files/bulk_assign?project_id={project_id}&uuid={unique_id}&client_id={client_id}"

        headers = self._build_headers(
            client_id=client_id, extra_headers={"content-type": "application/json"}
        )

        payload = json.dumps(
            {
                "file_ids": file_ids,
                "new_status": new_status,
            }
        )

        response = self._make_request("POST", url, headers=headers, data=payload)
        return self._handle_response(response, unique_id)
