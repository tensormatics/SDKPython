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
        "created_by": "test_user@example.com",
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
            attached_datasets=[dataset_id],
            annotation_template_id=template_id,
            rotations=sample_valid_payload["rotation_config"],
            use_ai=False,
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
            "autolabel",
        ]

        for param in required_params:
            invalid_payload = sample_valid_payload.copy()
            del invalid_payload[param]

            with pytest.raises(LabellerrError) as exc_info:
                client.initiate_create_project(invalid_payload)

            assert f"Required parameter {param} is missing" in str(exc_info.value)

        # Test annotation_guide separately since it has special validation
        invalid_payload = sample_valid_payload.copy()
        del invalid_payload["annotation_guide"]

        with pytest.raises(LabellerrError) as exc_info:
            client.initiate_create_project(invalid_payload)

        assert (
            "Please provide either annotation guide or annotation template id"
            in str(exc_info.value)
        )

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


class TestCreateUser:
    """Test cases for create_user method"""

    @patch("labellerr.client.LabellerrClient._make_request")
    def test_create_user_success(self, mock_make_request, client):
        """Test successful user creation"""
        # Mock response
        mock_response = type(
            "MockResponse",
            (),
            {
                "status_code": 200,
                "json": lambda *args, **kwargs: {
                    "response": {"user_id": "user_123", "status": "created"}
                },
            },
        )()
        mock_make_request.return_value = mock_response

        # Test data
        client_id = "12345"
        first_name = "John"
        last_name = "Doe"
        email_id = "john.doe@example.com"
        projects = ["project_1", "project_2"]
        roles = [
            {"project_id": "project_1", "role_id": 7},
            {"project_id": "project_2", "role_id": 5},
        ]

        # Execute
        result = client.create_user(
            client_id=client_id,
            first_name=first_name,
            last_name=last_name,
            email_id=email_id,
            projects=projects,
            roles=roles,
        )

        # Assert
        assert result["response"]["user_id"] == "user_123"
        assert result["response"]["status"] == "created"
        mock_make_request.assert_called_once()

    def test_create_user_missing_required_params(self, client):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            client.create_user(
                client_id="12345",
                first_name="John",
                last_name="Doe",
                # Missing email_id, projects, roles
            )

        assert "missing a required argument" in str(exc_info.value)

    def test_create_user_invalid_client_id(self, client):
        """Test error handling for invalid client_id"""
        with pytest.raises(LabellerrError) as exc_info:
            client.create_user(
                client_id=12345,  # Not a string
                first_name="John",
                last_name="Doe",
                email_id="john@example.com",
                projects=["project_1"],
                roles=[{"project_id": "project_1", "role_id": 7}],
            )

        assert "client_id must be a string" in str(exc_info.value)

    def test_create_user_empty_projects(self, client):
        """Test error handling for empty projects list"""
        with pytest.raises(LabellerrError) as exc_info:
            client.create_user(
                client_id="12345",
                first_name="John",
                last_name="Doe",
                email_id="john@example.com",
                projects=[],  # Empty list
                roles=[{"project_id": "project_1", "role_id": 7}],
            )

        assert "projects must be a non-empty list" in str(exc_info.value)

    def test_create_user_empty_roles(self, client):
        """Test error handling for empty roles list"""
        with pytest.raises(LabellerrError) as exc_info:
            client.create_user(
                client_id="12345",
                first_name="John",
                last_name="Doe",
                email_id="john@example.com",
                projects=["project_1"],
                roles=[],  # Empty list
            )

        assert "roles must be a non-empty list" in str(exc_info.value)


class TestUpdateUserRole:
    """Test cases for update_user_role method"""

    @patch("labellerr.client.LabellerrClient._make_request")
    def test_update_user_role_success(self, mock_make_request, client):
        """Test successful user role update"""
        # Mock response
        mock_response = type(
            "MockResponse",
            (),
            {
                "status_code": 200,
                "json": lambda *args, **kwargs: {
                    "response": {"user_id": "user_123", "status": "updated"}
                },
            },
        )()
        mock_make_request.return_value = mock_response

        # Test data
        client_id = "12345"
        project_id = "project_123"
        email_id = "john.doe@example.com"
        roles = [
            {"project_id": "project_1", "role_id": 2},
            {"project_id": "project_2", "role_id": 3},
        ]

        # Execute
        result = client.update_user_role(
            client_id=client_id,
            project_id=project_id,
            email_id=email_id,
            roles=roles,
            first_name="John",
            last_name="Doe",
        )

        # Assert
        assert result["response"]["user_id"] == "user_123"
        assert result["response"]["status"] == "updated"
        mock_make_request.assert_called_once()

    def test_update_user_role_missing_required_params(self, client):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            client.update_user_role(
                client_id="12345",
                project_id="project_123",
                # Missing email_id, roles
            )

        assert "missing a required argument" in str(exc_info.value)

    def test_update_user_role_invalid_client_id(self, client):
        """Test error handling for invalid client_id"""
        with pytest.raises(LabellerrError) as exc_info:
            client.update_user_role(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
                roles=[{"project_id": "project_1", "role_id": 7}],
            )

        assert "client_id must be a string" in str(exc_info.value)

    def test_update_user_role_empty_roles(self, client):
        """Test error handling for empty roles list"""
        with pytest.raises(LabellerrError) as exc_info:
            client.update_user_role(
                client_id="12345",
                project_id="project_123",
                email_id="john@example.com",
                roles=[],  # Empty list
            )

        assert "roles must be a non-empty list" in str(exc_info.value)

    @patch("labellerr.client.LabellerrClient._make_request")
    def test_update_user_role_with_optional_fields(self, mock_make_request, client):
        """Test user role update with all optional fields"""
        # Mock response
        mock_response = type(
            "MockResponse",
            (),
            {
                "status_code": 200,
                "json": lambda *args, **kwargs: {
                    "response": {"user_id": "user_123", "status": "updated"}
                },
            },
        )()
        mock_make_request.return_value = mock_response

        # Test data
        client_id = "12345"
        project_id = "project_123"
        email_id = "john.doe@example.com"
        roles = [{"project_id": "project_1", "role_id": 2}]

        # Execute with all optional fields
        result = client.update_user_role(
            client_id=client_id,
            project_id=project_id,
            email_id=email_id,
            roles=roles,
            first_name="John",
            last_name="Doe",
            work_phone="123-456-7890",
            job_title="Developer",
            language="en",
            timezone="GMT",
            profile_image="profile.jpg",
        )

        # Assert
        assert result["response"]["user_id"] == "user_123"
        assert result["response"]["status"] == "updated"
        mock_make_request.assert_called_once()


class TestDeleteUser:
    """Test cases for delete_user method"""

    @patch("labellerr.client.LabellerrClient._make_request")
    def test_delete_user_success(self, mock_make_request, client):
        """Test successful user deletion"""
        # Mock response
        mock_response = type(
            "MockResponse",
            (),
            {
                "status_code": 200,
                "json": lambda *args, **kwargs: {
                    "response": {"user_id": "user_123", "status": "deleted"}
                },
            },
        )()
        mock_make_request.return_value = mock_response

        # Test data
        client_id = "12345"
        project_id = "project_123"
        email_id = "john.doe@example.com"
        user_id = "google-oauth2|111089843886947795024"

        # Execute
        result = client.delete_user(
            client_id=client_id,
            project_id=project_id,
            email_id=email_id,
            user_id=user_id,
            first_name="John",
            last_name="Doe",
        )

        # Assert
        assert result["response"]["user_id"] == "user_123"
        assert result["response"]["status"] == "deleted"
        mock_make_request.assert_called_once()

    def test_delete_user_missing_required_params(self, client):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            client.delete_user(
                client_id="12345",
                project_id="project_123",
                # Missing email_id, user_id
            )

        assert "missing a required argument" in str(exc_info.value)

    def test_delete_user_invalid_client_id(self, client):
        """Test error handling for invalid client_id"""
        with pytest.raises(LabellerrError) as exc_info:
            client.delete_user(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
                user_id="user_123",
            )

        assert "client_id must be a string" in str(exc_info.value)

    @patch("labellerr.client.LabellerrClient._make_request")
    def test_delete_user_with_all_fields(self, mock_make_request, client):
        """Test user deletion with all optional fields"""
        # Mock response
        mock_response = type(
            "MockResponse",
            (),
            {
                "status_code": 200,
                "json": lambda *args, **kwargs: {
                    "response": {"user_id": "user_123", "status": "deleted"}
                },
            },
        )()
        mock_make_request.return_value = mock_response

        # Test data
        client_id = "12345"
        project_id = "project_123"
        email_id = "john.doe@example.com"
        user_id = "google-oauth2|111089843886947795024"

        # Execute with all optional fields
        result = client.delete_user(
            client_id=client_id,
            project_id=project_id,
            email_id=email_id,
            user_id=user_id,
            first_name="John",
            last_name="Doe",
            is_active=0,
            role="Admin",
            user_created_at="Thu, 17 Jun 2021 12:59:55 GMT",
            max_activity_created_at="2021-06-17T12:59:55.000Z",
            image_url="profile.jpg",
            name="John Doe",
            activity="Active",
            creation_date="2021-06-17T12:59:55.000Z",
            status="Deactivated",
        )

        # Assert
        assert result["response"]["user_id"] == "user_123"
        assert result["response"]["status"] == "deleted"
        mock_make_request.assert_called_once()

    def test_delete_user_invalid_project_id(self, client):
        """Test error handling for invalid project_id"""
        with pytest.raises(LabellerrError) as exc_info:
            client.delete_user(
                client_id="12345",
                project_id=12345,  # Not a string
                email_id="john@example.com",
                user_id="user_123",
            )

        assert "project_id must be a string" in str(exc_info.value)

    def test_delete_user_invalid_email_id(self, client):
        """Test error handling for invalid email_id"""
        with pytest.raises(LabellerrError) as exc_info:
            client.delete_user(
                client_id="12345",
                project_id="project_123",
                email_id=12345,  # Not a string
                user_id="user_123",
            )

        assert "email_id must be a string" in str(exc_info.value)

    def test_delete_user_invalid_user_id(self, client):
        """Test error handling for invalid user_id"""
        with pytest.raises(LabellerrError) as exc_info:
            client.delete_user(
                client_id="12345",
                project_id="project_123",
                email_id="john@example.com",
                user_id=12345,  # Not a string
            )

        assert "user_id must be a string" in str(exc_info.value)


class TestAddUserToProject:
    """Test cases for add_user_to_project method"""

    @patch("labellerr.client.LabellerrClient._make_request")
    def test_add_user_to_project_success(self, mock_make_request, client):
        """Test successful user addition to project"""
        # Mock response
        mock_response = type(
            "MockResponse",
            (),
            {
                "status_code": 200,
                "json": lambda *args, **kwargs: {
                    "response": {"user_id": "user_123", "status": "added"}
                },
            },
        )()
        mock_make_request.return_value = mock_response

        # Test data
        client_id = "12345"
        project_id = "project_123"
        email_id = "john.doe@example.com"
        role_id = "7"

        # Execute
        result = client.add_user_to_project(
            client_id=client_id,
            project_id=project_id,
            email_id=email_id,
            role_id=role_id,
        )

        # Assert
        assert result["response"]["user_id"] == "user_123"
        assert result["response"]["status"] == "added"
        mock_make_request.assert_called_once()

    def test_add_user_to_project_missing_required_params(self, client):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            client.add_user_to_project(
                client_id="12345",
                project_id="project_123",
                # Missing email_id
            )

        assert "missing a required argument" in str(exc_info.value)

    def test_add_user_to_project_invalid_client_id(self, client):
        """Test error handling for invalid client_id"""
        with pytest.raises(LabellerrError) as exc_info:
            client.add_user_to_project(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
            )

        assert "client_id must be a string" in str(exc_info.value)


class TestRemoveUserFromProject:
    """Test cases for remove_user_from_project method"""

    @patch("labellerr.client.LabellerrClient._make_request")
    def test_remove_user_from_project_success(self, mock_make_request, client):
        """Test successful user removal from project"""
        # Mock response
        mock_response = type(
            "MockResponse",
            (),
            {
                "status_code": 200,
                "json": lambda *args, **kwargs: {
                    "response": {"user_id": "user_123", "status": "removed"}
                },
            },
        )()
        mock_make_request.return_value = mock_response

        # Test data
        client_id = "12345"
        project_id = "project_123"
        email_id = "john.doe@example.com"

        # Execute
        result = client.remove_user_from_project(
            client_id=client_id, project_id=project_id, email_id=email_id
        )

        # Assert
        assert result["response"]["user_id"] == "user_123"
        assert result["response"]["status"] == "removed"
        mock_make_request.assert_called_once()

    def test_remove_user_from_project_missing_required_params(self, client):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            client.remove_user_from_project(
                client_id="12345",
                project_id="project_123",
                # Missing email_id
            )

        assert "missing a required argument" in str(exc_info.value)

    def test_remove_user_from_project_invalid_client_id(self, client):
        """Test error handling for invalid client_id"""
        with pytest.raises(LabellerrError) as exc_info:
            client.remove_user_from_project(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
            )

        assert "client_id must be a string" in str(exc_info.value)


class TestChangeUserRole:
    """Test cases for change_user_role method"""

    @patch("labellerr.client.LabellerrClient._make_request")
    def test_change_user_role_success(self, mock_make_request, client):
        """Test successful user role change"""
        # Mock response
        mock_response = type(
            "MockResponse",
            (),
            {
                "status_code": 200,
                "json": lambda *args, **kwargs: {
                    "response": {"user_id": "user_123", "status": "role_changed"}
                },
            },
        )()
        mock_make_request.return_value = mock_response

        # Test data
        client_id = "12345"
        project_id = "project_123"
        email_id = "john.doe@example.com"
        new_role_id = "7"

        # Execute
        result = client.change_user_role(
            client_id=client_id,
            project_id=project_id,
            email_id=email_id,
            new_role_id=new_role_id,
        )

        # Assert
        assert result["response"]["user_id"] == "user_123"
        assert result["response"]["status"] == "role_changed"
        mock_make_request.assert_called_once()

    def test_change_user_role_missing_required_params(self, client):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            client.change_user_role(
                client_id="12345",
                project_id="project_123",
                email_id="john@example.com",
                # Missing new_role_id
            )

        assert "missing a required argument" in str(exc_info.value)

    def test_change_user_role_invalid_client_id(self, client):
        """Test error handling for invalid client_id"""
        with pytest.raises(LabellerrError) as exc_info:
            client.change_user_role(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
                new_role_id="7",
            )

        assert "client_id must be a string" in str(exc_info.value)


class TestListAndBulkAssignFiles:
    """Tests for list_file and bulk_assign_files methods"""

    @patch("labellerr.client.LabellerrClient._make_request")
    def test_list_file_success(self, mock_make_request, client):
        mock_response = type(
            "MockResponse",
            (),
            {
                "status_code": 200,
                "json": lambda *args, **kwargs: {
                    "response": {"files": [{"id": "file1"}], "next_search_after": None}
                },
            },
        )()
        mock_make_request.return_value = mock_response

        result = client.list_file(
            client_id="12345",
            project_id="project_123",
            search_queries=[
                {
                    "op": "OR",
                    "id": "file_status",
                    "values": [{"p": "in", "v": ["None"]}],
                }
            ],
            size=10,
            next_search_after=None,
        )

        assert "files" in result["response"]
        mock_make_request.assert_called_once()

    def test_list_file_missing_required(self, client):
        with pytest.raises(TypeError):
            client.list_file(client_id="12345", project_id="project_123")

    @patch("labellerr.client.LabellerrClient._make_request")
    def test_bulk_assign_files_success(self, mock_make_request, client):
        mock_response = type(
            "MockResponse",
            (),
            {
                "status_code": 200,
                "json": lambda *args, **kwargs: {"response": {"updated": 1}},
            },
        )()
        mock_make_request.return_value = mock_response

        result = client.bulk_assign_files(
            client_id="12345",
            project_id="project_123",
            file_ids=["file-id-1"],
            new_status="None",
        )

        assert result["response"]["updated"] == 1
        mock_make_request.assert_called_once()

    def test_bulk_assign_files_missing_required(self, client):
        with pytest.raises(TypeError):
            client.bulk_assign_files(
                client_id="12345", project_id="project_123", new_status="None"
            )


if __name__ == "__main__":
    pytest.main()
