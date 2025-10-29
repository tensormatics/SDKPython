"""
Unit tests for Labellerr client functionality.

This module contains unit tests that test individual components
in isolation using mocks and fixtures.
"""

import os

import pytest
from pydantic import ValidationError

from labellerr.core.exceptions import LabellerrError
from labellerr.core.projects import create_project
from labellerr.core.projects.image_project import ImageProject
from labellerr.core.users.base import LabellerrUsers


@pytest.fixture
def project(client):
    """Create a test project instance without making API calls"""
    # Create a mock ImageProject instance directly, bypassing the metaclass factory
    project_data = {
        "project_id": "test_project_id",
        "data_type": "image",
        "attached_datasets": [],
    }
    # Use __new__ to create instance without calling __init__ through metaclass
    proj = ImageProject.__new__(ImageProject)
    proj.client = client
    proj.project_id = "test_project_id"
    proj.project_data = project_data
    return proj


@pytest.fixture
def users(client):
    """Create a test users instance with client reference"""
    users_instance = LabellerrUsers(client)
    return users_instance


@pytest.fixture
def sample_valid_payload():
    """Create a sample valid payload for create_project"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    test_image = os.path.join(current_dir, "test_data", "test_image.jpg")

    # Create test directory and file if they don't exist
    os.makedirs(os.path.join(current_dir, "test_data"), exist_ok=True)
    if not os.path.exists(test_image):
        with open(test_image, "w") as f:
            f.write("dummy image content")

    return {
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


@pytest.mark.unit
class TestInitiateCreateProject:

    def test_missing_required_parameters(self, client, sample_valid_payload):
        """Test error handling for missing required parameters"""
        # Remove required parameters one by one and test
        # Current required params in create_project: data_type, created_by, project_name, autolabel
        required_params = [
            "data_type",
            "created_by",
            "project_name",
            "autolabel",
        ]

        for param in required_params:
            invalid_payload = sample_valid_payload.copy()
            del invalid_payload[param]

            with pytest.raises(LabellerrError) as exc_info:
                create_project(client, invalid_payload)

            assert f"Required parameter {param} is missing" in str(exc_info.value)

        # Test annotation_guide separately since it has special validation
        invalid_payload = sample_valid_payload.copy()
        del invalid_payload["annotation_guide"]

        with pytest.raises(LabellerrError) as exc_info:
            create_project(client, invalid_payload)

        assert (
            "Please provide either annotation guide or annotation template id"
            in str(exc_info.value)
        )

    def test_invalid_created_by_email(self, client, sample_valid_payload):
        """Test error handling for invalid created_by email format"""
        invalid_payload = sample_valid_payload.copy()
        invalid_payload["created_by"] = "not_an_email"  # Missing @ and domain

        with pytest.raises(LabellerrError) as exc_info:
            create_project(client, invalid_payload)

        assert "Please enter email id in created_by" in str(exc_info.value)

        # Test invalid email without domain extension
        invalid_payload["created_by"] = "test@example"
        with pytest.raises(LabellerrError) as exc_info:
            create_project(client, invalid_payload)

        assert "Please enter email id in created_by" in str(exc_info.value)

    def test_invalid_annotation_guide(self, client, sample_valid_payload):
        """Test error handling for invalid annotation guide"""
        invalid_payload = sample_valid_payload.copy()

        # Missing option_type
        invalid_payload["annotation_guide"] = [{"question": "Test Question"}]
        with pytest.raises(LabellerrError) as exc_info:
            create_project(client, invalid_payload)

        assert "option_type is required in annotation_guide" in str(exc_info.value)

        # Invalid option_type
        invalid_payload["annotation_guide"] = [
            {"option_type": "invalid_type", "question": "Test Question"}
        ]
        with pytest.raises(LabellerrError) as exc_info:
            create_project(client, invalid_payload)

        assert "option_type must be one of" in str(exc_info.value)

    def test_both_upload_methods_specified(self, client, sample_valid_payload):
        """Test error when both files_to_upload and folder_to_upload are specified"""
        invalid_payload = sample_valid_payload.copy()
        invalid_payload["folder_to_upload"] = "/path/to/folder"

        with pytest.raises(LabellerrError) as exc_info:
            create_project(client, invalid_payload)

        assert "Cannot provide both files_to_upload and folder_to_upload" in str(
            exc_info.value
        )

    def test_no_upload_method_specified(self, client, sample_valid_payload):
        """Test error when neither files_to_upload nor folder_to_upload are specified"""
        invalid_payload = sample_valid_payload.copy()
        del invalid_payload["files_to_upload"]

        with pytest.raises(LabellerrError) as exc_info:
            create_project(client, invalid_payload)

        assert "Either files_to_upload or folder_to_upload must be provided" in str(
            exc_info.value
        )

    def test_empty_files_to_upload(self, client, sample_valid_payload):
        """Test error handling for empty files_to_upload"""
        invalid_payload = sample_valid_payload.copy()
        invalid_payload["files_to_upload"] = []
        with pytest.raises(LabellerrError):
            create_project(client, invalid_payload)

    def test_invalid_folder_to_upload(self, client, sample_valid_payload):
        """Test error handling for invalid folder_to_upload"""
        invalid_payload = sample_valid_payload.copy()
        del invalid_payload["files_to_upload"]
        invalid_payload["folder_to_upload"] = "   "

        with pytest.raises(LabellerrError) as exc_info:
            create_project(client, invalid_payload)

        assert "Folder path does not exist" in str(exc_info.value)


@pytest.mark.unit
class TestCreateUser:
    """Test cases for create_user method"""

    def test_create_user_missing_required_params(self, users):
        """Test error handling for missing required parameters"""
        from labellerr.schemas import CreateUserParams

        with pytest.raises(ValidationError) as exc_info:
            CreateUserParams(
                client_id="12345",
                first_name="John",
                last_name="Doe",
                # Missing email_id, projects, roles
            )

        assert (
            "field required" in str(exc_info.value).lower()
            or "missing" in str(exc_info.value).lower()
        )

    def test_create_user_invalid_client_id(self, users):
        """Test error handling for invalid client_id"""
        from labellerr.schemas import CreateUserParams

        with pytest.raises(ValidationError) as exc_info:
            CreateUserParams(
                client_id=12345,  # Not a string
                first_name="John",
                last_name="Doe",
                email_id="john@example.com",
                projects=["project_1"],
                roles=[{"project_id": "project_1", "role_id": 7}],
            )

        assert "client_id" in str(exc_info.value).lower()

    def test_create_user_empty_projects(self, users):
        """Test error handling for empty projects list"""
        from labellerr.schemas import CreateUserParams

        with pytest.raises(ValidationError) as exc_info:
            CreateUserParams(
                client_id="12345",
                first_name="John",
                last_name="Doe",
                email_id="john@example.com",
                projects=[],  # Empty list
                roles=[{"project_id": "project_1", "role_id": 7}],
            )

        assert "projects" in str(exc_info.value).lower()

    def test_create_user_empty_roles(self, users):
        """Test error handling for empty roles list"""
        from labellerr.schemas import CreateUserParams

        with pytest.raises(ValidationError) as exc_info:
            CreateUserParams(
                client_id="12345",
                first_name="John",
                last_name="Doe",
                email_id="john@example.com",
                projects=["project_1"],
                roles=[],  # Empty list
            )

        assert "roles" in str(exc_info.value).lower()


@pytest.mark.unit
class TestUpdateUserRole:
    """Test cases for update_user_role method"""

    def test_update_user_role_missing_required_params(self, users):
        """Test error handling for missing required parameters"""
        from labellerr.schemas import UpdateUserRoleParams

        with pytest.raises(ValidationError) as exc_info:
            UpdateUserRoleParams(
                client_id="12345",
                project_id="project_123",
                # Missing email_id, roles
            )

        assert (
            "field required" in str(exc_info.value).lower()
            or "missing" in str(exc_info.value).lower()
        )

    def test_update_user_role_invalid_client_id(self, users):
        """Test error handling for invalid client_id"""
        from labellerr.schemas import UpdateUserRoleParams

        with pytest.raises(ValidationError) as exc_info:
            UpdateUserRoleParams(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
                roles=[{"project_id": "project_1", "role_id": 7}],
            )

        assert "client_id" in str(exc_info.value).lower()

    def test_update_user_role_empty_roles(self, users):
        """Test error handling for empty roles list"""
        from labellerr.schemas import UpdateUserRoleParams

        with pytest.raises(ValidationError) as exc_info:
            UpdateUserRoleParams(
                client_id="12345",
                project_id="project_123",
                email_id="john@example.com",
                roles=[],  # Empty list
            )

        assert "roles" in str(exc_info.value).lower()


@pytest.mark.unit
class TestDeleteUser:
    """Test cases for delete_user method"""

    def test_delete_user_missing_required_params(self, users):
        """Test error handling for missing required parameters"""
        from labellerr.schemas import DeleteUserParams

        with pytest.raises(ValidationError) as exc_info:
            DeleteUserParams(
                client_id="12345",
                project_id="project_123",
                # Missing email_id, user_id
            )

        assert (
            "field required" in str(exc_info.value).lower()
            or "missing" in str(exc_info.value).lower()
        )

    def test_delete_user_invalid_client_id(self, users):
        """Test error handling for invalid client_id"""
        from labellerr.schemas import DeleteUserParams

        with pytest.raises(ValidationError) as exc_info:
            DeleteUserParams(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
                user_id="user_123",
            )

        assert "client_id" in str(exc_info.value).lower()

    def test_delete_user_invalid_project_id(self, users):
        """Test error handling for invalid project_id"""
        from labellerr.schemas import DeleteUserParams

        with pytest.raises(ValidationError) as exc_info:
            DeleteUserParams(
                client_id="12345",
                project_id=12345,  # Not a string
                email_id="john@example.com",
                user_id="user_123",
            )

        assert "project_id" in str(exc_info.value).lower()

    def test_delete_user_invalid_email_id(self, users):
        """Test error handling for invalid email_id"""
        from labellerr.schemas import DeleteUserParams

        with pytest.raises(ValidationError) as exc_info:
            DeleteUserParams(
                client_id="12345",
                project_id="project_123",
                email_id=12345,  # Not a string
                user_id="user_123",
            )

        assert "email_id" in str(exc_info.value).lower()

    def test_delete_user_invalid_user_id(self, users):
        """Test error handling for invalid user_id"""
        from labellerr.schemas import DeleteUserParams

        with pytest.raises(ValidationError) as exc_info:
            DeleteUserParams(
                client_id="12345",
                project_id="project_123",
                email_id="john@example.com",
                user_id=12345,  # Not a string
            )

        assert "user_id" in str(exc_info.value).lower()


@pytest.mark.unit
class TestAddUserToProject:
    """Test cases for add_user_to_project method"""

    def test_add_user_to_project_missing_required_params(self, users):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            users.add_user_to_project(
                project_id="project_123",
                # Missing email_id
            )

        assert (
            "missing" in str(exc_info.value).lower()
            or "required" in str(exc_info.value).lower()
        )

    def test_add_user_to_project_invalid_client_id(self, users):
        """Test error handling for invalid client_id - validation happens inside method"""
        from labellerr.schemas import AddUserToProjectParams

        with pytest.raises(ValidationError) as exc_info:
            AddUserToProjectParams(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
            )

        assert "client_id" in str(exc_info.value).lower()


@pytest.mark.unit
class TestRemoveUserFromProject:
    """Test cases for remove_user_from_project method"""

    def test_remove_user_from_project_missing_required_params(self, users):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            users.remove_user_from_project(
                project_id="project_123",
                # Missing email_id
            )

        assert (
            "missing" in str(exc_info.value).lower()
            or "required" in str(exc_info.value).lower()
        )

    def test_remove_user_from_project_invalid_client_id(self, users):
        """Test error handling for invalid client_id - validation happens inside method"""
        from labellerr.schemas import RemoveUserFromProjectParams

        with pytest.raises(ValidationError) as exc_info:
            RemoveUserFromProjectParams(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
            )

        assert "client_id" in str(exc_info.value).lower()


@pytest.mark.unit
class TestChangeUserRole:
    """Test cases for change_user_role method"""

    def test_change_user_role_missing_required_params(self, users):
        """Test error handling for missing required parameters"""
        with pytest.raises(TypeError) as exc_info:
            users.change_user_role(
                project_id="project_123",
                email_id="john@example.com",
                # Missing new_role_id
            )

        assert (
            "missing" in str(exc_info.value).lower()
            or "required" in str(exc_info.value).lower()
        )

    def test_change_user_role_invalid_client_id(self, users):
        """Test error handling for invalid client_id - validation happens inside method"""
        from labellerr.schemas import ChangeUserRoleParams

        with pytest.raises(ValidationError) as exc_info:
            ChangeUserRoleParams(
                client_id=12345,  # Not a string
                project_id="project_123",
                email_id="john@example.com",
                new_role_id="7",
            )

        assert "client_id" in str(exc_info.value).lower()


@pytest.mark.unit
class TestListAndBulkAssignFiles:
    """Tests for list_files and bulk_assign_files methods"""

    def test_list_files_missing_required(self, project):
        """Test list_files with missing required parameters"""
        with pytest.raises(TypeError):
            project.list_files()

    def test_bulk_assign_files_missing_required(self, project):
        """Test bulk_assign_files with missing required parameters"""
        with pytest.raises(TypeError):
            project.bulk_assign_files(new_status="None")


@pytest.mark.unit
class TestBulkAssignFiles:
    """Comprehensive tests for bulk_assign_files method"""

    def test_bulk_assign_files_invalid_client_id_type(self, project):
        """Test error handling for invalid client_id type - validation happens inside method"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id=12345,  # Not a string
                project_id="project_123",
                file_ids=["file1", "file2"],
                new_status="completed",
            )
        assert "client_id" in str(exc_info.value).lower()

    def test_bulk_assign_files_empty_client_id(self, project):
        """Test error handling for empty client_id"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id="",
                project_id="project_123",
                file_ids=["file1", "file2"],
                new_status="completed",
            )
        assert "client_id" in str(exc_info.value).lower()

    def test_bulk_assign_files_invalid_project_id_type(self, project):
        """Test error handling for invalid project_id type"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id="12345",
                project_id=12345,  # Not a string
                file_ids=["file1", "file2"],
                new_status="completed",
            )
        assert "project_id" in str(exc_info.value).lower()

    def test_bulk_assign_files_empty_project_id(self, project):
        """Test error handling for empty project_id"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id="12345",
                project_id="",
                file_ids=["file1", "file2"],
                new_status="completed",
            )
        assert "project_id" in str(exc_info.value).lower()

    def test_bulk_assign_files_empty_file_ids_list(self, project):
        """Test error handling for empty file_ids list"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id="12345",
                project_id="project_123",
                file_ids=[],  # Empty list
                new_status="completed",
            )
        assert "file_ids" in str(exc_info.value).lower()

    def test_bulk_assign_files_invalid_file_ids_type(self, project):
        """Test error handling for invalid file_ids type"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id="12345",
                project_id="project_123",
                file_ids="file1,file2",  # Not a list
                new_status="completed",
            )
        assert "file_ids" in str(exc_info.value).lower()

    def test_bulk_assign_files_invalid_new_status_type(self, project):
        """Test error handling for invalid new_status type"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id="12345",
                project_id="project_123",
                file_ids=["file1", "file2"],
                new_status=123,  # Not a string
            )
        assert "new_status" in str(exc_info.value).lower()

    def test_bulk_assign_files_empty_new_status(self, project):
        """Test error handling for empty new_status"""
        from labellerr.core.schemas import BulkAssignFilesParams

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignFilesParams(
                client_id="12345",
                project_id="project_123",
                file_ids=["file1", "file2"],
                new_status="",
            )
        assert "new_status" in str(exc_info.value).lower()

    def test_bulk_assign_files_single_file(self, project):
        """Test bulk assign with a single file - validation should pass"""
        from labellerr.core.schemas import BulkAssignFilesParams

        try:
            params = BulkAssignFilesParams(
                client_id="12345",
                project_id="project_123",
                file_ids=["file1"],
                new_status="completed",
            )
            assert params.file_ids == ["file1"]
        except ValidationError:
            pytest.fail("Validation should pass for single file")

    def test_bulk_assign_files_multiple_files(self, project):
        """Test bulk assign with multiple files - validation should pass"""
        from labellerr.core.schemas import BulkAssignFilesParams

        try:
            params = BulkAssignFilesParams(
                client_id="12345",
                project_id="project_123",
                file_ids=["file1", "file2", "file3", "file4", "file5"],
                new_status="in_progress",
            )
            assert len(params.file_ids) == 5
        except ValidationError:
            pytest.fail("Validation should pass for multiple files")

    def test_bulk_assign_files_special_characters_in_ids(self, project):
        """Test bulk assign with special characters in IDs - validation should pass"""
        from labellerr.core.schemas import BulkAssignFilesParams

        try:
            params = BulkAssignFilesParams(
                client_id="client-123_test",
                project_id="project-456_test",
                file_ids=["file-1_test", "file-2_test"],
                new_status="pending",
            )
            assert params.client_id == "client-123_test"
        except ValidationError:
            pytest.fail("Validation should pass for IDs with special characters")


@pytest.mark.unit
class TestListFiles:
    """Comprehensive tests for list_files method"""

    def test_list_files_invalid_client_id_type(self, project):
        """Test error handling for invalid client_id type - validation happens inside method"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id=12345,  # Not a string
                project_id="project_123",
                search_queries={"status": "completed"},
            )
        assert "client_id" in str(exc_info.value).lower()

    def test_list_files_empty_client_id(self, project):
        """Test error handling for empty client_id"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id="",
                project_id="project_123",
                search_queries={"status": "completed"},
            )
        assert "client_id" in str(exc_info.value).lower()

    def test_list_files_invalid_project_id_type(self, project):
        """Test error handling for invalid project_id type"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id="12345",
                project_id=12345,  # Not a string
                search_queries={"status": "completed"},
            )
        assert "project_id" in str(exc_info.value).lower()

    def test_list_files_empty_project_id(self, project):
        """Test error handling for empty project_id"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id="12345",
                project_id="",
                search_queries={"status": "completed"},
            )
        assert "project_id" in str(exc_info.value).lower()

    def test_list_files_invalid_search_queries_type(self, project):
        """Test error handling for invalid search_queries type"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries="status:completed",  # Not a dict
            )
        assert "search_queries" in str(exc_info.value).lower()

    def test_list_files_invalid_size_type(self, project):
        """Test error handling for invalid size type"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={"status": "completed"},
                size="invalid",  # Non-numeric string
            )
        assert "size" in str(exc_info.value).lower()

    def test_list_files_negative_size(self, project):
        """Test error handling for negative size"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={"status": "completed"},
                size=-1,
            )
        assert "size" in str(exc_info.value).lower()

    def test_list_files_zero_size(self, project):
        """Test error handling for zero size"""
        from labellerr.core.schemas import ListFileParams

        with pytest.raises(ValidationError) as exc_info:
            ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={"status": "completed"},
                size=0,
            )
        assert "size" in str(exc_info.value).lower()

    def test_list_files_with_default_size(self, project):
        """Test list_files with default size parameter - validation should pass"""
        from labellerr.core.schemas import ListFileParams

        try:
            params = ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={"status": "completed"},
            )
            assert params.size == 10  # Default value
        except ValidationError:
            pytest.fail("Validation should pass with default size")

    def test_list_files_with_custom_size(self, project):
        """Test list_files with custom size parameter - validation should pass"""
        from labellerr.core.schemas import ListFileParams

        try:
            params = ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={"status": "completed"},
                size=50,
            )
            assert params.size == 50
        except ValidationError:
            pytest.fail("Validation should pass with custom size")

    def test_list_files_with_next_search_after(self, project):
        """Test list_files with next_search_after for pagination - validation should pass"""
        from labellerr.core.schemas import ListFileParams

        try:
            params = ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={"status": "completed"},
                size=10,
                next_search_after="some_cursor_value",
            )
            assert params.next_search_after == "some_cursor_value"
        except ValidationError:
            pytest.fail("Validation should pass with next_search_after")

    def test_list_files_complex_search_queries(self, project):
        """Test list_files with complex search queries - validation should pass"""
        from labellerr.core.schemas import ListFileParams

        try:
            params = ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={
                    "status": "completed",
                    "created_at": {"gte": "2024-01-01"},
                    "tags": ["tag1", "tag2"],
                },
            )
            assert "status" in params.search_queries
        except ValidationError:
            pytest.fail("Validation should pass with complex search queries")

    def test_list_files_empty_search_queries(self, project):
        """Test list_files with empty search queries dict - validation should pass"""
        from labellerr.core.schemas import ListFileParams

        try:
            params = ListFileParams(
                client_id="12345",
                project_id="project_123",
                search_queries={},  # Empty dict
            )
            assert params.search_queries == {}
        except ValidationError:
            pytest.fail("Validation should pass with empty search queries")


if __name__ == "__main__":
    pytest.main()
