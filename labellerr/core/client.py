# labellerr/client.py

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import client_utils, constants, gcs, schemas

# Initialize DataSets handler for dataset-related operations
from .exceptions import LabellerrError

# Initialize Projects handler for project-related operations
# from .projects.base import LabellerrProject
from .utils import validate_params
from .validators import auto_log_and_handle_errors

create_dataset_parameters: Dict[str, Any] = {}


@auto_log_and_handle_errors(
    include_params=False,
    exclude_methods=[
        "close",
        "validate_rotation_config",
        "get_total_folder_file_count_and_total_size",
        "get_total_file_count_and_total_size",
    ],
)
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
        # Validate frame_number
        if not isinstance(self.frame_number, int):
            raise ValueError("frame_number must be an integer")
        if self.frame_number < 0:
            raise ValueError("frame_number must be non-negative")

        # Validate is_manual
        if not isinstance(self.is_manual, bool):
            raise ValueError("is_manual must be a boolean")

        # Validate method
        if not isinstance(self.method, str):
            raise ValueError("method must be a string")

        # Validate source
        if not isinstance(self.source, str):
            raise ValueError("source must be a string")


class LabellerrClient:
    """
    A client for interacting with the Labellerr API.
    """

    def __init__(
        self,
        api_key,
        api_secret,
        client_id,
        enable_connection_pooling=True,
        pool_connections=10,
        pool_maxsize=20,
    ):
        """
        Initializes the LabellerrClient with API credentials.

        :param api_key: The API key for authentication.
        :param api_secret: The API secret for authentication.
        :param client_id: The client ID for the Labellerr account.
        :param enable_connection_pooling: Whether to enable connection pooling
        :param pool_connections: Number of connection pools to cache
        :param pool_maxsize: Maximum number of connections to save in the pool
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.client_id = client_id
        self.base_url = constants.BASE_URL
        self._session = None
        self._enable_pooling = enable_connection_pooling
        self._pool_connections = pool_connections
        self._pool_maxsize = pool_maxsize

        if enable_connection_pooling:
            self._setup_session()

        # self.datasets = DataSets(api_key, api_secret, self)

        # self.projects = LabellerrProject.__new__(LabellerrProject)
        # self.projects.api_key = api_key
        # self.projects.api_secret = api_secret
        # self.projects.client = self

        # Initialize Users handler for user-related operations
        # from .users.base import LabellerrUsers

        # self.users = LabellerrUsers()
        # self.users.api_key = api_key
        # self.users.api_secret = api_secret
        # self.users.client = self

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
            if 400 <= response.status_code < 500:
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

    def _request(self, method, url, **kwargs):
        """
        Wrapper around client_utils.request for backward compatibility.

        :param method: HTTP method
        :param url: Request URL
        :param kwargs: Additional arguments
        :return: Response data
        """
        return client_utils.request(method, url, **kwargs)

    def _make_request(
        self,
        method,
        url,
        client_id=None,
        extra_headers=None,
        request_id=None,
        handle_response=True,
        **kwargs,
    ):
        """
        Make an HTTP request using the configured session or requests library.
        Automatically builds headers and handles response parsing.

        :param method: HTTP method (GET, POST, etc.)
        :param url: Request URL
        :param client_id: Optional client ID for header authentication
        :param extra_headers: Optional extra headers to include
        :param request_id: Optional request tracking ID
        :param handle_response: Whether to parse response (default True)
        :param kwargs: Additional arguments to pass to requests
        :return: Parsed response data if handle_response=True, otherwise Response object
        """
        # Build headers if client_id is provided
        if client_id is not None:
            headers = client_utils.build_headers(
                api_key=self.api_key,
                api_secret=self.api_secret,
                client_id=client_id,
                extra_headers=extra_headers,
            )
            # Merge with any existing headers in kwargs
            if "headers" in kwargs:
                headers.update(kwargs["headers"])
            kwargs["headers"] = headers

        # Make the request
        if self._session:
            response = self._session.request(method, url, **kwargs)
        else:
            response = requests.request(method, url, **kwargs)

        # Handle response if requested
        if handle_response:
            return self._handle_response(response, request_id)
        else:
            return response

    def _handle_response(self, response, request_id=None):
        """
        Handle API response and extract data or raise errors.

        :param response: requests.Response object
        :param request_id: Optional request tracking ID
        :return: Response data
        """
        return client_utils.handle_response(response, request_id)

    def get_direct_upload_url(self, file_name, client_id, purpose="pre-annotations"):
        """
        Get the direct upload URL for the given file names.

        :param file_name: The list of file names.
        :param client_id: The ID of the client.
        :param purpose: The purpose of the URL.
        :return: The response from the API.
        """
        url = f"{constants.BASE_URL}/connectors/direct-upload-url?client_id={client_id}&purpose={purpose}&file_name={file_name}"
        headers = client_utils.build_headers(
            client_id=client_id, api_key=self.api_key, api_secret=self.api_secret
        )

        try:
            response_data = client_utils.request(
                "GET", url, headers=headers, success_codes=[200]
            )
            return response_data["response"]
        except Exception as e:
            logging.exception(f"Error getting direct upload url: {e}")
            raise

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
        :return: Parsed JSON response
        """
        from .connectors.s3_connection import S3Connection

        connection_config = {
            "client_id": client_id,
            "aws_access_key": aws_access_key,
            "aws_secrets_key": aws_secrets_key,
            "s3_path": s3_path,
            "data_type": data_type,
            "name": name,
            "description": description,
            "connection_type": connection_type,
        }

        return S3Connection.setup_full_connection(self, connection_config)

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
        from .connectors.gcs_connection import GCSConnection

        connection_config = {
            "client_id": client_id,
            "gcs_cred_file": gcs_cred_file,
            "gcs_path": gcs_path,
            "data_type": data_type,
            "name": name,
            "description": description,
            "connection_type": connection_type,
            "credentials": credentials,
            "api_key": self.api_key,
            "api_secret": self.api_secret,
        }

        return GCSConnection.setup_full_connection(self, connection_config)

    def list_connection(
        self, client_id: str, connection_type: str, connector: str = None
    ):
        """
        List connections for a client
        :param client_id: The ID of the client
        :param connection_type: Type of connection (import/export)
        :param connector: Optional connector type filter (s3, gcs, etc.)
        :return: List of connections
        """
        from .connectors.connections import LabellerrConnectionMeta

        return LabellerrConnectionMeta.list_connections(
            self, client_id, connection_type, connector
        )

    def delete_connection(self, client_id: str, connection_id: str):
        """
        Deletes a connector connection by ID.

        :param client_id: The ID of the client.
        :param connection_id: The ID of the connection to delete.
        :return: Parsed JSON response
        """
        from .connectors.connections import LabellerrConnectionMeta

        return LabellerrConnectionMeta.delete_connection(self, client_id, connection_id)

    

    def get_dataset(self, workspace_id, dataset_id):
        """
        Retrieves a dataset from the Labellerr API.

        :param workspace_id: The ID of the workspace.
        :param dataset_id: The ID of the dataset.
        :return: The dataset as JSON.
        """
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/datasets/{dataset_id}?client_id={workspace_id}&uuid={unique_id}"

        return self._make_request(
            "GET",
            url,
            client_id=workspace_id,
            extra_headers={"Origin": constants.ALLOWED_ORIGINS},
            request_id=unique_id,
        )

    def enable_multimodal_indexing(self, client_id, dataset_id, is_multimodal=True):
        """
        Enables or disables multimodal indexing for an existing dataset.

        :param client_id: The ID of the client
        :param dataset_id: The ID of the dataset
        :param is_multimodal: Boolean flag to enable (True) or disable (False) multimodal indexing
        :return: Dictionary containing indexing status
        :raises LabellerrError: If the operation fails
        """
        # Validate parameters using Pydantic
        params = schemas.EnableMultimodalIndexingParams(
            client_id=client_id,
            dataset_id=dataset_id,
            is_multimodal=is_multimodal,
        )

        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/search/multimodal_index?client_id={params.client_id}"
        )
        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps(
            {
                "dataset_id": str(params.dataset_id),
                "client_id": params.client_id,
                "is_multimodal": params.is_multimodal,
            }
        )

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    def get_multimodal_indexing_status(self, client_id, dataset_id):
        """
        Retrieves the current multimodal indexing status for a dataset.

        :param client_id: The ID of the client
        :param dataset_id: The ID of the dataset
        :return: Dictionary containing indexing status and configuration
        :raises LabellerrError: If the operation fails
        """
        # Validate parameters using Pydantic
        params = schemas.GetMultimodalIndexingStatusParams(
            client_id=client_id,
            dataset_id=dataset_id,
        )

        url = (
            f"{constants.BASE_URL}/search/multimodal_index?client_id={params.client_id}"
        )
        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps(
            {
                "dataset_id": str(params.dataset_id),
                "client_id": params.client_id,
                "get_status": True,
            }
        )

        result = client_utils.request("POST", url, headers=headers, data=payload)

        # If the response is null or empty, provide a meaningful default status
        if result.get("response") is None:
            result["response"] = {
                "enabled": False,
                "modalities": [],
                "indexing_type": None,
                "status": "not_configured",
                "message": "Multimodal indexing has not been configured for this dataset",
            }

        return result

    def fetch_download_url(self, project_id, uuid, export_id, client_id):
        try:
            url = f"{constants.BASE_URL}/exports/download"
            params = {
                "client_id": client_id,
                "project_id": project_id,
                "uuid": uuid,
                "report_id": export_id,
            }

            response = self._make_request(
                "GET",
                url,
                client_id=client_id,
                extra_headers={"Content-Type": "application/json"},
                request_id=uuid,
                params=params,
            )

            return json.dumps(response.get("response"), indent=2)
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to download export: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error in download_function: {str(e)}")
            raise

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
        # Validate parameters using Pydantic
        params = schemas.CreateTemplateParams(
            client_id=client_id,
            data_type=data_type,
            template_name=template_name,
            questions=questions,
        )
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/annotations/create_template?client_id={params.client_id}&data_type={params.data_type}&uuid={unique_id}"

        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps(
            {
                "templateName": params.template_name,
                "questions": [q.model_dump() for q in params.questions],
            }
        )

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    @validate_params(client_id=str, project_id=str, file_id=str, key_frames=list)
    def link_key_frame(
        self, client_id: str, project_id: str, file_id: str, key_frames: List[KeyFrame]
    ):
        """
        Links key frames to a file in a video project.
        Delegates to VideoProject.link_key_frame().

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param file_id: The ID of the file
        :param key_frames: List of KeyFrame objects to link
        :return: Response from the API
        """
        from .projects.video_project import VideoProject

        # Create a temporary VideoProject instance for delegation
        video_project = VideoProject.__new__(VideoProject)
        video_project.client = self
        video_project.base_url = self.base_url

        return video_project.link_key_frame(client_id, project_id, file_id, key_frames)

    @validate_params(client_id=str, project_id=str)
    def delete_key_frames(self, client_id: str, project_id: str):
        """
        Deletes key frames from a video project.
        Delegates to VideoProject.delete_key_frames().

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :return: Response from the API
        """
        from .projects.video_project import VideoProject

        # Create a temporary VideoProject instance for delegation
        video_project = VideoProject.__new__(VideoProject)
        video_project.client = self
        video_project.base_url = self.base_url

        return video_project.delete_key_frames(client_id, project_id)
