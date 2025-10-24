from ..client import LabellerrClient
from .connections import LabellerrConnection
from .gcs_connection import GCSConnection as LabellerrGCSConnection
from .s3_connection import S3Connection as LabellerrS3Connection

__all__ = ["LabellerrGCSConnection", "LabellerrConnection", "LabellerrS3Connection"]


def create_connection(
    client: "LabellerrClient",
    connector_type: str,
    client_id: str,
    connector_config: dict,
) -> str:
    """
    Sets up cloud connector (GCP/AWS) for dataset creation using factory pattern.

    :param client: LabellerrClient instance
    :param connector_type: Type of connector ('gcp' or 'aws')
    :param client_id: Client ID
    :param connector_config: Configuration dictionary for the connector
    :return: Connection ID for the cloud connector
    """
    import logging

    from ..exceptions import InvalidConnectionError

    try:
        if connector_type == "gcp":
            from .gcs_connection import GCSConnection

            return GCSConnection.create_connection(client, client_id, connector_config)
        elif connector_type == "aws":
            from .s3_connection import S3Connection

            return S3Connection.create_connection(client, client_id, connector_config)
        else:
            raise InvalidConnectionError(
                f"Unsupported connector type: {connector_type}"
            )
    except Exception as e:
        logging.error(f"Failed to setup {connector_type} connector: {e}")
        raise
