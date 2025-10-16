
"""This module will contain all CRUD for datasets. Example, create, list datasets, get dataset, delete dataset, update dataset, etc.
"""
from abc import ABCMeta, abstractmethod
from ..client import LabellerrClient
from .. import constants, client_utils
from ..exceptions import InvalidDatasetError
import uuid
from ..exceptions import LabellerrError
import json
import logging

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

        response = client_utils.request("GET", url, headers=headers, request_id=unique_id)
        return response.get('response', None)
        # ------------------------------- [needs refactoring after we consolidate api_calls into one function ] ---------------------------------
    
    """Metaclass that combines ABC functionality with factory pattern"""
    def __call__(cls, client, dataset_id, **kwargs):
        # Only intercept calls to the base LabellerrFile class
        if cls.__name__ != 'LabellerrDataset':
            # For subclasses, use normal instantiation
            instance = cls.__new__(cls)
            if isinstance(instance, cls):
                instance.__init__(client, dataset_id, **kwargs)
            return instance
        dataset_data = cls.get_dataset(client, dataset_id)
        if dataset_data is None:
            raise InvalidDatasetError(f"Dataset not found: {dataset_id}")
        data_type = dataset_data.get('data_type')
        if data_type not in constants.DATA_TYPES:
            raise InvalidDatasetError(f"Data type not supported: {data_type}")
        
        dataset_class = cls._registry.get(data_type)
        if dataset_class is None:
            raise InvalidDatasetError(f"Unknown data type: {data_type}")
        kwargs['dataset_data'] = dataset_data
        return dataset_class(client, dataset_id, **kwargs)

class LabellerrDataset(metaclass=LabellerrDatasetMeta):
    """Base class for all Labellerr files with factory behavior"""
    def __init__(self, client: LabellerrClient, dataset_id: str, **kwargs):
        self.client = client
        self.dataset_id = dataset_id
        self.dataset_data = kwargs['dataset_data']
    
    @property
    def data_type(self):
        return self.dataset_data.get('data_type')
    
    @abstractmethod
    def fetch_files(self):
        """Each file type must implement its own download logic"""
        pass

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
