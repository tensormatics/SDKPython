import os
import uuid

from ... import schemas
from .. import client_utils, constants
from .connections import LabellerrConnection, LabellerrConnectionMeta


class GCSConnection(LabellerrConnection):
    @staticmethod
    def setup_full_connection(
        client: "LabellerrClient", connection_config: dict
    ) -> "GCSConnection":
        """
        Create/test a GCS connector connection (multipart/form-data)
        :param client_id: The ID of the client.
        :param gcs_cred_file: Path to the GCS service account JSON file.
        :param gcs_path: GCS path like gs://bucket/path
        :param data_type: Data type, e.g. "image", "video".
        :param name: Name of the connection
        :param description: Description of the connection
        :param connection_type: "import" or "export" (default: import)
        :param credentials: Credential type (default: svc_account_json)
        :return: Parsed JSON response
        """
        # Validate parameters using Pydantic
        params = schemas.GCSConnectionParams(
            client_id=connection_config["client_id"],
            gcs_cred_file=connection_config["gcs_cred_file"],
            gcs_path=connection_config["gcs_path"],
            data_type=connection_config["data_type"],
            name=connection_config["name"],
            description=connection_config["description"],
            connection_type=connection_config["connection_type"],
            credentials=connection_config["credentials"],
        )

        request_uuid = str(uuid.uuid4())
        test_url = (
            f"{constants.BASE_URL}/connectors/connections/test"
            f"?client_id={params.client_id}&uuid={request_uuid}"
        )

        headers = client_utils.build_headers(
            api_key=connection_config["api_key"],
            api_secret=connection_config["api_secret"],
            client_id=params.client_id,
            extra_headers={"email_id": connection_config["api_key"]},
        )

        test_request = {
            "credentials": params.credentials,
            "connector": "gcs",
            "path": params.gcs_path,
            "connection_type": params.connection_type,
            "data_type": params.data_type,
        }

        with open(params.gcs_cred_file, "rb") as fp:
            test_files = {
                "attachment_files": (
                    os.path.basename(params.gcs_cred_file),
                    fp,
                    "application/json",
                )
            }
            client_utils.request(
                "POST",
                test_url,
                headers=headers,
                data=test_request,
                files=test_files,
                request_id=request_uuid,
            )

        # If test passed, create/save the connection
        # use same uuid to track request
        create_url = (
            f"{constants.BASE_URL}/connectors/connections/create"
            f"?uuid={request_uuid}&client_id={params.client_id}"
        )

        create_request = {
            "client_id": params.client_id,
            "connector": "gcs",
            "name": params.name,
            "description": params.description,
            "connection_type": params.connection_type,
            "data_type": params.data_type,
            "credentials": params.credentials,
        }

        with open(params.gcs_cred_file, "rb") as fp:
            create_files = {
                "attachment_files": (
                    os.path.basename(params.gcs_cred_file),
                    fp,
                    "application/json",
                )
            }
            return client_utils.request(
                "POST",
                create_url,
                headers=headers,
                data=create_request,
                files=create_files,
                request_id=request_uuid,
            )

    def test_connection(self):
        print("Testing GCS connection!")
        return True

    @staticmethod
    def create_connection(
        client: "LabellerrClient", client_id: str, gcp_config: dict
    ) -> str:
        """
        Sets up GCP connector for dataset creation (quick connection).

        :param client: The LabellerrClient instance
        :param client_id: Client ID
        :param gcp_config: GCP configuration containing bucket_name, folder_path, service_account_key
        :return: Connection ID for GCP connector
        """
        import json

        from ... import LabellerrError

        required_fields = ["bucket_name"]
        for field in required_fields:
            if field not in gcp_config:
                raise LabellerrError(f"Required field '{field}' missing in gcp_config")

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/connectors/connect/gcp?client_id={client_id}&uuid={unique_id}"

        headers = client_utils.build_headers(
            api_key=client.api_key,
            api_secret=client.api_secret,
            client_id=client_id,
            extra_headers={"content-type": "application/json"},
        )

        payload = json.dumps(
            {
                "bucket_name": gcp_config["bucket_name"],
                "folder_path": gcp_config.get("folder_path", ""),
                "service_account_key": gcp_config.get("service_account_key"),
            }
        )

        response_data = client_utils.request(
            "POST", url, headers=headers, data=payload, request_id=unique_id
        )
        return response_data["response"]["connection_id"]


LabellerrConnectionMeta.register("gcs", GCSConnection)
