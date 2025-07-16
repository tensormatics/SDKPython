import os
import uuid
from unittest.mock import patch

import pytest

from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError


@pytest.fixture
def client():
    """Create a test client with mock credentials"""
    return LabellerrClient("test_api_key", "test_api_secret")


@pytest.fixture
def sample_valid_payload():
    """Create a sample valid payload for initiate_create_project"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    test_image = os.path.join(current_dir, "test_data", "test_image.jpg")

    # Create test directory and file if they don't exist
    os.makedirs(os.path.join(current_dir, "test_data"), exist_ok=True)
    if not os.path.exists(test_image):
        with open(test_image, "w") as f:
            f.write("dummy image content")

    return {
        "client_id": "12345",
        "dataset_name": "Test Dataset",
        "dataset_description": "Dataset for testing",
        "data_type": "image",
        "created_by": "test_user",
        "project_name": "Test Project",
        "autolabel": False,
        "files_to_upload": [test_image],
        "annotation_guide": [
            {
                "option_type": "radio",
                "question": "Test Question",
                "options": ["Option 1", "Option 2"],
            }
        ],
        "rotation_config": {
            "annotation_rotation_count": 1,
            "review_rotation_count": 1,
            "client_review_rotation_count": 1,
        },
    }


class TestInitiateCreateProject:

    @patch("labellerr.client.LabellerrClient.create_dataset")
    @patch("labellerr.client.LabellerrClient.get_dataset")
    @patch("labellerr.client.utils.poll")
    @patch("labellerr.client.LabellerrClient.create_annotation_guideline")
    @patch("labellerr.client.LabellerrClient.create_project")
    def test_successful_project_creation(
        self,
        mock_create_project,
        mock_create_guideline,
        mock_poll,
        mock_get_dataset,
        mock_create_dataset,
        client,
        sample_valid_payload,
    ):
        """Test successful project creation flow"""
        # Configure mocks
        dataset_id = str(uuid.uuid4())
        mock_create_dataset.return_value = {
            "response": "success",
            "dataset_id": dataset_id,
        }

        mock_get_dataset.return_value = {"response": {"status_code": 300}}

        mock_poll.return_value = {"response": {"status_code": 300}}

        template_id = str(uuid.uuid4())
        mock_create_guideline.return_value = template_id

        expected_project_response = {
            "response": "success",
            "project_id": str(uuid.uuid4()),
        }
        mock_create_project.return_value = expected_project_response

        # Execute
        result = client.initiate_create_project(sample_valid_payload)

        # Assert
        assert result["status"] == "success"
        assert "message" in result
        assert "project_id" in result
        mock_create_dataset.assert_called_once()
        mock_poll.assert_called_once()
        mock_create_guideline.assert_called_once_with(
            sample_valid_payload["client_id"],
            sample_valid_payload["annotation_guide"],
            sample_valid_payload["project_name"],
            sample_valid_payload["data_type"],
        )
        mock_create_project.assert_called_once_with(
            project_name=sample_valid_payload["project_name"],
            data_type=sample_valid_payload["data_type"],
            client_id=sample_valid_payload["client_id"],
            dataset_id=dataset_id,
            annotation_template_id=template_id,
            rotation_config=sample_valid_payload["rotation_config"],
            created_by=sample_valid_payload["created_by"],
        )

    def test_missing_required_parameters(self, client, sample_valid_payload):
        """Test error handling for missing required parameters"""
        # Remove required parameters one by one and test
        required_params = [
            "client_id",
            "dataset_name",
            "dataset_description",
            "data_type",
            "created_by",
            "project_name",
            "annotation_guide",
            "autolabel",
        ]

        for param in required_params:
            invalid_payload = sample_valid_payload.copy()
            del invalid_payload[param]

            with pytest.raises(LabellerrError) as exc_info:
                client.initiate_create_project(invalid_payload)

            assert f"Required parameter {param} is missing" in str(exc_info.value)

    def test_invalid_client_id(self, client, sample_valid_payload):
        """Test error handling for invalid client_id"""
        invalid_payload = sample_valid_payload.copy()
        invalid_payload["client_id"] = 123  # Not a string

        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        assert "client_id must be a non-empty string" in str(exc_info.value)

        # Test empty string
        invalid_payload["client_id"] = "   "
        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        # Whitespace client_id causes HTTP header issues
        assert "Invalid leading whitespace" in str(
            exc_info.value
        ) or "client_id must be a non-empty string" in str(exc_info.value)

    def test_invalid_annotation_guide(self, client, sample_valid_payload):
        """Test error handling for invalid annotation guide"""
        invalid_payload = sample_valid_payload.copy()

        # Missing option_type
        invalid_payload["annotation_guide"] = [{"question": "Test Question"}]
        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        assert "option_type is required in annotation_guide" in str(exc_info.value)

        # Invalid option_type
        invalid_payload["annotation_guide"] = [
            {"option_type": "invalid_type", "question": "Test Question"}
        ]
        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        assert "option_type must be one of" in str(exc_info.value)

    def test_both_upload_methods_specified(self, client, sample_valid_payload):
        """Test error when both files_to_upload and folder_to_upload are specified"""
        invalid_payload = sample_valid_payload.copy()
        invalid_payload["folder_to_upload"] = "/path/to/folder"

        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        assert "Cannot provide both files_to_upload and folder_to_upload" in str(
            exc_info.value
        )

    def test_no_upload_method_specified(self, client, sample_valid_payload):
        """Test error when neither files_to_upload nor folder_to_upload are specified"""
        invalid_payload = sample_valid_payload.copy()
        del invalid_payload["files_to_upload"]

        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        assert "Either files_to_upload or folder_to_upload must be provided" in str(
            exc_info.value
        )

    def test_empty_files_to_upload(self, client, sample_valid_payload):
        """Test error handling for empty files_to_upload"""
        invalid_payload = sample_valid_payload.copy()
        invalid_payload["files_to_upload"] = []

        with pytest.raises(LabellerrError):
            client.initiate_create_project(invalid_payload)

    def test_invalid_folder_to_upload(self, client, sample_valid_payload):
        """Test error handling for invalid folder_to_upload"""
        invalid_payload = sample_valid_payload.copy()
        del invalid_payload["files_to_upload"]
        invalid_payload["folder_to_upload"] = "   "

        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        assert "Folder path does not exist" in str(exc_info.value)

    @patch("labellerr.client.LabellerrClient.create_dataset")
    def test_create_dataset_error(
        self, mock_create_dataset, client, sample_valid_payload
    ):
        """Test error handling when create_dataset fails"""
        error_message = "Failed to create dataset"
        mock_create_dataset.side_effect = LabellerrError(error_message)

        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(sample_valid_payload)

        assert error_message in str(exc_info.value)

    @patch("labellerr.client.LabellerrClient.create_dataset")
    @patch("labellerr.client.utils.poll")
    def test_poll_timeout(
        self, mock_poll, mock_create_dataset, client, sample_valid_payload
    ):
        """Test handling when dataset polling times out"""
        dataset_id = str(uuid.uuid4())
        mock_create_dataset.return_value = {
            "response": "success",
            "dataset_id": dataset_id,
        }

        # Poll returns None when it times out
        mock_poll.return_value = None

        with pytest.raises(LabellerrError):
            client.initiate_create_project(sample_valid_payload)

    @patch("labellerr.client.LabellerrClient.create_dataset")
    @patch("labellerr.client.utils.poll")
    @patch("labellerr.client.LabellerrClient.create_annotation_guideline")
    def test_create_guideline_error(
        self,
        mock_create_guideline,
        mock_poll,
        mock_create_dataset,
        client,
        sample_valid_payload,
    ):
        """Test error handling when create_annotation_guideline fails"""
        dataset_id = str(uuid.uuid4())
        mock_create_dataset.return_value = {
            "response": "success",
            "dataset_id": dataset_id,
        }
        mock_poll.return_value = {"response": {"status_code": 300}}

        error_message = "Failed to create annotation guideline"
        mock_create_guideline.side_effect = LabellerrError(error_message)

        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(sample_valid_payload)

        assert error_message in str(exc_info.value)

    @patch("labellerr.client.LabellerrClient.create_dataset")
    @patch("labellerr.client.utils.poll")
    @patch("labellerr.client.LabellerrClient.create_annotation_guideline")
    @patch("labellerr.client.LabellerrClient.create_project")
    def test_create_project_error(
        self,
        mock_create_project,
        mock_create_guideline,
        mock_poll,
        mock_create_dataset,
        client,
        sample_valid_payload,
    ):
        """Test error handling when create_project fails"""
        dataset_id = str(uuid.uuid4())
        mock_create_dataset.return_value = {
            "response": "success",
            "dataset_id": dataset_id,
        }
        mock_poll.return_value = {"response": {"status_code": 300}}

        template_id = str(uuid.uuid4())
        mock_create_guideline.return_value = template_id

        error_message = "Failed to create project"
        mock_create_project.side_effect = LabellerrError(error_message)

        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(sample_valid_payload)

        assert error_message in str(exc_info.value)


if __name__ == "__main__":
    pytest.main()
