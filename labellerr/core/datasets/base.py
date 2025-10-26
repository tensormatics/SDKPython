"""This module will contain all CRUD for datasets. Example, create, list datasets, get dataset, delete dataset, update dataset, etc."""

import json
import uuid
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Dict

from ... import schemas
from ...schemas import DataSetScope
from .. import constants
from ..exceptions import InvalidDatasetError
from ..utils import validate_params

if TYPE_CHECKING:
    from ..client import LabellerrClient


class LabellerrDatasetMeta(ABCMeta):
    # Class-level registry for dataset types
    _registry: Dict[str, type] = {}

    @classmethod
    def _register(cls, data_type, dataset_class):
        """Register a dataset type handler"""
        cls._registry[data_type] = dataset_class

    @staticmethod
    def get_dataset(client: "LabellerrClient", dataset_id: str):
        """Get dataset from Labellerr API"""
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/datasets/{dataset_id}?client_id={client.client_id}"
            f"&uuid={unique_id}"
        )

        response = client.make_request(
            "GET",
            url,
            client_id=client.client_id,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
        )
        return response.get("response", None)

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

    def __init__(self, client: "LabellerrClient", dataset_id: str, **kwargs):
        self.client = client
        self.dataset_id = dataset_id
        self.dataset_data = kwargs["dataset_data"]

    @property
    def files_count(self):
        return self.dataset_data.get('files_count', 0)

    @property
    def status_code(self):
        return self.dataset_data.get("status_code", 501)  # if not found, return 501

    @property
    def data_type(self):
        return self.dataset_data.get("data_type")

    @abstractmethod
    def fetch_files(self):
        """Each file type must implement its own download logic"""
        pass

    @validate_params(client_id=str, datatype=str, project_id=str, scope=str)
    def get_all_datasets(
        self, client_id: str, datatype: str, project_id: str, scope: DataSetScope
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

        return self.client.make_request(
            "GET",
            url,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
        )

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

        return self.client.make_request(
            "DELETE",
            url,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
        )

    def sync_datasets(
        self,
        client_id,
        project_id,
        dataset_id,
        path,
        data_type,
        email_id,
        connection_id,
    ):
        """
        Syncs datasets with the backend.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param dataset_id: The ID of the dataset to sync
        :param path: The path to sync
        :param data_type: Type of data (image, video, audio, document, text)
        :param email_id: Email ID of the user
        :param connection_id: The connection ID
        :return: Dictionary containing sync status
        :raises LabellerrError: If the sync fails
        """
        # Validate parameters using Pydantic
        params = schemas.SyncDataSetParams(
            client_id=client_id,
            project_id=project_id,
            dataset_id=dataset_id,
            path=path,
            data_type=data_type,
            email_id=email_id,
            connection_id=connection_id,
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/connectors/datasets/sync?uuid={unique_id}&client_id={params.client_id}"

        payload = json.dumps(
            {
                "client_id": params.client_id,
                "project_id": params.project_id,
                "dataset_id": params.dataset_id,
                "path": params.path,
                "data_type": params.data_type,
                "email_id": params.email_id,
                "connection_id": params.connection_id,
            }
        )

        return self.client.make_request(
            "POST",
            url,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )
