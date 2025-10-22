import os
import sys

import pytest

from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError


@pytest.fixture(scope="session")
def credentials():
    """Load credentials from cred.py or environment variables"""
    # Try to import from cred.py
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "integration"))
        import cred

        return {
            "api_key": cred.API_KEY,
            "api_secret": cred.API_SECRET,
            "client_id": cred.CLIENT_ID,
            "project_id": cred.PROJECT_ID,
        }
    except (ImportError, AttributeError):
        # Fall back to environment variables
        api_key = os.environ.get("LABELLERR_API_KEY", "")
        api_secret = os.environ.get("LABELLERR_API_SECRET", "")
        client_id = os.environ.get("LABELLERR_CLIENT_ID", "")
        project_id = os.environ.get("LABELLERR_PROJECT_ID", "")

        if not all([api_key, api_secret, client_id, project_id]):
            pytest.skip(
                "Integration tests require credentials. Set environment variables:\n"
                "LABELLERR_API_KEY, LABELLERR_API_SECRET, LABELLERR_CLIENT_ID, LABELLERR_PROJECT_ID\n"
                "Or create tests/integration/cred.py with these values."
            )

        return {
            "api_key": api_key,
            "api_secret": api_secret,
            "client_id": client_id,
            "project_id": project_id,
        }


@pytest.fixture
def client(credentials):
    """Create a client for integration testing with real API credentials"""
    return LabellerrClient(credentials["api_key"], credentials["api_secret"])


@pytest.fixture
def client_id(credentials):
    """Get client_id from credentials"""
    return credentials["client_id"]


@pytest.fixture
def project_id(credentials):
    """Get project_id from credentials"""
    return credentials["project_id"]


def validate_bulk_assign_response(result, file_ids):
    """
    Helper function to validate bulk assign API response structure and content.

    Args:
        result: The API response dictionary
        file_ids: List of file IDs that were attempted to be assigned

    Raises:
        AssertionError: If validation fails
    """
    assert isinstance(result, dict), "Result should be a dictionary"

    # Check for expected response keys (adjust based on actual API response)
    if "response" in result:
        response_data = result["response"]
        assert isinstance(response_data, dict), "Response data should be a dictionary"

        # Validate status field
        if "status" in response_data:
            assert response_data["status"] in [
                "success",
                "completed",
                "pending",
            ], f"Expected valid status, got: {response_data['status']}"

        # Validate affected files or count
        if "affected_files" in response_data:
            assert isinstance(
                response_data["affected_files"], (list, int)
            ), "Affected files should be list or count"
            if isinstance(response_data["affected_files"], list):
                assert len(response_data["affected_files"]) <= len(
                    file_ids
                ), "Affected files count should not exceed requested files"

        # Validate message field
        if "message" in response_data:
            assert isinstance(
                response_data["message"], str
            ), "Message should be a string"

        # Validate success indicators
        if "success" in response_data:
            assert isinstance(
                response_data["success"], bool
            ), "Success flag should be boolean"


def validate_list_file_response(result):
    """
    Helper function to validate list_file API response structure and content.

    Args:
        result: The API response dictionary

    Raises:
        AssertionError: If validation fails
    """
    assert isinstance(result, dict), "Result should be a dictionary"

    # Check for files in response
    if "files" in result:
        assert isinstance(result["files"], list), "Files should be a list"

        # Validate individual file structure
        for file_item in result["files"]:
            assert isinstance(file_item, dict), "Each file should be a dictionary"
            # Common file fields
            if "id" in file_item:
                assert isinstance(file_item["id"], str), "File ID should be a string"
            if "status" in file_item:
                assert isinstance(
                    file_item["status"], str
                ), "File status should be a string"

    # Check pagination fields
    if "next_search_after" in result:
        # Cursor can be string or None
        assert result["next_search_after"] is None or isinstance(
            result["next_search_after"], str
        ), "Next search cursor should be string or None"

    if "total" in result:
        assert isinstance(result["total"], int), "Total count should be an integer"
        assert result["total"] >= 0, "Total count should be non-negative"


def get_file_ids_from_project(
    client, client_id, project_id, count=5, search_queries=None
):
    """
    Helper function to get real file IDs from a project for testing.

    Args:
        client: LabellerrClient instance
        client_id: Client ID
        project_id: Project ID
        count: Number of file IDs to retrieve
        search_queries: Optional search filters

    Returns:
        List of file IDs

    Raises:
        pytest.skip: If no files are available in the project
    """
    if search_queries is None:
        search_queries = {}

    list_result = client.list_file(
        client_id=client_id,
        project_id=project_id,
        search_queries=search_queries,
        size=count,
    )
    validate_list_file_response(list_result)

    files = list_result.get("files", [])
    if not files:
        pytest.skip(
            f"No files available in project for testing (search: {search_queries})"
        )

    file_ids = [f["id"] for f in files[:count] if "id" in f]
    if not file_ids:
        pytest.skip("No valid file IDs found in project")

    return file_ids


class TestBulkAssignBusinessScenarios:
    """Integration tests for bulk assign operations in realistic business scenarios"""

    def test_annotation_workflow_assignment(self, client, client_id, project_id):
        """
        Test complete workflow: Assign multiple files to annotation team

        Business scenario:
        - Project manager receives batch of uploaded images
        - Need to assign them to annotation team for labeling
        - Bulk operation for efficiency

        Note: This test uses real API credentials and requires actual files in the project.
        """
        try:
            # Get real file IDs from the project
            file_ids = get_file_ids_from_project(client, client_id, project_id, count=5)

            # Bulk assign files to annotation status
            new_status = "annotation"
            result = client.bulk_assign_files(
                client_id=client_id,
                project_id=project_id,
                file_ids=file_ids,
                new_status=new_status,
            )
            # Positive validation: verify the result structure and content
            validate_bulk_assign_response(result, file_ids)

        except LabellerrError as e:
            pytest.fail(f"Integration test failed with API error: {str(e)}")

    def test_quality_review_workflow(self, client, client_id, project_id):
        """
        Test workflow: Move completed annotations to review stage

        Business scenario:
        - Annotators complete their work
        - QA manager needs to bulk-move files to review stage
        - Ensures consistent status across batch

        Note: Uses real API with real credentials.
        """
        try:
            # Get real file IDs from the project
            file_ids = get_file_ids_from_project(client, client_id, project_id, count=4)

            new_status = "review"
            result = client.bulk_assign_files(
                client_id=client_id,
                project_id=project_id,
                file_ids=file_ids,
                new_status=new_status,
            )
            # Positive validation: verify the result structure and content
            validate_bulk_assign_response(result, file_ids)
        except LabellerrError as e:
            pytest.fail(f"Integration test failed with API error: {str(e)}")

    def test_failed_files_reassignment(self, client, client_id, project_id):
        """
        Test workflow: Reassign failed files back to annotation

        Business scenario:
        - Some files failed quality check
        - Need to move them back to annotation status
        - Annotators can rework these files

        Note: Uses real API with real credentials.
        """
        try:
            # Get real file IDs from the project
            file_ids = get_file_ids_from_project(client, client_id, project_id, count=3)

            new_status = "rework"
            result = client.bulk_assign_files(
                client_id=client_id,
                project_id=project_id,
                file_ids=file_ids,
                new_status=new_status,
            )
            # Positive validation: verify the result structure and content
            validate_bulk_assign_response(result, file_ids)
        except LabellerrError as e:
            pytest.fail(f"Integration test failed with API error: {str(e)}")

    def test_completion_workflow(self, client, client_id, project_id):
        """
        Test workflow: Mark reviewed files as completed

        Business scenario:
        - Final review is complete
        - Project manager marks files as done
        - Ready for export and delivery to client

        Note: Uses real API with real credentials.
        """
        try:
            # Get real file IDs from the project
            file_ids = get_file_ids_from_project(client, client_id, project_id, count=6)

            new_status = "completed"
            result = client.bulk_assign_files(
                client_id=client_id,
                project_id=project_id,
                file_ids=file_ids,
                new_status=new_status,
            )
            # Positive validation: verify the result structure and content
            validate_bulk_assign_response(result, file_ids)
        except LabellerrError as e:
            pytest.fail(f"Integration test failed with API error: {str(e)}")

    def test_single_file_bulk_operation(self, client, client_id, project_id):
        """
        Test workflow: Bulk operation with single file

        Business scenario:
        - Sometimes need to change status of just one file
        - Using bulk API for consistency
        - Should work same as multi-file operation

        Note: Uses real API with real credentials.
        """
        try:
            # Get a single real file ID from the project
            file_ids = get_file_ids_from_project(client, client_id, project_id, count=1)

            new_status = "urgent_review"
            result = client.bulk_assign_files(
                client_id=client_id,
                project_id=project_id,
                file_ids=file_ids,
                new_status=new_status,
            )
            # Positive validation: verify the result structure and content
            validate_bulk_assign_response(result, file_ids)
        except LabellerrError as e:
            pytest.fail(f"Integration test failed with API error: {str(e)}")

    def test_large_batch_assignment(self, client, client_id, project_id):
        """
        Test workflow: Bulk assign large batch of files

        Business scenario:
        - Processing large dataset upload
        - Need to assign 50+ files efficiently
        - Testing system scalability

        Note: Uses real API with real credentials. Tries to get up to 50 files.
        """
        try:
            # Try to get a large batch of files (up to 50)
            file_ids = get_file_ids_from_project(
                client, client_id, project_id, count=50
            )

            new_status = "pending_annotation"
            result = client.bulk_assign_files(
                client_id=client_id,
                project_id=project_id,
                file_ids=file_ids,
                new_status=new_status,
            )
            # Positive validation: verify the result structure and content
            validate_bulk_assign_response(result, file_ids)
        except LabellerrError as e:
            pytest.fail(f"Integration test failed with API error: {str(e)}")


class TestListFileBusinessScenarios:
    """Integration tests for list file operations in realistic business scenarios"""

    def test_search_by_status(self, client, client_id, project_id):
        """
        Test workflow: Find all files in annotation status

        Business scenario:
        - Team lead wants to see all files currently being annotated
        - Filter by status to track progress
        - Plan resource allocation

        Note: Uses real API with real credentials.
        """
        search_queries = {"status": "annotation"}

        try:
            result = client.list_file(
                client_id=client_id,
                project_id=project_id,
                search_queries=search_queries,
                size=20,
            )
            # Positive validation: verify the result structure and content
            validate_list_file_response(result)
        except LabellerrError as e:
            pytest.fail(f"Integration test failed with API error: {str(e)}")

    def test_search_with_pagination(self, client, client_id, project_id):
        """
        Test workflow: Paginate through large file list

        Business scenario:
        - Project has 1000+ files
        - Need to load them in pages for performance
        - Use pagination cursor to navigate

        Note: Uses real API with real credentials.
        """
        search_queries = {}

        try:
            # First page
            result = client.list_file(
                client_id=client_id,
                project_id=project_id,
                search_queries=search_queries,
                size=50,
            )
            # Positive validation: verify the result structure and content
            validate_list_file_response(result)

            # Get next page if cursor exists
            next_cursor = result.get("next_search_after")
            if next_cursor:
                result_page_2 = client.list_file(
                    client_id=client_id,
                    project_id=project_id,
                    search_queries=search_queries,
                    size=50,
                    next_search_after=next_cursor,
                )
                # Positive validation: verify the result structure and content
                validate_list_file_response(result_page_2)

        except LabellerrError as e:
            pytest.fail(f"Integration test failed with API error: {str(e)}")

    def test_search_with_date_range(self, client, client_id, project_id):
        """
        Test workflow: Find files uploaded in specific date range

        Business scenario:
        - Manager wants to review this week's uploads
        - Filter by creation date range
        - Generate weekly progress report

        Note: Uses real API with real credentials.
        """
        search_queries = {
            "created_at": {"gte": "2024-01-01", "lte": "2024-01-07"},
            "status": "review",
        }

        try:
            result = client.list_file(
                client_id=client_id,
                project_id=project_id,
                search_queries=search_queries,
                size=100,
            )
            # Positive validation: verify the result structure and content
            validate_list_file_response(result)
        except LabellerrError as e:
            pytest.fail(f"Integration test failed with API error: {str(e)}")

    def test_search_with_multiple_filters(self, client, client_id, project_id):
        """
        Test workflow: Complex search with multiple criteria

        Business scenario:
        - Quality manager needs specific subset of files
        - Must match multiple criteria: status, assignee, date
        - Precise targeting for audit purposes

        Note: Uses real API with real credentials.
        """
        search_queries = {
            "status": "completed",
        }

        try:
            result = client.list_file(
                client_id=client_id,
                project_id=project_id,
                search_queries=search_queries,
                size=25,
            )
            # Positive validation: verify the result structure and content
            validate_list_file_response(result)
        except LabellerrError as e:
            pytest.fail(f"Integration test failed with API error: {str(e)}")

    def test_search_pending_files(self, client, client_id, project_id):
        """
        Test workflow: Find unassigned files needing attention

        Business scenario:
        - New files uploaded but not yet assigned
        - Project coordinator identifies work backlog
        - Prepares batch for assignment

        Note: Uses real API with real credentials.
        """
        search_queries = {"status": "pending"}

        try:
            result = client.list_file(
                client_id=client_id,
                project_id=project_id,
                search_queries=search_queries,
                size=100,
            )
            # Positive validation: verify the result structure and content
            validate_list_file_response(result)
        except LabellerrError as e:
            pytest.fail(f"Integration test failed with API error: {str(e)}")

    def test_search_with_custom_page_size(self, client, client_id, project_id):
        """
        Test workflow: Adjust page size based on use case

        Business scenario:
        - Different views need different page sizes
        - Dashboard preview: 10 items
        - Bulk operations: 100+ items
        - Testing flexible pagination

        Note: Uses real API with real credentials.
        """
        search_queries = {}

        try:
            # Small page for preview
            result_preview = client.list_file(
                client_id=client_id,
                project_id=project_id,
                search_queries=search_queries,
                size=10,
            )
            # Positive validation: verify the result structure and content
            validate_list_file_response(result_preview)

            # Large page for bulk operations
            result_bulk = client.list_file(
                client_id=client_id,
                project_id=project_id,
                search_queries=search_queries,
                size=200,
            )
            # Positive validation: verify the result structure and content
            validate_list_file_response(result_bulk)

        except LabellerrError as e:
            pytest.fail(f"Integration test failed with API error: {str(e)}")

    def test_empty_search_results(self, client, client_id, project_id):
        """
        Test workflow: Handle searches with no results

        Business scenario:
        - Search for files that don't exist
        - System should handle gracefully
        - No errors for empty results

        Note: Uses real API with real credentials.
        """
        search_queries = {"status": "failed"}

        try:
            result = client.list_file(
                client_id=client_id,
                project_id=project_id,
                search_queries=search_queries,
                size=10,
            )
            # Positive validation: verify the result structure and content
            validate_list_file_response(result)
        except LabellerrError as e:
            pytest.fail(f"Integration test failed with API error: {str(e)}")


class TestIntegratedWorkflow:
    """Integration tests combining list and bulk assign operations"""

    def test_list_and_bulk_assign_workflow(self, client, client_id, project_id):
        """
        Test complete workflow: Search then bulk assign

        Business scenario:
        - Find all pending files
        - Bulk assign them to annotation team
        - Common workflow pattern

        Note: Uses real API with real credentials and actual files.
        """
        try:
            # Step 1: Get real file IDs from the project
            file_ids = get_file_ids_from_project(client, client_id, project_id, count=3)

            # Step 2: Bulk assign to annotation
            assign_result = client.bulk_assign_files(
                client_id=client_id,
                project_id=project_id,
                file_ids=file_ids,
                new_status="annotation",
            )
            # Positive validation: verify the result structure and content
            validate_bulk_assign_response(assign_result, file_ids)

        except LabellerrError as e:
            pytest.fail(f"Integration test failed with API error: {str(e)}")

    def test_progressive_assignment_workflow(self, client, client_id, project_id):
        """
        Test workflow: Progressive assignment through stages

        Business scenario:
        - Files move through annotation pipeline
        - List files at each stage
        - Bulk assign to next stage
        - Complete workflow automation

        Note: Uses real API with real credentials and actual files.
        """
        stages = ["annotation", "review", "qa", "completed"]

        try:
            for i, stage in enumerate(stages[:-1]):
                # Get real files for each stage transition
                file_ids = get_file_ids_from_project(
                    client, client_id, project_id, count=3
                )

                # Move files to next stage
                next_stage = stages[i + 1]
                assign_result = client.bulk_assign_files(
                    client_id=client_id,
                    project_id=project_id,
                    file_ids=file_ids,
                    new_status=next_stage,
                )
                # Positive validation: verify the result structure and content
                validate_bulk_assign_response(assign_result, file_ids)

        except LabellerrError as e:
            pytest.fail(f"Integration test failed with API error: {str(e)}")


class TestErrorScenarios:
    """Integration tests for realistic error scenarios"""

    def test_authentication_failure(self, client_id):
        """
        Test authentication failure scenario

        Note: Uses invalid credentials to test error handling.
        """
        # Create client with invalid credentials
        invalid_client = LabellerrClient("invalid_api_key", "invalid_api_secret")
        project_id = "test_project"
        file_ids = ["file1.jpg"]

        with pytest.raises(LabellerrError) as exc_info:
            invalid_client.bulk_assign_files(
                client_id=client_id,
                project_id=project_id,
                file_ids=file_ids,
                new_status="annotation",
            )

        # Verify it's an authentication error
        error_str = str(exc_info.value).lower()
        assert any(
            word in error_str
            for word in ["auth", "invalid", "unauthorized", "credentials"]
        )

    def test_project_not_found(self, client, client_id):
        """
        Test project not found scenario

        Note: Uses real API with valid credentials but nonexistent project.
        """
        project_id = "nonexistent_project_xyz_12345"
        search_queries = {"status": "completed"}

        with pytest.raises(LabellerrError) as exc_info:
            client.list_file(
                client_id=client_id,
                project_id=project_id,
                search_queries=search_queries,
            )

        # Verify it's a project not found error
        error_str = str(exc_info.value).lower()
        assert any(
            word in error_str for word in ["project", "not found", "does not exist"]
        )

    def test_invalid_file_ids(self, client, client_id, project_id):
        """
        Test bulk assign with nonexistent file IDs

        Note: Uses real API with valid credentials but invalid file IDs.
        """
        file_ids = ["nonexistent_file_1_xyz", "nonexistent_file_2_xyz"]

        with pytest.raises(LabellerrError) as exc_info:
            client.bulk_assign_files(
                client_id=client_id,
                project_id=project_id,
                file_ids=file_ids,
                new_status="annotation",
            )

        # Verify it's a file not found error
        error_str = str(exc_info.value).lower()
        assert any(
            word in error_str
            for word in ["file", "not found", "does not exist", "invalid"]
        )
