
"""This module will contain all CRUD for datasets. Example, create, list datasets, get dataset, delete dataset, update dataset, etc.
"""
from abc import ABCMeta, abstractmethod
from ..client import LabellerrClient
from .. import constants, client_utils
from ..exceptions import InvalidDatasetError
import uuid

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

    
