"""This module will contain all CRUD for datasets. Example, create, list datasets, get dataset, delete dataset, update dataset, etc."""

import json
import uuid
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Dict

from ... import schemas
from .. import constants
from ..exceptions import InvalidDatasetError, LabellerrError
from ..utils import validate_params

if TYPE_CHECKING:
    from ..client import LabellerrClient


class LabellerrDatasetMeta(ABCMeta):
    # Class-level registry for dataset types
    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, data_type, dataset_class):
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

        response = client._make_request(
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

        payload = json.dumps({"attached_datasets": validated_dataset_ids})

        return self.client._make_request(
            "POST",
            url,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
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

        payload = json.dumps({"attached_datasets": validated_dataset_ids})

        return self.client._make_request(
            "POST",
            url,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
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

        return self.client._make_request(
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

        return self.client._make_request(
            "DELETE",
            url,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
        )
