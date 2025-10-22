"""This module will contain all CRUD for datasets. Example, create, list datasets, get dataset, delete dataset, update dataset, etc."""

import json
import logging
import os
import uuid
from abc import ABCMeta, abstractmethod
from asyncio import as_completed
from concurrent.futures import ThreadPoolExecutor

from ... import schemas
from .. import client_utils, constants
from ..client import LabellerrClient
from ..exceptions import InvalidDatasetError, LabellerrError
from ..utils import validate_params


class LabellerrDatasetMeta(ABCMeta):
    # Class-level registry for dataset types
    _registry = {}

    @classmethod
    def register(cls, data_type, dataset_class):
        """Register a dataset type handler"""
        cls._registry[data_type] = dataset_class

    @staticmethod
    def get_dataset(client: LabellerrClient, dataset_id: str):
        """Get dataset from Labellerr API"""
        # ------------------------------- [needs refactoring after we consolidate api_calls into one function ] ---------------------------------
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/datasets/{dataset_id}?client_id={client.client_id}"
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

    def __call__(cls, client, dataset_id, **kwargs):
        # Only intercept calls to the base LabellerrFile class
        if cls.__name__ != "LabellerrDataset":
            # For subclasses, use normal instantiation
            instance = cls.__new__(cls)
            if isinstance(instance, cls):
                instance.__init__(client, dataset_id, **kwargs)
            return instance
        dataset_data = cls.get_dataset(client, dataset_id)
        if dataset_data is None:
            raise InvalidDatasetError(f"Dataset not found: {dataset_id}")
        data_type = dataset_data.get("data_type")
        if data_type not in constants.DATA_TYPES:
            raise InvalidDatasetError(f"Data type not supported: {data_type}")

        dataset_class = cls._registry.get(data_type)
        if dataset_class is None:
            raise InvalidDatasetError(f"Unknown data type: {data_type}")
        kwargs["dataset_data"] = dataset_data
        return dataset_class(client, dataset_id, **kwargs)


class LabellerrDataset(metaclass=LabellerrDatasetMeta):
    """Base class for all Labellerr files with factory behavior"""

    def __init__(self, client: LabellerrClient, dataset_id: str, **kwargs):
        self.client = client
        self.dataset_id = dataset_id
        self.dataset_data = kwargs["dataset_data"]

    @property
    def data_type(self):
        return self.dataset_data.get("data_type")

    @abstractmethod
    def fetch_files(self):
        """Each file type must implement its own download logic"""
        pass

    def attach_dataset_to_project(
        self, client_id, project_id, dataset_id=None, dataset_ids=None
    ):
        """
        Attaches one or more datasets to an existing project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
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
                client_id=client_id, project_id=project_id, dataset_id=ds_id
            )
            validated_dataset_ids.append(str(params.dataset_id))

        # Use the first params validation for client_id and project_id
        params = schemas.AttachDatasetParams(
            client_id=client_id, project_id=project_id, dataset_id=dataset_ids[0]
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/actions/jobs/add_datasets_to_project?project_id={params.project_id}&uuid={unique_id}&client_id={params.client_id}"
        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps({"attached_datasets": validated_dataset_ids})

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    def detach_dataset_from_project(
        self, client_id, project_id, dataset_id=None, dataset_ids=None
    ):
        """
        Detaches one or more datasets from an existing project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
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
                client_id=client_id, project_id=project_id, dataset_id=ds_id
            )
            validated_dataset_ids.append(str(params.dataset_id))

        # Use the first params validation for client_id and project_id
        params = schemas.DetachDatasetParams(
            client_id=client_id, project_id=project_id, dataset_id=dataset_ids[0]
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/actions/jobs/delete_datasets_from_project?project_id={params.project_id}&uuid={unique_id}"
        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps({"attached_datasets": validated_dataset_ids})

        return client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )

    @validate_params(client_id=str, datatype=str, project_id=str, scope=str)
    def get_all_datasets(
        self, client_id: str, datatype: str, project_id: str, scope: str
    ):
        """
        Retrieves datasets by parameters.

        :param client_id: The ID of the client.
        :param datatype: The type of data for the dataset.
        :param project_id: The ID of the project.
        :param scope: The permission scope for the dataset.
        :return: The dataset list as JSON.
        """
        # Validate parameters using Pydantic
        params = schemas.GetAllDatasetParams(
            client_id=client_id,
            datatype=datatype,
            project_id=project_id,
            scope=scope,
        )
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/datasets/list?client_id={params.client_id}&data_type={params.datatype}&permission_level={params.scope}"
            f"&project_id={params.project_id}&uuid={unique_id}"
        )
        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        return client_utils.request("GET", url, headers=headers, request_id=unique_id)

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
                        connection_id = self.client.upload_files(
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
                    connection_id = self.client._setup_cloud_connector(
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
            headers = client_utils.build_headers(
                api_key=self.api_key,
                api_secret=self.api_secret,
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
            response_data = client_utils.request(
                "POST", url, headers=headers, data=payload, request_id=unique_id
            )
            dataset_id = response_data["response"]["dataset_id"]

            return {"response": "success", "dataset_id": dataset_id}

        except LabellerrError as e:
            logging.error(f"Failed to create dataset: {e}")
            raise

    def delete_dataset(self, client_id, dataset_id):
        """
        Deletes a dataset from the system.

        :param client_id: The ID of the client
        :param dataset_id: The ID of the dataset to delete
        :return: Dictionary containing deletion status
        :raises LabellerrError: If the deletion fails
        """
        # Validate parameters using Pydantic
        params = schemas.DeleteDatasetParams(client_id=client_id, dataset_id=dataset_id)
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/datasets/{params.dataset_id}/delete?client_id={params.client_id}&uuid={unique_id}"
        headers = client_utils.build_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
        )

        return client_utils.request(
            "DELETE", url, headers=headers, request_id=unique_id
        )

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
                    self.client.get_total_folder_file_count_and_total_size(
                        data_config["folder_path"], data_config["data_type"]
                    )
                )
            except Exception as e:
                logging.error(f"Failed to analyze folder contents: {str(e)}")
                raise

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

            logging.info(f"CPU count: {os.cpu_count()}, Batch Count: {len(batches)}")

            # Calculate optimal number of workers based on CPU count and batch count
            max_workers = min(
                os.cpu_count(),  # Number of CPU cores
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

        except LabellerrError:
            raise
        except Exception as e:
            logging.error(f"Failed to upload files: {str(e)}")
            raise
