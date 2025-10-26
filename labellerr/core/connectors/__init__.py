from typing import TYPE_CHECKING

from .connections import LabellerrConnection
from .gcs_connection import GCSConnection as LabellerrGCSConnection
from .s3_connection import S3Connection as LabellerrS3Connection

if TYPE_CHECKING:
    from ..client import LabellerrClient

__all__ = ["LabellerrGCSConnection", "LabellerrConnection", "LabellerrS3Connection"]


def create_connection(
    client: "LabellerrClient",
    connector_type: str,
    client_id: str,
    connector_config: dict,
):
    """
    Sets up cloud connector (GCP/AWS) for dataset creation using factory pattern.

    :param client: LabellerrClient instance
    :param connector_type: Type of connector ('gcp' or 'aws')
    :param client_id: Client ID
    :param connector_config: Configuration dictionary for the connector
    :return: Connection ID (str) for quick connection or full response (dict) for full connection
    """
    import logging

    from ..exceptions import InvalidConnectionError

    try:
        if connector_type == "gcp":
            from .gcs_connection import GCSConnection

            return GCSConnection.create_connection(client, client_id, connector_config)
        elif connector_type == "aws":
            from .s3_connection import S3Connection

            # Determine which method to call based on config parameters
            # Full connection has: aws_access_key, aws_secrets_key, s3_path, name, description
            # Quick connection has: bucket_name, folder_path, access_key_id, secret_access_key
            if "aws_access_key" in connector_config and "name" in connector_config:
                # Full connection flow - creates a saved connection
                return S3Connection.setup_full_connection(client, connector_config)
            else:
                # Quick connection flow - for dataset creation
                return S3Connection.create_connection(
                    client, client_id, connector_config
                )
        else:
            raise InvalidConnectionError(
                f"Unsupported connector type: {connector_type}"
            )
    except Exception as e:
        logging.error(f"Failed to setup {connector_type} connector: {e}")
        raise
