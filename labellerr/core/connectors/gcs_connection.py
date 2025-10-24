import uuid

from labellerr import LabellerrClient

from .. import client_utils, constants
from .connections import LabellerrConnection, LabellerrConnectionMeta


class GCSConnection(LabellerrConnection):

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


LabellerrConnectionMeta._register("gcs", GCSConnection)
