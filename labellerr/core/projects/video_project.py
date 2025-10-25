import uuid
from typing import TYPE_CHECKING, List

from .. import constants
from ..exceptions import LabellerrError
from ..utils import validate_params
from .base import LabellerrProject

if TYPE_CHECKING:
    from ..client import KeyFrame, LabellerrClient


class VideoProject(LabellerrProject):
    """
    Class for handling video project operations and fetching multiple datasets.
    """

    @staticmethod
    def create_project(client: "LabellerrClient", payload: dict) -> "VideoProject":
        return VideoProject(
            client=client, connection_id=payload["connection_id"], **payload
        )

    @validate_params(client_id=str, project_id=str, file_id=str, key_frames=list)
    def link_key_frame(
        self,
        client_id: str,
        project_id: str,
        file_id: str,
        key_frames: List["KeyFrame"],
    ):
        """
        Links key frames to a file in a project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param file_id: The ID of the file
        :param key_frames: List of KeyFrame objects to link
        :return: Response from the API
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/actions/add_update_keyframes?client_id={client_id}&uuid={unique_id}"

            body = {
                "project_id": project_id,
                "file_id": file_id,
                "keyframes": [
                    (kf.model_dump() if hasattr(kf, "model_dump") else kf)
                    for kf in key_frames
                ],
            }

            return self.client.make_request(
                "POST",
                url,
                client_id=client_id,
                extra_headers={"content-type": "application/json"},
                request_id=unique_id,
                json=body,
            )

        except LabellerrError as e:
            raise e
        except Exception as e:
            raise LabellerrError(f"Failed to link key frames: {str(e)}")

    @validate_params(client_id=str, project_id=str)
    def delete_key_frames(self, client_id: str, project_id: str):
        """
        Deletes key frames from a project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :return: Response from the API
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/actions/delete_keyframes?project_id={project_id}&uuid={unique_id}&client_id={client_id}"

            return self.client.make_request(
                "POST",
                url,
                client_id=client_id,
                extra_headers={"content-type": "application/json"},
                request_id=unique_id,
            )

        except LabellerrError as e:
            raise e
        except Exception as e:
            raise LabellerrError(f"Failed to delete key frames: {str(e)}")
