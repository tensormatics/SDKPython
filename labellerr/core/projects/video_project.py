import uuid
from concurrent.futures import Future
from typing import List

from .. import constants
from ..exceptions import LabellerrError
from ..schemas import DatasetDataType, KeyFrame
from ..utils import validate_params
from .base import LabellerrProject, LabellerrProjectMeta


class VideoProject(LabellerrProject):
    """
    Class for handling video project operations and fetching multiple datasets.
    """

    @validate_params(file_id=str, keyframes=list)
    def add_or_update_keyframes(
        self,
        file_id: str,
        keyframes: List[KeyFrame],
    ):
        """
        Links key frames to a file in a project.

        :param file_id: The ID of the file
        :param keyframes: List of KeyFrame objects to link
        :return: Response from the API
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/actions/add_update_keyframes?client_id={self.client.client_id}&uuid={unique_id}"

            body = {
                "project_id": self.project_id,
                "file_id": file_id,
                "keyframes": [
                    (kf.model_dump() if hasattr(kf, "model_dump") else kf)
                    for kf in keyframes
                ],
            }

            return self.client.make_request(
                "POST",
                url,
                extra_headers={"content-type": "application/json"},
                request_id=unique_id,
                json=body,
            )

        except LabellerrError as e:
            raise e
        except Exception as e:
            raise LabellerrError(f"Failed to link key frames: {str(e)}")

    @validate_params(file_id=str, keyframes=list)
    def delete_keyframes(self, file_id: str, keyframes: List[int]):
        """
        Deletes key frames from a project.

        :param file_id: The ID of the file
        :param keyframes: List of key frame numbers to delete
        :return: Response from the API
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/actions/delete_keyframes?project_id={self.project_id}&uuid={unique_id}&client_id={self.client.client_id}"

            return self.client.make_request(
                "POST",
                url,
                extra_headers={"content-type": "application/json"},
                request_id=unique_id,
                json={
                    "project_id": self.project_id,
                    "file_id": file_id,
                    "keyframes": keyframes,
                },
            )

        except LabellerrError as e:
            raise e
        except Exception as e:
            raise LabellerrError(f"Failed to delete key frames: {str(e)}")

    def upload_preannotation(
        self, annotation_format: str, annotation_file: str, conf_bucket: str = None
    ):
        """
        Upload pre-annotations for video project.

        For video projects, use annotation_format="video_json" with a JSON file containing
        video annotations in the format:
        [
            {
                "file_name": "video.mp4",
                "annotations": [
                    {
                        "question_name": "Label name",
                        "question_type": "BoundingBox" or "polygon",
                        "answer": [
                            {
                                "frames": {
                                    "0": {
                                        "frame": 0,
                                        "answer": {
                                            "xmin": 100, "ymin": 100, "xmax": 300, "ymax": 300, "rotation": 0
                                        },
                                        "timestamp": 0.0
                                    },
                                    "25": {
                                        "frame": 25,
                                        "answer": {
                                            "xmin": 150, "ymin": 150, "xmax": 350, "ymax": 350, "rotation": 0
                                        },
                                        "timestamp": 1.0
                                    }
                                }
                            }
                        ]
                    }
                ]
            }
        ]

        For polygon annotations, use answer format:
        "answer": [{"x": 0, "y": 600}, {"x": 1920, "y": 600}, ...]

        :param annotation_format: Format of annotations ("video_json", "coco_json", etc.)
        :param annotation_file: Path to the annotation file
        :param conf_bucket: Optional confidence bucket ("low", "medium", "high")
        :return: Response with job status
        :raises LabellerrError: If upload fails
        """
        # Delegate to the base class synchronous upload (blocks until completion)
        return self.upload_preannotations(
            annotation_format, annotation_file, conf_bucket, _async=False
        )

    def upload_preannotation_async(
        self, annotation_format: str, annotation_file: str, conf_bucket: str = None
    ) -> Future:
        """
        Asynchronously upload pre-annotations for video project and monitor the job status.

        This method returns immediately with a Future object. The actual upload and monitoring
        happens in a background thread. Use future.result() to wait for completion.

        For video projects, use annotation_format="video_json" with a JSON file containing
        video annotations.

        :param annotation_format: Format of annotations ("video_json", "coco_json", etc.)
        :param annotation_file: Path to the annotation file
        :param conf_bucket: Optional confidence bucket ("low", "medium", "high")
        :return: Future object that will contain the response when complete
        :raises LabellerrError: If upload fails
        """
        # Delegate to the base class async upload (returns Future immediately)
        return self.upload_preannotations(
            annotation_format, annotation_file, conf_bucket, _async=True
        )


LabellerrProjectMeta._register(DatasetDataType.video, VideoProject)
