"""This module will contain all CRUD for datasets. Example, create, list datasets, get dataset, delete dataset, update dataset, etc."""

import json
import uuid
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Dict

from ...schemas import DataSetScope
from .. import constants
from ..exceptions import InvalidDatasetError

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
        return self.dataset_data.get("files_count", 0)

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

    @staticmethod
    def get_all_datasets(
        client: "LabellerrClient",
        datatype: str,
        scope: DataSetScope,
        page_size: int = None,
        last_dataset_id: str = None,
    ):
        """
        Retrieves datasets by parameters with pagination support.
        Always returns a generator that yields individual datasets.

        :param client: The client object.
        :param datatype: The type of data for the dataset.
        :param scope: The permission scope for the dataset.
        :param page_size: Number of datasets to return per page (default: 10)
                         Use -1 to auto-paginate through all pages
                         Use specific number to fetch only that many datasets from first page
        :param last_dataset_id: ID of the last dataset from previous page for pagination
                               (only used when page_size is a specific number, ignored for -1)
        :return: Generator yielding individual datasets

        Examples:
            # Auto-paginate through all datasets
            for dataset in get_all_datasets(client, "image", DataSetScope.client, page_size=-1):
                print(dataset)

            # Get first 20 datasets
            datasets = list(get_all_datasets(client, "image", DataSetScope.client, page_size=20))

            # Manual pagination - first page of 10
            gen = get_all_datasets(client, "image", DataSetScope.client, page_size=10)
            first_10 = list(gen)
        """
        # Set default page size if not specified
        if page_size is None:
            page_size = constants.DEFAULT_PAGE_SIZE

        # Auto-pagination mode: yield datasets across all pages
        if page_size == -1:
            actual_page_size = constants.DEFAULT_PAGE_SIZE
            current_last_dataset_id = None
            has_more = True

            while has_more:
                unique_id = str(uuid.uuid4())
                url = (
                    f"{constants.BASE_URL}/datasets/list?client_id={client.client_id}&data_type={datatype}&permission_level={scope}"
                    f"&page_size={actual_page_size}&uuid={unique_id}"
                )

                if current_last_dataset_id:
                    url += f"&last_dataset_id={current_last_dataset_id}"

                response = client.make_request(
                    "GET",
                    url,
                    client_id=client.client_id,
                    extra_headers={"content-type": "application/json"},
                    request_id=unique_id,
                )

                datasets = response.get("datasets", [])
                for dataset in datasets:
                    yield dataset

                # Check if there are more pages
                has_more = response.get("has_more", False)
                current_last_dataset_id = response.get("last_dataset_id")

        else:
            unique_id = str(uuid.uuid4())
            url = (
                f"{constants.BASE_URL}/datasets/list?client_id={client.client_id}&data_type={datatype}&permission_level={scope}"
                f"&page_size={page_size}&uuid={unique_id}"
            )

            # Add last_dataset_id for pagination if provided
            if last_dataset_id:
                url += f"&last_dataset_id={last_dataset_id}"

            response = client.make_request(
                "GET",
                url,
                client_id=client.client_id,
                extra_headers={"content-type": "application/json"},
                request_id=unique_id,
            )

            datasets = response.get("datasets", [])
            for dataset in datasets:
                yield dataset

    def delete_dataset(self, dataset_id):
        """
        Deletes a dataset from the system.

        :param dataset_id: The ID of the dataset to delete
        :return: Dictionary containing deletion status
        :raises LabellerrError: If the deletion fails
        """
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/datasets/{dataset_id}/delete?client_id={self.client.client_id}&uuid={unique_id}"

        return self.client.make_request(
            "DELETE",
            url,
            client_id=self.client.client_id,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
        )

    def sync_datasets(
        self,
        project_id,
        path,
        data_type,
        email_id,
        connection_id,
    ):
        """
        Syncs datasets with the backend.

        :param project_id: The ID of the project
        :param path: The path to sync
        :param data_type: Type of data (image, video, audio, document, text)
        :param email_id: Email ID of the user
        :param connection_id: The connection ID
        :return: Dictionary containing sync status
        :raises LabellerrError: If the sync fails
        """

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/connectors/datasets/sync?uuid={unique_id}&client_id={self.client.client_id}"

        payload = json.dumps(
            {
                "client_id": self.client.client_id,
                "project_id": project_id,
                "dataset_id": self.dataset_id,
                "path": path,
                "data_type": data_type,
                "email_id": email_id,
                "connection_id": connection_id,
            }
        )

        return self.client.make_request(
            "POST",
            url,
            client_id=self.client.client_id,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )

    def enable_multimodal_indexing(self, is_multimodal=True):
        """
        Enables or disables multimodal indexing for an existing dataset.

        :param is_multimodal: Boolean flag to enable (True) or disable (False) multimodal indexing
        :return: Dictionary containing indexing status
        :raises LabellerrError: If the operation fails
        """
        assert is_multimodal is True, "Disabling multimodal indexing is not supported"

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/search/multimodal_index?client_id={self.client.client_id}"

        payload = json.dumps(
            {
                "dataset_id": str(self.dataset_id),
                "client_id": self.client.client_id,
                "is_multimodal": is_multimodal,
            }
        )

        return self.client.make_request(
            "POST",
            url,
            client_id=self.client.client_id,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )
