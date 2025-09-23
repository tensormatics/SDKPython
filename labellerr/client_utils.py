"""
Shared utilities for both sync and async Labellerr clients.
"""

import uuid
from typing import Any, Dict, Optional

from . import constants


def build_headers(
    api_key: str,
    api_secret: str,
    source: str = "sdk",
    client_id: Optional[str] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Builds standard headers for API requests.

    :param api_key: API key for authentication
    :param api_secret: API secret for authentication
    :param source: Source identifier (e.g., "sdk", "sdk-async")
    :param client_id: Optional client ID to include in headers
    :param extra_headers: Optional dictionary of additional headers
    :return: Dictionary of headers
    """
    headers = {
        "api_key": api_key,
        "api_secret": api_secret,
        "source": source,
        "origin": constants.ALLOWED_ORIGINS,
    }

    if client_id:
        headers["client_id"] = str(client_id)

    if extra_headers:
        headers.update(extra_headers)

    return headers


def validate_rotation_config(rotation_config: Dict[str, Any]) -> None:
    """
    Validates a rotation configuration.

    :param rotation_config: A dictionary containing the configuration for the rotations.
    :raises LabellerrError: If the configuration is invalid.
    """
    from .exceptions import LabellerrError

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


def validate_required_params(params: Dict[str, Any], required_list: list) -> None:
    """
    Validates that all required parameters are present.

    :param params: Dictionary of parameters to validate
    :param required_list: List of required parameter names
    :raises LabellerrError: If any required parameter is missing
    """
    from .exceptions import LabellerrError

    for param in required_list:
        if param not in params:
            raise LabellerrError(f"Required parameter {param} is missing")


def validate_file_exists(file_path: str) -> str:
    """
    Validates that a file exists and returns the basename.

    :param file_path: Path to the file
    :return: basename of the file
    :raises LabellerrError: If file doesn't exist
    """
    import os

    from .exceptions import LabellerrError

    if os.path.exists(file_path):
        return os.path.basename(file_path)
    else:
        raise LabellerrError(f"File not found: {file_path}")


def validate_annotation_format(annotation_format: str, annotation_file: str) -> None:
    """
    Validates annotation format and file extension compatibility.

    :param annotation_format: Format of the annotation
    :param annotation_file: Path to the annotation file
    :raises LabellerrError: If format/extension mismatch
    """
    import os

    from .exceptions import LabellerrError

    if annotation_format not in constants.ANNOTATION_FORMAT:
        raise LabellerrError(
            f"Invalid annotation_format. Must be one of {constants.ANNOTATION_FORMAT}"
        )

    # Check if the file extension is .json when annotation_format is coco_json
    if annotation_format == "coco_json":
        file_extension = os.path.splitext(annotation_file)[1].lower()
        if file_extension != ".json":
            raise LabellerrError(
                "For coco_json annotation format, the file must have a .json extension"
            )


def validate_export_config(export_config: Dict[str, Any]) -> None:
    """
    Validates export configuration parameters.

    :param export_config: Export configuration dictionary
    :raises LabellerrError: If configuration is invalid
    """
    from .exceptions import LabellerrError

    required_params = [
        "export_name",
        "export_description",
        "export_format",
        "statuses",
    ]

    for param in required_params:
        if param not in export_config:
            raise LabellerrError(f"Required parameter {param} is missing")

        if param == "export_format":
            if export_config[param] not in constants.LOCAL_EXPORT_FORMAT:
                raise LabellerrError(
                    f"Invalid export_format. Must be one of {constants.LOCAL_EXPORT_FORMAT}"
                )

        if param == "statuses":
            if not isinstance(export_config[param], list):
                raise LabellerrError(f"Invalid statuses. Must be an array {param}")
            for status in export_config[param]:
                if status not in constants.LOCAL_EXPORT_STATUS:
                    raise LabellerrError(
                        f"Invalid status. Must be one of {constants.LOCAL_EXPORT_STATUS}"
                    )


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())
