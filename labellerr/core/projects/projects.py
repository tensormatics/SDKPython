"""This module will contain all CRUD for projects. Example, create, list projects, get project, delete project, update project, etc.
"""
from abc import ABCMeta, abstractmethod
from ..client import LabellerrClient
from .. import constants, client_utils
from ..exceptions import InvalidProjectError
import uuid

class LabellerrProjectMeta(ABCMeta):
    # Class-level registry for project types
    _registry = {}
    
    @classmethod
    def register(cls, data_type, project_class):
        """Register a project type handler"""
        cls._registry[data_type] = project_class

    @staticmethod
    def get_project(client: LabellerrClient, project_id: str):
        """Get project from Labellerr API"""
        # ------------------------------- [needs refactoring after we consolidate api_calls into one function ] ---------------------------------
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/projects/{project_id}?client_id={client.client_id}"
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
    def __call__(cls, client, project_id, **kwargs):
        # Only intercept calls to the base LabellerrProject class
        if cls.__name__ != 'LabellerrProject':
            # For subclasses, use normal instantiation
            instance = cls.__new__(cls)
            if isinstance(instance, cls):
                instance.__init__(client, project_id, **kwargs)
            return instance
        project_data = cls.get_project(client, project_id)
        if project_data is None:
            raise InvalidProjectError(f"Project not found: {project_id}")
        data_type = project_data.get('data_type')
        if data_type not in constants.DATA_TYPES:
            raise InvalidProjectError(f"Data type not supported: {data_type}")
        
        project_class = cls._registry.get(data_type)
        if project_class is None:
            raise InvalidProjectError(f"Unknown data type: {data_type}")
        kwargs['project_data'] = project_data
        return project_class(client, project_id, **kwargs)

class LabellerrProject(metaclass=LabellerrProjectMeta):
    """Base class for all Labellerr projects with factory behavior"""
    def __init__(self, client: LabellerrClient, project_id: str, **kwargs):
        self.client = client
        self.project_id = project_id
        self.project_data = kwargs['project_data']
    
    @property
    def data_type(self):
        return self.project_data.get('data_type')
    
    @property
    def attached_datasets(self):
        return self.project_data.get('attached_datasets')

    
