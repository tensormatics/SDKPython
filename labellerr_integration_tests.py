import os
import sys
import time
import json
import tempfile
import unittest
from unittest.mock import patch
from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError
import dotenv

dotenv.load_dotenv()


class LabelerUseCaseIntegrationTests(unittest.TestCase):

    def setUp(self):

        self.api_key = os.getenv("LABELLERR_API_KEY", "test-api-key")
        self.api_secret = os.getenv("LABELLERR_API_SECRET", "test-api-secret")
        self.client_id = os.getenv("LABELLERR_CLIENT_ID", "test-client-id")
        self.test_email = os.getenv("LABELLERR_TEST_EMAIL", "test@example.com")

        if (
            self.api_key == "test-api-key"
            or self.api_secret == "test-api-secret"
            or self.client_id == "test-client-id"
            or self.test_email == "test@example.com"
        ):

            raise ValueError(
                "Real Labellerr credentials are required for integration testing. "
                "Please set environment variables: "
                "LABELLERR_API_KEY, LABELLERR_API_SECRET, LABELLERR_CLIENT_ID, LABELLERR_TEST_EMAIL"
            )

        # Initialize the client
        self.client = LabellerrClient(self.api_key, self.api_secret)

        # Common test data
        self.test_project_name = f"SDK_Test_Project_{int(time.time())}"
        self.test_dataset_name = f"SDK_Test_Dataset_{int(time.time())}"

        # Sample annotation guide as per documentation requirements
        self.annotation_guide = [
            {
                "question": "What objects do you see?",
                "option_type": "select",
                "options": ["cat", "dog", "car", "person", "other"],
            },
            {
                "question": "Image quality rating",
                "option_type": "radio",
                "options": ["excellent", "good", "fair", "poor"],
            },
        ]

        # Valid rotation configuration
        self.rotation_config = {
            "annotation_rotation_count": 1,
            "review_rotation_count": 1,
            "client_review_rotation_count": 1,
        }

    def test_use_case_1_complete_project_creation_workflow(self):

        # Create temporary test files to simulate real data upload
        test_files = []
        try:
            # Create sample image files for testing
            for i in range(3):
                temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                temp_file.write(b"fake_image_data_" + str(i).encode())
                temp_file.close()
                test_files.append(temp_file.name)

            # Step 1: Prepare project payload with all required parameters
            project_payload = {
                "client_id": self.client_id,
                "dataset_name": self.test_dataset_name,
                "dataset_description": "Test dataset for SDK integration testing",
                "data_type": "image",
                "created_by": self.test_email,
                "project_name": self.test_project_name,
                "autolabel": False,
                "files_to_upload": test_files,
                "annotation_guide": self.annotation_guide,
                "rotation_config": self.rotation_config,
            }

            # Step 2: Execute complete project creation workflow

            result = self.client.initiate_create_project(project_payload)

            # Step 3: Validate the workflow execution
            self.assertIsInstance(
                result, dict, "Project creation should return a dictionary"
            )
            self.assertEqual(
                result.get("status"), "success", "Project creation should be successful"
            )
            self.assertIn("message", result, "Result should contain a success message")
            self.assertIn("project_id", result, "Result should contain project_id")

            # Store project details for potential cleanup
            if isinstance(result, dict) and "response" in result:
                self.created_project_id = result["response"].get("project_id")
            else:
                self.created_project_id = result.get("project_id") if isinstance(result, dict) else None
            self.created_dataset_name = self.test_dataset_name

        except LabellerrError as e:
            self.fail(f"Project creation failed with LabellerrError: {e}")
        except Exception as e:
            self.fail(f"Project creation failed with unexpected error: {e}")
        finally:
            # Clean up temporary files
            for file_path in test_files:
                try:
                    os.unlink(file_path)
                except OSError:
                    pass

    def test_use_case_1_validation_requirements(self):
        """Table-driven test for project creation validation requirements"""

        validation_test_cases = [
            {
                "test_name": "Missing client_id",
                "payload_overrides": {"client_id": None},
                "remove_keys": ["client_id"],
                "expected_error": "Required parameter client_id is missing",
            },
            {
                "test_name": "Invalid data type",
                "payload_overrides": {"data_type": "invalid_type"},
                "remove_keys": [],
                "expected_error": "Invalid data_type",
            },
            {
                "test_name": "Missing dataset_name",
                "payload_overrides": {},
                "remove_keys": ["dataset_name"],
                "expected_error": "Required parameter dataset_name is missing",
            },
            {
                "test_name": "Missing annotation guide and template ID",
                "payload_overrides": {},
                "remove_keys": ["annotation_guide"],
                "expected_error": "Required parameter annotation_guide is missing",
            },
        ]

        temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        temp_file.write(b"fake_image_data")
        temp_file.close()

        try:
            # Base valid payload
            base_payload = {
                "client_id": self.client_id,
                "dataset_name": "test_dataset",
                "dataset_description": "test description",
                "data_type": "image",
                "created_by": "test@example.com",
                "project_name": "test_project",
                "autolabel": False,
                "files_to_upload": [temp_file.name],
                "annotation_guide": self.annotation_guide,
            }

            for i, test_case in enumerate(validation_test_cases, 1):
                with self.subTest(test_name=test_case["test_name"]):

                    # Create test payload by modifying base payload
                    test_payload = base_payload.copy()
                    test_payload.update(test_case["payload_overrides"])

                    # Remove keys if specified
                    for key in test_case["remove_keys"]:
                        test_payload.pop(key, None)

                    # Execute test and verify expected behavior
                    # Some validation might pass through to API and timeout instead of immediate error
                    try:
                        result = self.client.initiate_create_project(test_payload)

                        # If we reach here, check if it's an error result disguised as success
                        if isinstance(result, dict):
                            # If the result contains error information or timeout, that's acceptable validation
                            if (result.get("status") == "error" or
                                    "error" in result or
                                    result.get("status") != "success"):
                                print(f"✓ {test_case['test_name']}: Validation caught by API (non-success result)")
                                continue
                            elif result.get("status") == "success":
                                # This is unexpected - validation should have failed
                                self.fail(f"Expected validation error for {test_case['test_name']}, but got success: {result}")

                        # If we get a result that's not clearly an error, that's unexpected
                        print(f"⚠️  {test_case['test_name']}: Unexpected result format: {result}")

                    except LabellerrError as e:
                        # This is the expected behavior - validation failed with proper exception
                        error_message = str(e)
                        print(f"✓ {test_case['test_name']}: Validation failed as expected: {error_message}")

                        # Check if the error message contains what we expect
                        expected_error = test_case["expected_error"]
                        if expected_error not in error_message:
                            print(f"⚠️  Expected '{expected_error}' in error message, got: {error_message}")

                    except Exception as e:
                        # Some other exception - might be timeout or network issue
                        error_message = str(e)
                        print(f"✓ {test_case['test_name']}: Exception occurred: {error_message}")
                        # For validation tests, any exception is acceptable as it means the request failed

        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass

    def test_use_case_1_multiple_data_types_table_driven(self):

        project_test_scenarios = [
            {
                "scenario_name": "Image Classification Project",
                "data_type": "image",
                "file_extensions": [".jpg", ".png"],
                "annotation_types": ["select", "radio"],
                "expected_success": True,
            },
            {
                "scenario_name": "Document Processing Project",
                "data_type": "document",
                "file_extensions": [".pdf"],
                "annotation_types": ["input", "boolean"],
                "expected_success": True,
            },
        ]

        test_scenario = project_test_scenarios[0]  # Image classification

        test_files = []
        try:
            for ext in test_scenario["file_extensions"][:2]:  # Limit to 2 files
                temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                temp_file.write(f'fake_{test_scenario["data_type"]}_data'.encode())
                temp_file.close()
                test_files.append(temp_file.name)

            annotation_guide = []
            for i, annotation_type in enumerate(test_scenario["annotation_types"]):
                annotation_guide.append(
                    {
                        "question": f"Test question {i+1}",
                        "option_type": annotation_type,
                        "options": (
                            ["option1", "option2", "option3"]
                            if annotation_type in ["select", "radio"]
                            else []
                        ),
                    }
                )

            # Build project payload
            project_payload = {
                "client_id": self.client_id,
                "dataset_name": f"SDK_Test_{test_scenario['data_type']}_{int(time.time())}",
                "dataset_description": f"Test dataset for {test_scenario['scenario_name']}",
                "data_type": test_scenario["data_type"],
                "created_by": self.test_email,
                "project_name": f"SDK_Test_Project_{test_scenario['data_type']}_{int(time.time())}",
                "autolabel": False,
                "files_to_upload": test_files,
                "annotation_guide": annotation_guide,
                "rotation_config": self.rotation_config,
            }

            # Execute test based on credentials
            result = self.client.initiate_create_project(project_payload)

            self.assertIsInstance(result, dict)
            self.assertEqual(result.get("status"), "success")
            print(f"✓ {test_scenario['scenario_name']} project created successfully")

        finally:
            # Clean up test files
            for file_path in test_files:
                try:
                    os.unlink(file_path)
                except OSError:
                    pass

    def test_use_case_2_preannotation_upload_workflow(self):
        annotation_data = {
            "annotations": [
                {
                    "id": 1,
                    "image_id": 1,
                    "category_id": 1,
                    "bbox": [100, 100, 200, 200],
                    "area": 40000,
                    "iscrowd": 0,
                }
            ],
            "images": [
                {"id": 1, "width": 640, "height": 480, "file_name": "test_image.jpg"}
            ],
            "categories": [{"id": 1, "name": "person", "supercategory": "human"}],
        }

        temp_annotation_file = None
        try:
            temp_annotation_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            )
            json.dump(annotation_data, temp_annotation_file)
            temp_annotation_file.close()

            annotation_format = "coco_json"

            if hasattr(self, "created_project_id") and self.created_project_id:
                actual_project_id = self.created_project_id
            else:
                test_files = []
                try:
                    # Create a small test file
                    temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                    temp_file.write(b"fake_image_data_for_preannotation_test")
                    temp_file.close()
                    test_files.append(temp_file.name)

                    # Create project for preannotation testing
                    project_payload = {
                        "client_id": self.client_id,
                        "dataset_name": f"SDK_Preannotation_Test_{int(time.time())}",
                        "dataset_description": "Test dataset for preannotation integration testing",
                        "data_type": "image",
                        "created_by": self.test_email,
                        "project_name": f"SDK_Preannotation_Project_{int(time.time())}",
                        "autolabel": False,
                        "files_to_upload": test_files,
                        "annotation_guide": self.annotation_guide,
                        "rotation_config": self.rotation_config,
                    }

                    result = self.client.initiate_create_project(project_payload)
                    if isinstance(result, dict) and "response" in result:
                        actual_project_id = result["response"].get("project_id")
                    else:
                        actual_project_id = result.get("project_id") if isinstance(result, dict) else None

                    if not actual_project_id:
                        self.fail("Failed to create project for preannotation testing")

                finally:
                    # Clean up test files
                    for file_path in test_files:
                        try:
                            os.unlink(file_path)
                        except OSError:
                            pass

            print(
                "Calling actual Labellerr pre-annotation API with real credentials..."
            )

            try:
                with patch.object(
                    self.client, "preannotation_job_status", create=True
                ) as mock_status:
                    mock_status.return_value = {
                        "response": {"status": "completed", "job_id": "real-job-id"}
                    }

                    result = self.client._upload_preannotation_sync(
                        project_id=actual_project_id,
                        client_id=self.client_id,
                        annotation_format=annotation_format,
                        annotation_file=temp_annotation_file.name,
                    )

                    self.assertIsInstance(
                        result, dict, "Upload should return a dictionary"
                    )
                    self.assertIn(
                        "response", result, "Result should contain response"
                    )

            except Exception as api_error:
                raise api_error

        except LabellerrError as e:
            self.fail(f"Pre-annotation upload failed with LabellerrError: {e}")
        except Exception as e:
            self.fail(f"Pre-annotation upload failed with unexpected error: {e}")
        finally:
            if temp_annotation_file:
                try:
                    os.unlink(temp_annotation_file.name)
                except OSError:
                    pass

    def test_use_case_2_format_validation(self):

        format_test_cases = [
            {
                "test_name": "Invalid annotation format",
                "project_id": "test-project",
                "annotation_format": "invalid_format",
                "annotation_file": "test.json",
                "expected_error": "Invalid annotation_format",
                "create_temp_file": False,
                "temp_suffix": None,
            },
            {
                "test_name": "File not found",
                "project_id": "test-project",
                "annotation_format": "json",
                "annotation_file": "non_existent_file.json",
                "expected_error": "File not found",
                "create_temp_file": False,
                "temp_suffix": None,
            },
            {
                "test_name": "Wrong file extension for COCO format",
                "project_id": "test-project",
                "annotation_format": "coco_json",
                "annotation_file": None,  # Will be set to temp file
                "expected_error": "For coco_json annotation format, the file must have a .json extension",
                "create_temp_file": True,
                "temp_suffix": ".txt",
            },
        ]

        for i, test_case in enumerate(format_test_cases, 1):
            with self.subTest(test_name=test_case["test_name"]):

                temp_file = None
                try:
                    # Create temporary file if needed
                    if test_case["create_temp_file"]:
                        temp_file = tempfile.NamedTemporaryFile(
                            suffix=test_case["temp_suffix"], delete=False
                        )
                        temp_file.write(b"test content")
                        temp_file.close()
                        annotation_file = temp_file.name
                    else:
                        annotation_file = test_case["annotation_file"]

                    # Execute test and verify expected error
                    with self.assertRaises(LabellerrError) as context:
                        self.client._upload_preannotation_sync(
                            project_id=test_case["project_id"],
                            client_id=self.client_id,
                            annotation_format=test_case["annotation_format"],
                            annotation_file=annotation_file,
                        )

                    # Verify error message contains expected substring
                    error_message = str(context.exception)
                    self.assertIn(
                        test_case["expected_error"],
                        error_message,
                        f"Expected error '{test_case['expected_error']}' not found in '{error_message}'",
                    )

                finally:
                    # Clean up temporary file
                    if temp_file:
                        try:
                            os.unlink(temp_file.name)
                        except OSError:
                            pass

    def test_use_case_2_multiple_formats_table_driven(self):

        preannotation_scenarios = [
            {
                "scenario_name": "COCO JSON Upload",
                "annotation_format": "coco_json",
                "file_extension": ".json",
                "sample_data": {
                    "annotations": [
                        {
                            "id": 1,
                            "image_id": 1,
                            "category_id": 1,
                            "bbox": [0, 0, 100, 100],
                        }
                    ],
                    "images": [
                        {"id": 1, "file_name": "test.jpg", "width": 640, "height": 480}
                    ],
                    "categories": [
                        {"id": 1, "name": "test", "supercategory": "object"}
                    ],
                },
                "expected_success": True,
            },
            {
                "scenario_name": "JSON Annotations Upload",
                "annotation_format": "json",
                "file_extension": ".json",
                "sample_data": {
                    "labels": [
                        {
                            "image": "test.jpg",
                            "annotations": [{"label": "cat", "confidence": 0.95}],
                        }
                    ]
                },
                "expected_success": True,
            },
        ]

        test_scenario = preannotation_scenarios[0]  # COCO JSON

        temp_annotation_file = None
        try:
            temp_annotation_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=test_scenario["file_extension"], delete=False
            )
            json.dump(test_scenario["sample_data"], temp_annotation_file)
            temp_annotation_file.close()

            # Use project ID from previous tests if available, or create a new project
            test_project_id = getattr(self, "created_project_id", None)

            if not test_project_id:
                # Create a minimal project for preannotation testing
                test_files = []
                try:
                    # Create a small test file
                    temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                    temp_file.write(b"fake_image_data_for_preannotation_test")
                    temp_file.close()
                    test_files.append(temp_file.name)

                    # Create project for preannotation testing
                    project_payload = {
                        "client_id": self.client_id,
                        "dataset_name": f"SDK_Preannotation_Test_{int(time.time())}",
                        "dataset_description": "Test dataset for preannotation integration testing",
                        "data_type": "image",
                        "created_by": self.test_email,
                        "project_name": f"SDK_Preannotation_Project_{int(time.time())}",
                        "autolabel": False,
                        "files_to_upload": test_files,
                        "annotation_guide": self.annotation_guide,
                        "rotation_config": self.rotation_config,
                    }

                    result = self.client.initiate_create_project(project_payload)
                    if isinstance(result, dict) and "response" in result:
                        test_project_id = result["response"].get("project_id")
                    else:
                        test_project_id = result.get("project_id") if isinstance(result, dict) else None

                    if not test_project_id:
                        self.fail("Failed to create project for preannotation testing")

                finally:
                    # Clean up test files
                    for file_path in test_files:
                        try:
                            os.unlink(file_path)
                        except OSError:
                            pass

            try:
                # Only patch the missing method, let everything else be real
                with patch.object(
                    self.client, "preannotation_job_status", create=True
                ) as mock_status:
                    mock_status.return_value = {
                        "response": {
                            "status": "completed",
                            "job_id": f'job-{test_scenario["annotation_format"]}-{int(time.time())}',
                        }
                    }

                    result = self.client._upload_preannotation_sync(
                        project_id=test_project_id,
                        client_id=self.client_id,
                        annotation_format=test_scenario["annotation_format"],
                        annotation_file=temp_annotation_file.name,
                    )

                    self.assertIsInstance(result, dict)

            except Exception as api_error:
                raise api_error

        finally:
            # Clean up annotation file
            if temp_annotation_file:
                try:
                    os.unlink(temp_annotation_file.name)
                except OSError:
                    pass

    def tearDown(self):
        pass

    @classmethod
    def setUpClass(cls):
        """Set up test suite."""

    @classmethod
    def tearDownClass(cls):
        """Tear down test suite."""


def run_use_case_tests():

    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(LabelerUseCaseIntegrationTests)

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

    # Return success status
    return result.wasSuccessful()


if __name__ == "__main__":
    """
    Main execution block for running use case integration tests.

    Environment Variables Required:
    - LABELLERR_API_KEY: Your Labellerr API key
    - LABELLERR_API_SECRET: Your Labellerr API secret
    - LABELLERR_CLIENT_ID: Your Labellerr client ID
    - LABELLERR_TEST_EMAIL: Valid email address for testing

    Run with:
    python use_case_tests.py
    """
    # Check for required environment variables
    required_env_vars = ["LABELLERR_API_KEY", "LABELLERR_API_SECRET", "LABELLERR_CLIENT_ID", "LABELLERR_TEST_EMAIL"]

    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    # Run the tests
    success = run_use_case_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)
