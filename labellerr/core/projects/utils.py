from typing import Dict, Any
from ..exceptions import LabellerrError

def validate_rotation_config(rotation_config: Dict[str, Any]) -> None:
    """
    Validates a rotation configuration.

    :param rotation_config: A dictionary containing the configuration for the rotations.
    :raises LabellerrError: If the configuration is invalid.
    """
    annotation_rotation_count = rotation_config.get("annotation_rotation_count")
    review_rotation_count = rotation_config.get("review_rotation_count")
    client_review_rotation_count = rotation_config.get("client_review_rotation_count")

    # Validate review_rotation_count
    if int(review_rotation_count or 0) != 1:
        raise LabellerrError("review_rotation_count must be 1")

    # Validate client_review_rotation_count based on annotation_rotation_count
    if (
        int(annotation_rotation_count or 0) == 0
        and int(client_review_rotation_count or 0) != 0
    ):
        raise LabellerrError(
            "client_review_rotation_count must be 0 when annotation_rotation_count is 0"
        )
    elif int(annotation_rotation_count or 0) == 1 and int(
        client_review_rotation_count or 0
    ) not in [0, 1]:
        raise LabellerrError(
            "client_review_rotation_count can only be 0 or 1 when annotation_rotation_count is 1"
        )
    elif (
        int(annotation_rotation_count or 0) > 1
        and int(client_review_rotation_count or 0) != 0
    ):
        raise LabellerrError(
            "client_review_rotation_count must be 0 when annotation_rotation_count is greater than 1"
        )
