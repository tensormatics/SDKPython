"""
Unit tests for create_dataset path parameter validation.

This module focuses on testing path parameter handling for AWS and GCS connectors
in the create_dataset functionality.
"""

from unittest.mock import patch

import pytest

from labellerr.core.datasets import create_dataset
from labellerr.core.exceptions import LabellerrError
from labellerr.core.schemas import DatasetConfig


@pytest.mark.unit
class TestCreateDatasetPathValidation:
    """Test path parameter validation for AWS and GCS connectors"""

    def test_aws_connector_missing_path_with_config(self, client):
        """Test that AWS connector requires path when using connector_config"""
        dataset_config = DatasetConfig(
            client_id="test_client_id",
            dataset_name="Test AWS Dataset",
            data_type="image",
            connector_type="aws",
        )

        aws_config = {
            "aws_access_key_id": "test-key",
            "aws_secret_access_key": "test-secret",
            "aws_region": "us-east-1",
            "bucket_name": "test-bucket",
            "data_type": "image",
        }

        with pytest.raises(LabellerrError) as exc_info:
            create_dataset(
                client=client,
                dataset_config=dataset_config,
                connector_config=aws_config,
                # Missing path parameter
            )

        assert "path is required for aws connector" in str(exc_info.value)

    def test_gcp_connector_missing_path_with_config(self, client):
        """Test that GCP connector requires path when using connector_config"""
        dataset_config = DatasetConfig(
            client_id="test_client_id",
            dataset_name="Test GCP Dataset",
            data_type="image",
            connector_type="gcp",
        )

        # Create a temporary credentials file for testing
        import json
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"type": "service_account"}, f)
            temp_cred_file = f.name

        try:
            gcp_config = {
                "gcs_cred_file": temp_cred_file,
                "gcs_path": "gs://test-bucket/path",
                "data_type": "image",
            }

            with pytest.raises(LabellerrError) as exc_info:
                create_dataset(
                    client=client,
                    dataset_config=dataset_config,
                    connector_config=gcp_config,
                    # Missing path parameter
                )

            assert "path is required for gcp connector" in str(exc_info.value)
        finally:
            import os

            os.unlink(temp_cred_file)

    def test_aws_connector_with_path_and_connection_id(self, client):
        """Test AWS connector with both path and existing connection_id"""
        dataset_config = DatasetConfig(
            client_id="test_client_id",
            dataset_name="Test AWS Dataset",
            data_type="image",
            connector_type="aws",
        )

        mock_response = {
            "response": {"dataset_id": "test-dataset-id", "data_type": "image"}
        }

        # Mock both the dataset creation and the get_dataset call
        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.datasets.base.LabellerrDataset.get_dataset",
                return_value={"dataset_id": "test-dataset-id", "data_type": "image"},
            ):
                dataset = create_dataset(
                    client=client,
                    dataset_config=dataset_config,
                    path="s3://test-bucket/path/to/data",
                    connection_id="existing-aws-connection-id",
                )

                # Should succeed - path is provided with connection_id
                assert dataset is not None

    def test_gcp_connector_with_path_and_connection_id(self, client):
        """Test GCP connector with both path and existing connection_id"""
        dataset_config = DatasetConfig(
            client_id="test_client_id",
            dataset_name="Test GCP Dataset",
            data_type="image",
            connector_type="gcp",
        )

        mock_response = {
            "response": {"dataset_id": "test-dataset-id", "data_type": "image"}
        }

        # Mock both the dataset creation and the get_dataset call
        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.datasets.base.LabellerrDataset.get_dataset",
                return_value={"dataset_id": "test-dataset-id", "data_type": "image"},
            ):
                dataset = create_dataset(
                    client=client,
                    dataset_config=dataset_config,
                    path="gs://test-bucket/path/to/data",
                    connection_id="existing-gcp-connection-id",
                )

                # Should succeed - path is provided with connection_id
                assert dataset is not None

    def test_local_connector_path_parameter_ignored(self, client):
        """Test that local connector ignores path parameter"""
        dataset_config = DatasetConfig(
            client_id="test_client_id",
            dataset_name="Test Local Dataset",
            data_type="image",
            connector_type="local",
        )

        mock_response = {
            "response": {"dataset_id": "test-dataset-id", "data_type": "image"}
        }

        # Mock both the dataset creation and the get_dataset call
        with patch.object(client, "make_request", return_value=mock_response):
            with patch(
                "labellerr.core.datasets.base.LabellerrDataset.get_dataset",
                return_value={"dataset_id": "test-dataset-id", "data_type": "image"},
            ):
                dataset = create_dataset(
                    client=client,
                    dataset_config=dataset_config,
                    path="some/ignored/path",  # Should be ignored for local
                )

                # Should succeed - path is not validated for local connector
                assert dataset is not None

    def test_aws_missing_connector_config_and_connection_id(self, client):
        """Test error when neither connector_config nor connection_id is provided for AWS"""
        dataset_config = DatasetConfig(
            client_id="test_client_id",
            dataset_name="Test AWS Dataset",
            data_type="image",
            connector_type="aws",
        )

        with pytest.raises(LabellerrError) as exc_info:
            create_dataset(
                client=client,
                dataset_config=dataset_config,
                path="s3://test-bucket/path/to/data",
                # Missing both connector_config and connection_id
            )

        assert "connector_config is required for aws connector" in str(exc_info.value)

    def test_gcp_missing_connector_config_and_connection_id(self, client):
        """Test error when neither connector_config nor connection_id is provided for GCP"""
        dataset_config = DatasetConfig(
            client_id="test_client_id",
            dataset_name="Test GCP Dataset",
            data_type="image",
            connector_type="gcp",
        )

        with pytest.raises(LabellerrError) as exc_info:
            create_dataset(
                client=client,
                dataset_config=dataset_config,
                path="gs://test-bucket/path/to/data",
                # Missing both connector_config and connection_id
            )

        assert "connector_config is required for gcp connector" in str(exc_info.value)

    def test_both_connection_id_and_connector_config(self, client):
        """Test error when both connection_id and connector_config are provided"""
        dataset_config = DatasetConfig(
            client_id="test_client_id",
            dataset_name="Test AWS Dataset",
            data_type="image",
            connector_type="aws",
        )

        aws_config = {
            "aws_access_key_id": "test-key",
            "aws_secret_access_key": "test-secret",
            "aws_region": "us-east-1",
            "bucket_name": "test-bucket",
            "data_type": "image",
        }

        with pytest.raises(LabellerrError) as exc_info:
            create_dataset(
                client=client,
                dataset_config=dataset_config,
                path="s3://test-bucket/path/to/data",
                connection_id="existing-connection-id",
                connector_config=aws_config,
            )

        assert "Cannot provide both connection_id and connector_config" in str(
            exc_info.value
        )
