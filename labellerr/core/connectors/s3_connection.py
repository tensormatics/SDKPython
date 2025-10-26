import json
import uuid
from typing import TYPE_CHECKING

from ... import schemas
from .. import client_utils, constants
from .connections import LabellerrConnection, LabellerrConnectionMeta

if TYPE_CHECKING:
    from labellerr import LabellerrClient


class S3Connection(LabellerrConnection):
    @staticmethod
    def setup_full_connection(
        client: "LabellerrClient", connection_config: dict
    ) -> "S3Connection":
        """
        AWS S3 connector and, if valid, save the connection.
        :param client: The LabellerrClient instance
        :param connection_config: Dictionary containing:
            - client_id: The ID of the client
            - aws_access_key: The AWS access key
            - aws_secrets_key: The AWS secrets key
            - s3_path: The S3 path
            - data_type: The data type
            - name: The name of the connection
            - description: The description
            - connection_type: The connection type (default: import)
        :return: Parsed JSON response
        """
        # Validate parameters using Pydantic
        params = schemas.AWSConnectionParams(
            client_id=connection_config["client_id"],
            aws_access_key=connection_config["aws_access_key"],
            aws_secrets_key=connection_config["aws_secrets_key"],
            s3_path=connection_config["s3_path"],
            data_type=connection_config["data_type"],
            name=connection_config["name"],
            description=connection_config["description"],
            connection_type=connection_config.get("connection_type", "import"),
        )

        request_uuid = str(uuid.uuid4())
        test_connection_url = (
            f"{constants.BASE_URL}/connectors/connections/test"
            f"?client_id={params.client_id}&uuid={request_uuid}"
        )

        headers = client_utils.build_headers(
            api_key=client.api_key,
            api_secret=client.api_secret,
            client_id=params.client_id,
            extra_headers={"email_id": client.api_key},
        )

        aws_credentials_json = json.dumps(
            {
                "access_key_id": params.aws_access_key,
                "secret_access_key": params.aws_secrets_key,
            }
        )

        test_request = {
            "credentials": aws_credentials_json,
            "connector": "s3",
            "path": params.s3_path,
            "connection_type": params.connection_type,
            "data_type": params.data_type,
        }

        client_utils.request(
            "POST",
            test_connection_url,
            headers=headers,
            data=test_request,
            request_id=request_uuid,
        )

        create_url = (
            f"{constants.BASE_URL}/connectors/connections/create"
            f"?uuid={request_uuid}&client_id={params.client_id}"
        )

        create_request = {
            "client_id": params.client_id,
            "connector": "s3",
            "name": params.name,
            "description": params.description,
            "connection_type": params.connection_type,
            "data_type": params.data_type,
            "credentials": aws_credentials_json,
        }

        return client_utils.request(
            "POST",
            create_url,
            headers=headers,
            data=create_request,
            request_id=request_uuid,
        )

    def test_connection(self):
        print("Testing S3 connection!")
        return True

    @staticmethod
    def create_connection(
        client: "LabellerrClient", client_id: str, aws_config: dict
    ) -> str:
        """
        Sets up AWS S3 connector for dataset creation (quick connection).

        :param client: The LabellerrClient instance
        :param client_id: Client ID
        :param aws_config: AWS configuration containing bucket_name, folder_path, access_key_id, secret_access_key, region
        :return: Connection ID for AWS connector
        """
        from ... import LabellerrError

        # TODO: gaurav  recheck this for bucket name in connection string
        required_fields = ["bucket_name"]
        for field in required_fields:
            if field not in aws_config:
                raise LabellerrError(f"Required field '{field}' missing in aws_config")

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/connectors/connect/aws?client_id={client_id}&uuid={unique_id}"

        headers = client_utils.build_headers(
            api_key=client.api_key,
            api_secret=client.api_secret,
            client_id=client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps(
            {
                "bucket_name": aws_config["bucket_name"],
                "folder_path": aws_config.get("folder_path", ""),
                "access_key_id": aws_config.get("access_key_id"),
                "secret_access_key": aws_config.get("secret_access_key"),
                "region": aws_config.get("region", "us-east-1"),
            }
        )

        response_data = client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )
        return response_data["response"]["connection_id"]


LabellerrConnectionMeta._register("s3", S3Connection)
