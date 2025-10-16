"""
Example usage of bulk assign integration tests.

This script demonstrates how to use the bulk assign integration tests
with real API credentials.
"""

import os
import sys

# Add the root directory to Python path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(root_dir)

from Bulk_Assign_Operations import (
    test_bulk_assign_files,
    test_bulk_assign_single_file,
    test_list_files_by_status,
    test_list_files_with_pagination,
    test_list_then_bulk_assign_workflow,
    test_search_with_filters,
)


def example_basic_list_files():
    """Example: List files in a project"""
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Basic List Files")
    print("=" * 60)

    # Import credentials
    try:
        import cred

        api_key = cred.API_KEY
        api_secret = cred.API_SECRET
        client_id = cred.CLIENT_ID
        project_id = cred.PROJECT_ID
    except ImportError:
        print("Error: Please configure credentials in cred.py")
        return

    # List files
    result = test_list_files_by_status(api_key, api_secret, client_id, project_id)

    if result:
        print("\n✓ Successfully listed files!")
        # You can now work with the result
        files = result.get("files", [])
        print(f"Number of files: {len(files)}")


def example_bulk_assign_workflow():
    """Example: Complete bulk assign workflow"""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Bulk Assign Workflow")
    print("=" * 60)

    try:
        import cred

        api_key = cred.API_KEY
        api_secret = cred.API_SECRET
        client_id = cred.CLIENT_ID
        project_id = cred.PROJECT_ID
    except ImportError:
        print("Error: Please configure credentials in cred.py")
        return

    # Step 1: List files
    print("\nStep 1: Listing files to get file IDs...")
    result = test_list_files_by_status(api_key, api_secret, client_id, project_id)

    if not result or "files" not in result:
        print("No files found or error occurred")
        return

    # Step 2: Extract file IDs
    files = result.get("files", [])
    file_ids = [f["id"] for f in files if "id" in f][:3]  # Take first 3 files

    if not file_ids:
        print("No file IDs found in response")
        return

    print(f"\nStep 2: Found {len(file_ids)} files to assign")

    # Step 3: Bulk assign to new status
    print("\nStep 3: Bulk assigning files to 'annotation' status...")
    assign_result = test_bulk_assign_files(
        api_key, api_secret, client_id, project_id, file_ids, "annotation"
    )

    if assign_result:
        print("\n✓ Workflow completed successfully!")


def example_progressive_pipeline():
    """Example: Move files through pipeline stages"""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Progressive Pipeline")
    print("=" * 60)

    try:
        import cred

        api_key = cred.API_KEY
        api_secret = cred.API_SECRET
        client_id = cred.CLIENT_ID
        project_id = cred.PROJECT_ID
    except ImportError:
        print("Error: Please configure credentials in cred.py")
        return

    # Move files from pending to annotation
    print("\nMoving files from 'pending' to 'annotation'...")
    result = test_list_then_bulk_assign_workflow(
        api_key, api_secret, client_id, project_id, "pending", "annotation"
    )

    if result:
        print("\n✓ Pipeline stage completed!")


def example_pagination():
    """Example: Paginate through large file lists"""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Pagination")
    print("=" * 60)

    try:
        import cred

        api_key = cred.API_KEY
        api_secret = cred.API_SECRET
        client_id = cred.CLIENT_ID
        project_id = cred.PROJECT_ID
    except ImportError:
        print("Error: Please configure credentials in cred.py")
        return

    # Test pagination
    result = test_list_files_with_pagination(api_key, api_secret, client_id, project_id)

    if result:
        print("\n✓ Pagination test completed!")


def example_single_file():
    """Example: Bulk assign a single file"""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Single File Assignment")
    print("=" * 60)

    try:
        import cred

        api_key = cred.API_KEY
        api_secret = cred.API_SECRET
        client_id = cred.CLIENT_ID
        project_id = cred.PROJECT_ID
    except ImportError:
        print("Error: Please configure credentials in cred.py")
        return

    # First get a file ID
    result = test_list_files_by_status(api_key, api_secret, client_id, project_id)

    if not result or "files" not in result:
        print("No files found")
        return

    files = result.get("files", [])
    if not files:
        print("No files available")
        return

    file_id = files[0].get("id")
    if not file_id:
        print("No file ID found")
        return

    # Assign single file
    print(f"\nAssigning single file: {file_id}")
    assign_result = test_bulk_assign_single_file(
        api_key, api_secret, client_id, project_id, file_id, "review"
    )

    if assign_result:
        print("\n✓ Single file assignment completed!")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print(" BULK ASSIGN OPERATIONS - EXAMPLE USAGE")
    print("=" * 80)
    print("\nThis script demonstrates various ways to use the bulk assign")
    print("integration tests. Make sure to configure credentials in cred.py")
    print("\nAvailable examples:")
    print("  1. Basic list files")
    print("  2. Bulk assign workflow")
    print("  3. Progressive pipeline")
    print("  4. Pagination")
    print("  5. Single file assignment")
    print("\n" + "=" * 80)

    # Check if credentials are configured
    try:
        import cred

        if not all([cred.API_KEY, cred.API_SECRET, cred.CLIENT_ID, cred.PROJECT_ID]):
            print("\n⚠ Warning: Credentials not configured in cred.py")
            print("Please edit tests/integration/cred.py to add your credentials")
            sys.exit(1)
    except ImportError:
        print("\n⚠ Warning: cred.py not found")
        print("Please create tests/integration/cred.py with your credentials")
        sys.exit(1)

    # Run examples (uncomment the ones you want to run)
    print("\n\nRunning examples...")

    # Uncomment to run specific examples:
    example_basic_list_files()
    # example_bulk_assign_workflow()
    # example_progressive_pipeline()
    # example_pagination()
    # example_single_file()

    print("\n" + "=" * 80)
    print(" EXAMPLES COMPLETED")
    print("=" * 80)
    print(
        "\nTo run other examples, edit this file and uncomment the example functions."
    )
    print("\n")
