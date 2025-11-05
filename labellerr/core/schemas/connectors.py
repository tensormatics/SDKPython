"""
Schema models for connection operations (AWS, GCS, etc.).
"""

import os
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class DatasetDataType(str, Enum):
    """Enum for dataset data types."""

    image = "image"
    video = "video"
    audio = "audio"
    document = "document"
    text = "text"


class ConnectionType(str, Enum):
    """Enum for connection types."""

    _IMPORT = "import"
    _EXPORT = "export"

class ConnectorType(str, Enum):
    """Enum for connector types."""

    _S3 = "s3"
    _GCS = "gcs"
    _LOCAL = "local"

class AWSConnectionTestParams(BaseModel):
    """Parameters for testing an AWS S3 connection."""

    aws_access_key: str = Field(min_length=1)
    aws_secrets_key: str = Field(min_length=1)
    s3_path: str = Field(min_length=1)
    connection_type: ConnectionType = ConnectionType._IMPORT


class AWSConnectionParams(AWSConnectionTestParams):
    """Parameters for creating an AWS S3 connection."""

    name: str = Field(min_length=1)
    description: str


class GCSConnectionParams(BaseModel):
    """Parameters for creating a GCS connection."""

    client_id: str = Field(min_length=1)
    gcs_cred_file: str
    gcs_path: str = Field(min_length=1)
    data_type: DatasetDataType
    name: str = Field(min_length=1)
    description: str
    connection_type: str = "import"
    credentials: str = "svc_account_json"

    @field_validator("gcs_cred_file")
    @classmethod
    def validate_gcs_cred_file(cls, v):
        if not os.path.exists(v):
            raise ValueError(f"GCS credential file not found: {v}")
        return v


class DeleteConnectionParams(BaseModel):
    """Parameters for deleting a connection."""

    client_id: str = Field(min_length=1)
    connection_id: str = Field(min_length=1)


class AWSConnectorConfig(BaseModel):
    """Configuration for AWS S3 connector."""

    aws_access_key: str = Field(min_length=1)
    aws_secrets_key: str = Field(min_length=1)
    s3_path: str = Field(min_length=1)
    data_type: Literal["image", "video", "audio", "document", "text"]
    name: Optional[str] = None
    description: str = "Auto-created AWS connector"
    connection_type: str = "import"


class GCPConnectorConfig(BaseModel):
    """Configuration for GCP connector."""

    gcs_cred_file: str = Field(min_length=1)
    gcs_path: str = Field(min_length=1)
    data_type: Literal["image", "video", "audio", "document", "text"]
    name: Optional[str] = None
    description: str = "Auto-created GCS connector"
    connection_type: str = "import"
    credentials: str = "svc_account_json"

    @field_validator("gcs_cred_file")
    @classmethod
    def validate_gcs_cred_file(cls, v):
        if not os.path.exists(v):
            raise ValueError(f"GCS credential file not found: {v}")
        return v
