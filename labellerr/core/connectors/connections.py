"""This module will contain all CRUD for connections. Example, create, list connections, get connection, delete connection, update connection, etc."""

import uuid
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Dict

from .. import client_utils, constants
from ..exceptions import InvalidConnectionError, InvalidDatasetIDError

if TYPE_CHECKING:
    from ..client import LabellerrClient


class LabellerrConnectionMeta(ABCMeta):
    # Class-level registry for connection types
    _registry: Dict[str, type] = {}

    @classmethod
    def _register(cls, connection_type, connection_class):
        """Register a connection type handler"""
        cls._registry[connection_type] = connection_class

    @staticmethod
    def get_connection(client: "LabellerrClient", connection_id: str):
        """Get connection from Labellerr API"""
        # ------------------------------- [needs refactoring after we consolidate api_calls into one function ] ---------------------------------
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/connections/{connection_id}?client_id={client.client_id}"
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

    def __call__(cls, client, connection_id, **kwargs):
        # Only intercept calls to the base LabellerrConnection class
        if cls.__name__ != "LabellerrConnection":
            # For subclasses, use normal instantiation
            instance = cls.__new__(cls)
            if isinstance(instance, cls):
                instance.__init__(client, connection_id, **kwargs)
            return instance
        connection_data = cls.get_connection(client, connection_id)
        if connection_data is None:
            raise InvalidDatasetIDError(f"Connection not found: {connection_id}")
        connection_type = connection_data.get("connection_type")
        if connection_type not in constants.CONNECTION_TYPES:
            raise InvalidConnectionError(
                f"Connection type not supported: {connection_type}"
            )

        connection_class = cls._registry.get(connection_type)
        if connection_class is None:
            raise InvalidConnectionError(f"Unknown connection type: {connection_type}")
        kwargs["connection_data"] = connection_data
        return connection_class(client, connection_id, **kwargs)


class LabellerrConnection(metaclass=LabellerrConnectionMeta):
    """Base class for all Labellerr connections with factory behavior"""

    def __init__(self, client: "LabellerrClient", connection_id: str, **kwargs):
        self.client = client
        self._connection_id_input = connection_id
        self.connection_data = kwargs["connection_data"]

    @property
    def connection_id(self):
        return self.connection_data.get("connection_id")

    @property
    def connection_type(self):
        return self.connection_data.get("connection_type")

    @abstractmethod
    def test_connection(self):
        """Each connection type must implement its own connection testing logic"""
        pass

    def list_connections(
        self,
        connection_type: str,
        connector: str = None,
    ) -> list:
        """
        List connections for a client
        :param connection_type: Type of connection (import/export)
        :param connector: Optional connector type filter (s3, gcs, etc.)
        :return: List of connections
        """
        request_uuid = str(uuid.uuid4())
        list_connection_url = (
            f"{constants.BASE_URL}/connectors/connections/list"
            f"?client_id={self.client.client_id}&uuid={request_uuid}&connection_type={connection_type}"
        )

        if connector:
            list_connection_url += f"&connector={connector}"

        headers = client_utils.build_headers(
            api_key=self.client.api_key,
            api_secret=self.client.api_secret,
            client_id=self.client.client_id,
            extra_headers={"email_id": self.client.api_key},
        )

        return client_utils.request(
            "GET", list_connection_url, headers=headers, request_id=request_uuid
        )

    def delete_connection(self, connection_id: str):
        """
        Deletes a connector connection by ID.
        :param connection_id: The ID of the connection to delete
        :return: Parsed JSON response
        """
        import json

        from ... import schemas

        # Validate parameters using Pydantic
        params = schemas.DeleteConnectionParams(
            client_id=self.client.client_id, connection_id=connection_id
        )
        request_uuid = str(uuid.uuid4())
        delete_url = (
            f"{constants.BASE_URL}/connectors/connections/delete"
            f"?client_id={params.client_id}&uuid={request_uuid}"
        )

        headers = client_utils.build_headers(
            api_key=self.client.api_key,
            api_secret=self.client.api_secret,
            client_id=self.client.client_id,
            extra_headers={
                "content-type": "application/json",
                "email_id": self.client.api_key,
            },
        )

        payload = json.dumps({"connection_id": params.connection_id})

        return client_utils.request(
            "POST", delete_url, headers=headers, data=payload, request_id=request_uuid
        )
