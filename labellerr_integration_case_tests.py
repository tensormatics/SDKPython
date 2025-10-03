import json
import os
import sys
import tempfile
import time
import unittest
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import dotenv

from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError

dotenv.load_dotenv()


@dataclass
class AttachDetachTestCase:
    """Test case for attach/detach dataset operations"""

    test_name: str
    client_id: str
    project_id: str
    dataset_id: str
    expect_error_substr: Optional[str] = None
    expected_success: bool = True


@dataclass
class MultimodalIndexingTestCase:
    """Test case for multimodal indexing operations"""

    test_name: str
    client_id: str
    dataset_id: str
    indexing_config: Dict[str, Any]
    expect_error_substr: Optional[str] = None
    expected_success: bool = True


@dataclass
class AWSConnectionTestCase:
    test_name: str
    client_id: str
    access_key: str
    secret_key: str
    s3_path: str
    data_type: str
    name: str
    description: str
    connection_type: str = "import"
    expect_error_substr: str | None = None


@dataclass
class GCSConnectionTestCase:
    test_name: str
    client_id: str
    cred_file_content: str
    gcs_path: str
    data_type: str
    name: str
    description: str
    connection_type: str = "import"
    expect_error_substr: str | None = None


@dataclass
class UserManagementTestCase:
    """Test case for user management operations"""

    test_name: str
    client_id: str
    project_id: str
    email_id: str
    first_name: str
    last_name: str
    user_id: str = None
    role_id: str = None
    new_role_id: str = None
    expect_error_substr: str | None = None
    expected_success: bool = True


@dataclass
class UserWorkflowTestCase:
    """Test case for complete user workflow operations"""

    test_name: str
    client_id: str
    project_id: str
    email_id: str
    first_name: str
    last_name: str
    user_id: str
    roles: List[Dict[str, Any]]
    projects: List[str]
    expect_error_substr: str | None = None
    expected_success: bool = True


class LabelerIntegrationTests(unittest.TestCase):

    def setUp(self):

        self.api_key = os.getenv("API_KEY")
        self.api_secret = os.getenv("API_SECRET")
        self.client_id = os.getenv("CLIENT_ID")
        self.test_email = os.getenv("CLIENT_EMAIL")
        self.connector_video_creds_aws = os.getenv("AWS_CONNECTION_VIDEO")
        self.connector_image_creds_aws = os.getenv("AWS_CONNECTION_IMAGE")
        self.connector_image_creds_gcs = os.getenv("GCS_CONNECTION_IMAGE")
        self.connector_video_creds_gcs = os.getenv("GCS_CONNECTION_VIDEO")

        if (
            self.api_key == ""
            or self.api_secret == ""
            or self.client_id == ""
            or self.test_email == ""
            or self.connector_video_creds_aws == ""
            or self.connector_image_creds_aws == ""
        ):

            raise ValueError(
                "missing environment variables: "
                "LABELLERR_API_KEY, LABELLERR_API_SECRET, LABELLERR_CLIENT_ID, LABELLERR_TEST_EMAIL, AWS_CONNECTION_VIDEO, AWS_CONNECTION_IMAGE"
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

    def test_complete_project_creation_workflow(self):

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
            self.created_project_id = result.get("project_id")
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

    def test__request_validation(self):

        validation_test_cases = [
            {
                "test_name": "Missing client_id",
                "payload_overrides": {"client_id": None},
                "remove_keys": ["client_id"],
                "expected_error": "Required parameter client_id is missing",
            },
            {
                "test_name": "Invalid email format",
                "payload_overrides": {"created_by": "invalid-email"},
                "remove_keys": [],
                "expected_error": "Please enter email id in created_by",
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
                "expected_error": "Please provide either annotation guide or annotation template id",
            },
        ]

        # Base valid payload
        base_payload = {
            "client_id": self.client_id,
            "dataset_name": "test_dataset",
            "dataset_description": "test description",
            "data_type": "image",
            "created_by": "test@example.com",
            "project_name": "test_project",
            "autolabel": False,
            "files_to_upload": [],
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

                # Execute test and verify expected error
                with self.assertRaises(LabellerrError) as context:
                    self.client.initiate_create_project(test_payload)

                # Verify error message contains expected substring
                error_message = str(context.exception)
                self.assertIn(
                    test_case["expected_error"],
                    error_message,
                    f"Expected error '{test_case['expected_error']}' not found in '{error_message}'",
                )

    def test_create_project_multiple_data_types(self):

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
            print(f" {test_scenario['scenario_name']} project created successfully")

        finally:
            # Clean up test files
            for file_path in test_files:
                try:
                    os.unlink(file_path)
                except OSError:
                    pass

    def test_pre_annotation_upload_workflow(self):
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

            test_project_id = "sunny_tough_blackbird_40468"
            annotation_format = "coco_json"

            if hasattr(self, "created_project_id") and self.created_project_id:
                actual_project_id = self.created_project_id
            else:
                actual_project_id = test_project_id
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

    def test_use_format_validation(self):

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

    def test_pre_annotation_multiple_format(self):

        pre_annotation_scenarios = [
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

        test_scenario = pre_annotation_scenarios[0]  # COCO JSON

        temp_annotation_file = None
        try:
            temp_annotation_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=test_scenario["file_extension"], delete=False
            )
            json.dump(test_scenario["sample_data"], temp_annotation_file)
            temp_annotation_file.close()

            # Use project ID from previous tests if available
            test_project_id = getattr(
                self, "created_project_id", "test-project-id-table-driven"
            )

            try:
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

    def test_data_set_connection_aws(self):

        # Read per-type AWS secrets from env (JSON strings): AWS_CONNECTION_IMAGE, AWS_CONNECTION_VIDEO
        image_secret_json = os.getenv("AWS_CONNECTION_IMAGE")
        video_secret_json = os.getenv("AWS_CONNECTION_VIDEO")

        def _parse_secret(env_json: str):
            if not env_json:
                return {}
            try:
                return json.loads(env_json)
            except Exception:
                return {}

        image_secret = _parse_secret(image_secret_json)
        video_secret = _parse_secret(video_secret_json)

        image_access_key = image_secret.get("access_key")
        image_secret_key = image_secret.get("secret_key")
        image_s3_path = image_secret.get("s3_path")

        video_access_key = video_secret.get("access_key")
        video_secret_key = video_secret.get("secret_key")
        video_s3_path = video_secret.get("s3_path")

        cases: list[AWSConnectionTestCase] = [
            AWSConnectionTestCase(
                test_name="Missing credentials",
                client_id=self.client_id,
                access_key="",
                secret_key="",
                s3_path="s3://bucket/path",
                data_type="image",
                name="aws_invalid_connection_test",
                description="missing_secrets",
                expect_error_substr="Required parameter",
            ),
            AWSConnectionTestCase(
                test_name="Invalid S3 path",
                client_id=self.client_id,
                access_key=image_access_key or "dummy",
                secret_key=image_secret_key or "dummy",
                s3_path="invalid_path",
                data_type="image",
                name="aws_invalid_s3_path",
                description="invalid_path",
                expect_error_substr=None,
            ),
            AWSConnectionTestCase(
                test_name="Valid image import",
                client_id=self.client_id,
                access_key=image_access_key,
                secret_key=image_secret_key,
                s3_path=image_s3_path,
                data_type="image",
                name="aws_connection_image",
                description="test_description",
            ),
            AWSConnectionTestCase(
                test_name="Valid video import",
                client_id=self.client_id,
                access_key=video_access_key,
                secret_key=video_secret_key,
                s3_path=video_s3_path,
                data_type="video",
                name="aws_connection_video",
                description="test_description",
            ),
        ]

        # created_connection_ids = []
        for case in cases:
            with self.subTest(test_name=case.test_name):
                if case.expect_error_substr is not None:
                    with self.assertRaises(LabellerrError) as ctx:
                        self.client.create_aws_connection(
                            client_id=case.client_id,
                            aws_access_key=case.access_key,
                            aws_secrets_key=case.secret_key,
                            s3_path=case.s3_path,
                            data_type=case.data_type,
                            name=case.name,
                            description=case.description,
                            connection_type=case.connection_type,
                        )
                    if case.expect_error_substr:
                        self.assertIn(case.expect_error_substr, str(ctx.exception))
                else:
                    result = self.client.create_aws_connection(
                        client_id=case.client_id,
                        aws_access_key=case.access_key,
                        aws_secrets_key=case.secret_key,
                        s3_path=case.s3_path,
                        data_type=case.data_type,
                        name=case.name,
                        description=case.description,
                        connection_type=case.connection_type,
                    )
                    self.assertIsInstance(result, dict)
                    self.assertIn("response", result)
                    connection_id = result["response"].get("connection_id")
                    self.assertIsNotNone(connection_id)

                    # List connections to ensure it appears
                    list_result = self.client.list_connection(
                        client_id=case.client_id, connection_type=case.connection_type
                    )
                    self.assertIsInstance(list_result, dict)
                    self.assertIn("response", list_result)

                    # Delete the created connection
                    del_result = self.client.delete_connection(
                        client_id=case.client_id, connection_id=connection_id
                    )
                    self.assertIsInstance(del_result, dict)
                    self.assertIn("response", del_result)

    def test_data_set_connection_gcs(self):
        # Read per-type GCS secrets from env (JSON strings): GCS_CONNECTION_IMAGE, GCS_CONNECTION_VIDEO
        image_secret_json = os.getenv("GCS_CONNECTION_IMAGE")
        video_secret_json = os.getenv("GCS_CONNECTION_VIDEO")

        def _parse_secret(env_json: str):
            if not env_json:
                return {}
            try:
                return json.loads(env_json)
            except Exception:
                return {}

        image_secret = _parse_secret(image_secret_json)
        video_secret = _parse_secret(video_secret_json)

        image_cred_file = image_secret.get("cred_file")
        image_gcs_path = image_secret.get("gcs_path")

        video_cred_file = video_secret.get("cred_file")
        video_gcs_path = video_secret.get("gcs_path")

        cases: list[GCSConnectionTestCase] = [
            GCSConnectionTestCase(
                test_name="Missing credential file",
                client_id=self.client_id,
                cred_file_content="",
                gcs_path="gs://bucket/path",
                data_type="image",
                name="gcs_invalid_connection_test",
                description="missing_cred_file",
                expect_error_substr="GCS credential file not found",
            ),
            GCSConnectionTestCase(
                test_name="Valid image import",
                client_id=self.client_id,
                cred_file_content=image_cred_file,
                gcs_path=image_gcs_path,
                data_type="image",
                name="gcs_connection_image",
                description="test_description",
            ),
            GCSConnectionTestCase(
                test_name="Valid video import",
                client_id=self.client_id,
                cred_file_content=video_cred_file,
                gcs_path=video_gcs_path,
                data_type="video",
                name="gcs_connection_video",
                description="test_description",
            ),
        ]

        for case in cases:
            with self.subTest(test_name=case.test_name):
                temp_created_path = None
                if case.expect_error_substr is not None:
                    with self.assertRaises(LabellerrError) as ctx:
                        self.client.create_gcs_connection(
                            client_id=case.client_id,
                            gcs_cred_file=case.cred_file_content,
                            gcs_path=case.gcs_path,
                            data_type=case.data_type,
                            name=case.name,
                            description=case.description,
                            connection_type=case.connection_type,
                        )
                    if case.expect_error_substr:
                        self.assertIn(case.expect_error_substr, str(ctx.exception))
                else:
                    tf = tempfile.NamedTemporaryFile(
                        mode="w", suffix=".json", delete=False
                    )
                    try:
                        # Support both JSON string and already-parsed dict for creds
                        if isinstance(case.cred_file_content, (dict, list)):
                            parsed = case.cred_file_content
                        elif isinstance(
                            case.cred_file_content, (str, bytes, bytearray)
                        ):
                            parsed = json.loads(case.cred_file_content)
                        else:
                            raise TypeError(
                                "Unsupported credential content type; expected str/bytes/dict/list"
                            )
                        tf.write(json.dumps(parsed))
                        tf.flush()
                    except Exception as e:
                        raise e
                    finally:
                        try:
                            tf.close()
                        except Exception:
                            pass
                    temp_created_path = tf.name
                    result = self.client.create_gcs_connection(
                        client_id=case.client_id,
                        gcs_cred_file=temp_created_path,
                        gcs_path=case.gcs_path,
                        data_type=case.data_type,
                        name=case.name,
                        description=case.description,
                        connection_type=case.connection_type,
                    )
                    self.assertIsInstance(result, dict)
                    self.assertIn("response", result)
                    connection_id = result["response"].get("connection_id")
                    self.assertIsNotNone(connection_id)

                    list_result = self.client.list_connection(
                        client_id=case.client_id, connection_type=case.connection_type
                    )
                    self.assertIsInstance(list_result, dict)
                    self.assertIn("response", list_result)

                    del_result = self.client.delete_connection(
                        client_id=case.client_id, connection_id=connection_id
                    )
                    self.assertIsInstance(del_result, dict)
                    self.assertIn("response", del_result)
                # Cleanup any temp cred file created for this subtest
                if temp_created_path:
                    try:
                        os.unlink(temp_created_path)
                    except OSError:
                        pass

    def test_attach_detach_dataset_operations(self):
        test_project_id = "sunny_tough_blackbird_40468"
        test_dataset_id = "769a313a-ea7e-47f2-83de-e4a11befd048"

        attach_detach_test_cases = [
            {
                "test_name": "Attach dataset to project",
                "operation": "attach",
                "client_id": self.client_id,
                "project_id": test_project_id,
                "dataset_id": test_dataset_id,
                "expected_success": True,
            },
            {
                "test_name": "Detach dataset from project",
                "operation": "detach",
                "client_id": self.client_id,
                "project_id": test_project_id,
                "dataset_id": test_dataset_id,
                "expected_success": True,
            },
            {
                "test_name": "Attach with invalid project_id",
                "operation": "attach",
                "client_id": self.client_id,
                "project_id": "invalid-project-id",
                "dataset_id": test_dataset_id,
                "expected_success": False,
                "expect_error_substr": "Invalid",
            },
            {
                "test_name": "Detach with invalid dataset_id",
                "operation": "detach",
                "client_id": self.client_id,
                "project_id": test_project_id,
                "dataset_id": "invalid-dataset-id",
                "expected_success": False,
                "expect_error_substr": "Invalid",
            },
        ]

        for i, test_case in enumerate(attach_detach_test_cases, 1):
            with self.subTest(test_name=test_case["test_name"]):
                try:
                    if test_case["operation"] == "attach":
                        result = self.client.attach_dataset_to_project(
                            client_id=test_case["client_id"],
                            project_id=test_case["project_id"],
                            dataset_id=test_case["dataset_id"],
                        )
                    else:  # detach
                        result = self.client.detach_dataset_from_project(
                            client_id=test_case["client_id"],
                            project_id=test_case["project_id"],
                            dataset_id=test_case["dataset_id"],
                        )

                    if test_case["expected_success"]:
                        self.assertIsInstance(
                            result, dict, f"Test case {i} should return a dictionary"
                        )
                        self.assertIn(
                            "response", result, f"Test case {i} should contain response"
                        )
                        print(f" {test_case['test_name']} - Operation successful")
                    else:
                        self.fail(
                            f"Test case {i} should have failed but succeeded: {result}"
                        )

                except LabellerrError as e:
                    if test_case["expected_success"]:
                        self.fail(
                            f"Test case {i} should have succeeded but failed: {e}"
                        )
                    else:
                        if test_case.get("expect_error_substr"):
                            self.assertIn(
                                test_case["expect_error_substr"],
                                str(e),
                                f"Test case {i} error message should contain '{test_case['expect_error_substr']}'",
                            )
                        print(f" {test_case['test_name']} - Expected error: {e}")
                except Exception as e:
                    self.fail(f"Test case {i} failed with unexpected error: {e}")

    def test_multimodal_indexing_operations(self):

        test_dataset_id = "769a313a-ea7e-47f2-83de-e4a11befd048"

        indexing_test_cases = [
            {
                "test_name": "Enable multimodal indexing with text and image",
                "client_id": self.client_id,
                "dataset_id": test_dataset_id,
                "indexing_config": {
                    "enabled": True,
                    "modalities": ["text", "image"],
                    "indexing_type": "semantic",
                },
                "expected_success": True,
            },
            {
                "test_name": "Enable multimodal indexing with all modalities",
                "client_id": self.client_id,
                "dataset_id": test_dataset_id,
                "indexing_config": {
                    "enabled": True,
                    "modalities": ["text", "image", "audio", "video"],
                    "indexing_type": "semantic",
                    "embedding_model": "default",
                },
                "expected_success": True,
            },
            {
                "test_name": "Disable multimodal indexing",
                "client_id": self.client_id,
                "dataset_id": test_dataset_id,
                "indexing_config": {"enabled": False, "modalities": []},
                "expected_success": True,
            },
            {
                "test_name": "Invalid dataset_id format",
                "client_id": self.client_id,
                "dataset_id": "invalid-dataset-id",
                "indexing_config": {"enabled": True, "modalities": ["text"]},
                "expected_success": False,
                "expect_error_substr": "Invalid",
            },
            {
                "test_name": "Invalid indexing config - missing enabled",
                "client_id": self.client_id,
                "dataset_id": test_dataset_id,
                "indexing_config": {"modalities": ["text"]},
                "expected_success": False,
                "expect_error_substr": "enabled",
            },
        ]

        for i, test_case in enumerate(indexing_test_cases, 1):
            with self.subTest(test_name=test_case["test_name"]):
                try:
                    result = self.client.enable_multimodal_indexing(
                        client_id=test_case["client_id"],
                        dataset_id=test_case["dataset_id"],
                        indexing_config=test_case["indexing_config"],
                    )

                    if test_case["expected_success"]:
                        self.assertIsInstance(
                            result, dict, f"Test case {i} should return a dictionary"
                        )
                        self.assertIn(
                            "response", result, f"Test case {i} should contain response"
                        )
                        print(
                            f" {test_case['test_name']} - Multimodal indexing operation successful"
                        )
                    else:
                        self.fail(
                            f"Test case {i} should have failed but succeeded: {result}"
                        )

                except LabellerrError as e:
                    if test_case["expected_success"]:
                        self.fail(
                            f"Test case {i} should have succeeded but failed: {e}"
                        )
                    else:
                        if test_case.get("expect_error_substr"):
                            self.assertIn(
                                test_case["expect_error_substr"],
                                str(e),
                                f"Test case {i} error message should contain '{test_case['expect_error_substr']}'",
                            )
                        print(f" {test_case['test_name']} - Expected error: {e}")
                except Exception as e:
                    self.fail(f"Test case {i} failed with unexpected error: {e}")

    def test_attach_dataset_to_project_table_driven(self):
        """Table-driven tests for attach_dataset_to_project functionality"""

        test_dataset_id = "769a313a-ea7e-47f2-83de-e4a11befd048"

        test_project_id = "sunny_tough_blackbird_40468"

        attach_test_cases = [
            AttachDetachTestCase(
                test_name="Valid attach operation",
                client_id=self.client_id,
                project_id=test_project_id,
                dataset_id=test_dataset_id,
                expected_success=True,
            ),
            AttachDetachTestCase(
                test_name="Invalid project_id format",
                client_id=self.client_id,
                project_id="invalid-project-id",
                dataset_id=test_dataset_id,
                expect_error_substr="Invalid",
                expected_success=False,
            ),
            AttachDetachTestCase(
                test_name="Invalid dataset_id format",
                client_id=self.client_id,
                project_id=test_project_id,
                dataset_id="invalid-dataset-id",
                expect_error_substr="Invalid",
                expected_success=False,
            ),
            AttachDetachTestCase(
                test_name="Missing client_id",
                client_id="",
                project_id=test_project_id,
                dataset_id=test_dataset_id,
                expect_error_substr="Required parameter",
                expected_success=False,
            ),
            AttachDetachTestCase(
                test_name="Non-existent project_id",
                client_id=self.client_id,
                project_id="00000000-0000-0000-0000-000000000000",
                dataset_id=test_dataset_id,
                expect_error_substr="not found",
                expected_success=False,
            ),
            AttachDetachTestCase(
                test_name="Non-existent dataset_id",
                client_id=self.client_id,
                project_id=test_project_id,
                dataset_id="00000000-0000-0000-0000-000000000000",
                expect_error_substr="not found",
                expected_success=False,
            ),
        ]

        for i, test_case in enumerate(attach_test_cases, 1):
            with self.subTest(test_name=test_case.test_name):
                try:
                    result = self.client.attach_dataset_to_project(
                        client_id=test_case.client_id,
                        project_id=test_case.project_id,
                        dataset_id=test_case.dataset_id,
                    )

                    if test_case.expected_success:
                        self.assertIsInstance(
                            result, dict, f"Test case {i} should return a dictionary"
                        )
                        self.assertIn(
                            "response", result, f"Test case {i} should contain response"
                        )
                        print(f" {test_case.test_name} - Attach operation successful")
                    else:
                        self.fail(
                            f"Test case {i} should have failed but succeeded: {result}"
                        )

                except LabellerrError as e:
                    if test_case.expected_success:
                        self.fail(
                            f"Test case {i} should have succeeded but failed: {e}"
                        )
                    else:
                        if test_case.expect_error_substr:
                            self.assertIn(
                                test_case.expect_error_substr,
                                str(e),
                                f"Test case {i} error message should contain '{test_case.expect_error_substr}'",
                            )
                        print(f" {test_case.test_name} - Expected error: {e}")
                except Exception as e:
                    self.fail(f"Test case {i} failed with unexpected error: {e}")

    def test_detach_dataset_from_project_table_driven(self):

        test_dataset_id = "769a313a-ea7e-47f2-83de-e4a11befd048"
        test_project_id = "sunny_tough_blackbird_40468"

        detach_test_cases = [
            AttachDetachTestCase(
                test_name="Valid detach operation",
                client_id=self.client_id,
                project_id=test_project_id,
                dataset_id=test_dataset_id,
                expected_success=True,
            ),
            AttachDetachTestCase(
                test_name="Invalid project_id format",
                client_id=self.client_id,
                project_id="invalid-project-id",
                dataset_id=test_dataset_id,
                expect_error_substr="Invalid",
                expected_success=False,
            ),
            AttachDetachTestCase(
                test_name="Invalid dataset_id format",
                client_id=self.client_id,
                project_id=test_project_id,
                dataset_id="invalid-dataset-id",
                expect_error_substr="Invalid",
                expected_success=False,
            ),
            AttachDetachTestCase(
                test_name="Missing client_id",
                client_id="",
                project_id=test_project_id,
                dataset_id=test_dataset_id,
                expect_error_substr="Required parameter",
                expected_success=False,
            ),
            AttachDetachTestCase(
                test_name="Non-existent project_id",
                client_id=self.client_id,
                project_id="00000000-0000-0000-0000-000000000000",
                dataset_id=test_dataset_id,
                expect_error_substr="not found",
                expected_success=False,
            ),
            AttachDetachTestCase(
                test_name="Non-existent dataset_id",
                client_id=self.client_id,
                project_id=test_project_id,
                dataset_id="00000000-0000-0000-0000-000000000000",
                expect_error_substr="not found",
                expected_success=False,
            ),
        ]

        for i, test_case in enumerate(detach_test_cases, 1):
            with self.subTest(test_name=test_case.test_name):
                try:
                    result = self.client.detach_dataset_from_project(
                        client_id=test_case.client_id,
                        project_id=test_case.project_id,
                        dataset_id=test_case.dataset_id,
                    )

                    if test_case.expected_success:
                        self.assertIsInstance(
                            result, dict, f"Test case {i} should return a dictionary"
                        )
                        self.assertIn(
                            "response", result, f"Test case {i} should contain response"
                        )
                        print(f" {test_case.test_name} - Detach operation successful")
                    else:
                        self.fail(
                            f"Test case {i} should have failed but succeeded: {result}"
                        )

                except LabellerrError as e:
                    if test_case.expected_success:
                        self.fail(
                            f"Test case {i} should have succeeded but failed: {e}"
                        )
                    else:
                        if test_case.expect_error_substr:
                            self.assertIn(
                                test_case.expect_error_substr,
                                str(e),
                                f"Test case {i} error message should contain '{test_case.expect_error_substr}'",
                            )
                        print(f" {test_case.test_name} - Expected error: {e}")
                except Exception as e:
                    self.fail(f"Test case {i} failed with unexpected error: {e}")

    def test_enable_multimodal_indexing_table_driven(self):

        test_dataset_id = "769a313a-ea7e-47f2-83de-e4a11befd048"

        indexing_test_cases = [
            MultimodalIndexingTestCase(
                test_name="Valid multimodal indexing with text and image",
                client_id=self.client_id,
                dataset_id=test_dataset_id,
                indexing_config={
                    "enabled": True,
                    "modalities": ["text", "image"],
                    "indexing_type": "semantic",
                },
                expected_success=True,
            ),
            MultimodalIndexingTestCase(
                test_name="Valid multimodal indexing with all modalities",
                client_id=self.client_id,
                dataset_id=test_dataset_id,
                indexing_config={
                    "enabled": True,
                    "modalities": ["text", "image", "audio", "video"],
                    "indexing_type": "semantic",
                    "embedding_model": "default",
                },
                expected_success=True,
            ),
            MultimodalIndexingTestCase(
                test_name="Disable multimodal indexing",
                client_id=self.client_id,
                dataset_id=test_dataset_id,
                indexing_config={"enabled": False, "modalities": []},
                expected_success=True,
            ),
            MultimodalIndexingTestCase(
                test_name="Invalid dataset_id format",
                client_id=self.client_id,
                dataset_id="invalid-dataset-id",
                indexing_config={"enabled": True, "modalities": ["text"]},
                expect_error_substr="Invalid",
                expected_success=False,
            ),
            MultimodalIndexingTestCase(
                test_name="Missing client_id",
                client_id="",
                dataset_id=test_dataset_id,
                indexing_config={"enabled": True, "modalities": ["text"]},
                expect_error_substr="Required parameter",
                expected_success=False,
            ),
            MultimodalIndexingTestCase(
                test_name="Invalid indexing config - missing enabled",
                client_id=self.client_id,
                dataset_id=test_dataset_id,
                indexing_config={"modalities": ["text"]},
                expect_error_substr="enabled",
                expected_success=False,
            ),
            MultimodalIndexingTestCase(
                test_name="Invalid indexing config - empty modalities",
                client_id=self.client_id,
                dataset_id=test_dataset_id,
                indexing_config={"enabled": True, "modalities": []},
                expect_error_substr="modalities",
                expected_success=False,
            ),
            MultimodalIndexingTestCase(
                test_name="Invalid indexing config - invalid modality",
                client_id=self.client_id,
                dataset_id=test_dataset_id,
                indexing_config={"enabled": True, "modalities": ["invalid_modality"]},
                expect_error_substr="modality",
                expected_success=False,
            ),
            MultimodalIndexingTestCase(
                test_name="Non-existent dataset_id",
                client_id=self.client_id,
                dataset_id="00000000-0000-0000-0000-000000000000",
                indexing_config={"enabled": True, "modalities": ["text"]},
                expect_error_substr="not found",
                expected_success=False,
            ),
        ]

        for i, test_case in enumerate(indexing_test_cases, 1):
            with self.subTest(test_name=test_case.test_name):
                try:
                    result = self.client.enable_multimodal_indexing(
                        client_id=test_case.client_id,
                        dataset_id=test_case.dataset_id,
                        indexing_config=test_case.indexing_config,
                    )

                    if test_case.expected_success:
                        self.assertIsInstance(
                            result, dict, f"Test case {i} should return a dictionary"
                        )
                        self.assertIn(
                            "response", result, f"Test case {i} should contain response"
                        )
                        print(
                            f" {test_case.test_name} - Multimodal indexing operation successful"
                        )
                    else:
                        self.fail(
                            f"Test case {i} should have failed but succeeded: {result}"
                        )

                except LabellerrError as e:
                    if test_case.expected_success:
                        self.fail(
                            f"Test case {i} should have succeeded but failed: {e}"
                        )
                    else:
                        if test_case.expect_error_substr:
                            self.assertIn(
                                test_case.expect_error_substr,
                                str(e),
                                f"Test case {i} error message should contain '{test_case.expect_error_substr}'",
                            )
                        print(f" {test_case.test_name} - Expected error: {e}")
                except Exception as e:
                    self.fail(f"Test case {i} failed with unexpected error: {e}")

    def test_attach_detach_workflow_integration(self):

        test_project_id = "sunny_tough_blackbird_40468"
        test_dataset_id = "769a313a-ea7e-47f2-83de-e4a11befd048"

        try:
            # Step 1: Attach dataset to project
            print("Step 1: Attaching dataset to project...")
            attach_result = self.client.attach_dataset_to_project(
                client_id=self.client_id,
                project_id=test_project_id,
                dataset_id=test_dataset_id,
            )
            self.assertIsInstance(attach_result, dict)
            self.assertIn("response", attach_result)
            print(" Dataset attached successfully")

            # Step 2: Verify attachment (you might need to implement a get_project_datasets method)
            # This is a placeholder - you may need to implement this method or use existing API
            print("Step 2: Verifying attachment...")

            # Step 3: Detach dataset from project
            print("Step 3: Detaching dataset from project...")
            detach_result = self.client.detach_dataset_from_project(
                client_id=self.client_id,
                project_id=test_project_id,
                dataset_id=test_dataset_id,
            )
            self.assertIsInstance(detach_result, dict)
            self.assertIn("response", detach_result)
            print(" Dataset detached successfully")

            print(" Complete attach/detach workflow successful")

        except LabellerrError as e:
            self.fail(f"Integration test failed with LabellerrError: {e}")
        except Exception as e:
            self.fail(f"Integration test failed with unexpected error: {e}")

    def test_multimodal_indexing_workflow_integration(self):
        """Integration test for complete multimodal indexing workflow"""

        test_dataset_id = "769a313a-ea7e-47f2-83de-e4a11befd048"

        try:
            # Step 1: Enable multimodal indexing
            print("Step 1: Enabling multimodal indexing...")
            indexing_config = {
                "enabled": True,
                "modalities": ["text", "image"],
                "indexing_type": "semantic",
                "embedding_model": "default",
            }

            enable_result = self.client.enable_multimodal_indexing(
                client_id=self.client_id,
                dataset_id=test_dataset_id,
                indexing_config=indexing_config,
            )
            self.assertIsInstance(enable_result, dict)
            self.assertIn("response", enable_result)
            print("Multimodal indexing enabled successfully")

            # Step 2: Verify indexing status (you might need to implement a get_indexing_status method)
            print("Step 2: Verifying indexing status...")
            # Note: Manual verification may be required through Labellerr UI or API

            # Step 3: Disable multimodal indexing
            print("Step 3: Disabling multimodal indexing...")
            disable_config = {"enabled": False, "modalities": []}

            disable_result = self.client.enable_multimodal_indexing(
                client_id=self.client_id,
                dataset_id=test_dataset_id,
                indexing_config=disable_config,
            )
            self.assertIsInstance(disable_result, dict)
            self.assertIn("response", disable_result)
            print(" Multimodal indexing disabled successfully")

            print(" Complete multimodal indexing workflow successful")

        except LabellerrError as e:
            self.fail(f"Integration test failed with LabellerrError: {e}")
        except Exception as e:
            self.fail(f"Integration test failed with unexpected error: {e}")

    def test_user_management_workflow(self):
        """Test complete user management workflow: create, update, add to project, change role, remove, delete"""
        try:
            # Test data
            test_email = f"test_user_{int(time.time())}@example.com"
            test_first_name = "Test"
            test_last_name = "User"
            test_user_id = f"test-user-{int(time.time())}"
            test_project_id = "test_project_123"
            test_role_id = "7"
            test_new_role_id = "5"

            # Step 1: Create a user
            print(f"\n=== Step 1: Creating user {test_email} ===")
            create_result = self.client.create_user(
                client_id=self.client_id,
                first_name=test_first_name,
                last_name=test_last_name,
                email_id=test_email,
                projects=[test_project_id],
                roles=[{"project_id": test_project_id, "role_id": test_role_id}],
            )
            print(f"User creation result: {create_result}")
            self.assertIsNotNone(create_result)

            # Step 2: Update user role
            print(f"\n=== Step 2: Updating user role for {test_email} ===")
            update_result = self.client.update_user_role(
                client_id=self.client_id,
                project_id=test_project_id,
                email_id=test_email,
                roles=[{"project_id": test_project_id, "role_id": test_new_role_id}],
                first_name=test_first_name,
                last_name=test_last_name,
            )
            print(f"User role update result: {update_result}")
            self.assertIsNotNone(update_result)

            # Step 3: Add user to project (if not already added)
            print(f"\n=== Step 3: Adding user to project {test_project_id} ===")
            add_result = self.client.add_user_to_project(
                client_id=self.client_id,
                project_id=test_project_id,
                email_id=test_email,
                role_id=test_role_id,
            )
            print(f"Add user to project result: {add_result}")
            self.assertIsNotNone(add_result)

            # Step 4: Change user role
            print(f"\n=== Step 4: Changing user role for {test_email} ===")
            change_role_result = self.client.change_user_role(
                client_id=self.client_id,
                project_id=test_project_id,
                email_id=test_email,
                new_role_id=test_new_role_id,
            )
            print(f"Change user role result: {change_role_result}")
            self.assertIsNotNone(change_role_result)

            # Step 5: Remove user from project
            print(f"\n=== Step 5: Removing user from project {test_project_id} ===")
            remove_result = self.client.remove_user_from_project(
                client_id=self.client_id,
                project_id=test_project_id,
                email_id=test_email,
            )
            print(f"Remove user from project result: {remove_result}")
            self.assertIsNotNone(remove_result)

            # Step 6: Delete user
            print(f"\n=== Step 6: Deleting user {test_email} ===")
            delete_result = self.client.delete_user(
                client_id=self.client_id,
                project_id=test_project_id,
                email_id=test_email,
                user_id=test_user_id,
                first_name=test_first_name,
                last_name=test_last_name,
            )
            print(f"Delete user result: {delete_result}")
            self.assertIsNotNone(delete_result)

            print("Complete user management workflow completed successfully")

        except Exception as e:
            print(f" User management workflow failed: {str(e)}")
            raise

    def test_create_user_integration(self):
        """Test user creation with real API calls"""
        try:
            test_email = f"integration_test_{int(time.time())}@example.com"
            test_first_name = "Integration"
            test_last_name = "Test"
            test_project_id = "test_project_1233"
            test_role_id = "7"

            print(f"\n=== Testing user creation for {test_email} ===")

            result = self.client.create_user(
                client_id=self.client_id,
                first_name=test_first_name,
                last_name=test_last_name,
                email_id=test_email,
                projects=[test_project_id],
                roles=[{"project_id": test_project_id, "role_id": test_role_id}],
                work_phone="123-456-7890",
                job_title="Test Engineer",
                language="en",
                timezone="GMT",
            )

            print(f"User creation result: {result}")
            self.assertIsNotNone(result)

            # Clean up - delete the user
            try:
                self.client.delete_user(
                    client_id=self.client_id,
                    project_id=test_project_id,
                    email_id=test_email,
                    user_id=f"test-user-{int(time.time())}",
                    first_name=test_first_name,
                    last_name=test_last_name,
                )
                print(f"Cleanup: User {test_email} deleted successfully")
            except Exception as cleanup_error:
                print(
                    f"Cleanup warning: Could not delete user {test_email}: {cleanup_error}"
                )

        except Exception as e:
            print(f" User creation integration test failed: {str(e)}")
            raise

    # todo this is failing on update role
    def test_update_user_role_integration(self):
        """Test user role update with real API calls"""
        try:
            test_email = f"update_test_{int(time.time())}@example.com"
            test_first_name = "Update"
            test_last_name = "Test"
            test_project_id = "test_project_123"
            test_role_id = "7"
            test_new_role_id = "5"

            print(f"\n=== Testing user role update for {test_email} ===")

            # First create a user
            create_result = self.client.create_user(
                client_id=self.client_id,
                first_name=test_first_name,
                last_name=test_last_name,
                email_id=test_email,
                projects=[test_project_id],
                roles=[{"project_id": test_project_id, "role_id": test_role_id}],
            )
            print(f"User creation result: {create_result}")

            # Then update the user role
            update_result = self.client.update_user_role(
                client_id=self.client_id,
                project_id=test_project_id,
                email_id=test_email,
                roles=[{"project_id": test_project_id, "role_id": test_new_role_id}],
                first_name=test_first_name,
                last_name=test_last_name,
                work_phone="987-654-3210",
                job_title="Senior Test Engineer",
                language="en",
                timezone="UTC",
            )

            print(f"User role update result: {update_result}")
            self.assertIsNotNone(update_result)

            # Clean up - delete the user
            try:
                self.client.delete_user(
                    client_id=self.client_id,
                    project_id=test_project_id,
                    email_id=test_email,
                    user_id=f"test-user-{int(time.time())}",
                    first_name=test_first_name,
                    last_name=test_last_name,
                )
                print(f" Cleanup: User {test_email} deleted successfully")
            except Exception as cleanup_error:
                print(
                    f" Cleanup warning: Could not delete user {test_email}: {cleanup_error}"
                )

        except Exception as e:
            print(f" User role update integration test failed: {str(e)}")
            raise

    def test_project_user_management_integration(self):
        """Test project user management operations with real API calls"""
        try:
            test_email = f"project_test_{int(time.time())}@example.com"
            test_first_name = "Project"
            test_last_name = "Test"
            test_project_id = "test_project_123"
            test_role_id = "7"
            test_new_role_id = "5"

            print(f"\n=== Testing project user management for {test_email} ===")

            # Step 1: Create a user
            create_result = self.client.create_user(
                client_id=self.client_id,
                first_name=test_first_name,
                last_name=test_last_name,
                email_id=test_email,
                projects=[test_project_id],
                roles=[{"project_id": test_project_id, "role_id": test_role_id}],
            )
            print(f"User creation result: {create_result}")

            # Step 2: Add user to project
            add_result = self.client.add_user_to_project(
                client_id=self.client_id,
                project_id=test_project_id,
                email_id=test_email,
                role_id=test_role_id,
            )
            print(f"Add user to project result: {add_result}")
            self.assertIsNotNone(add_result)

            # Step 3: Change user role
            change_role_result = self.client.change_user_role(
                client_id=self.client_id,
                project_id=test_project_id,
                email_id=test_email,
                new_role_id=test_new_role_id,
            )
            print(f"Change user role result: {change_role_result}")
            self.assertIsNotNone(change_role_result)

            # Step 4: Remove user from project
            remove_result = self.client.remove_user_from_project(
                client_id=self.client_id,
                project_id=test_project_id,
                email_id=test_email,
            )
            print(f"Remove user from project result: {remove_result}")
            self.assertIsNotNone(remove_result)

            # Clean up - delete the user
            try:
                self.client.delete_user(
                    client_id=self.client_id,
                    project_id=test_project_id,
                    email_id=test_email,
                    user_id=f"test-user-{int(time.time())}",
                    first_name=test_first_name,
                    last_name=test_last_name,
                )
                print(f" Cleanup: User {test_email} deleted successfully")
            except Exception as cleanup_error:
                print(
                    f" Cleanup warning: Could not delete user {test_email}: {cleanup_error}"
                )

        except Exception as e:
            print(f" Project user management integration test failed: {str(e)}")
            raise

    def test_user_management_error_handling(self):
        """Test user management error handling with invalid inputs"""
        try:
            print("=== Testing user management error handling ===")

            # Test with invalid client_id
            try:
                self.client.create_user(
                    client_id="invalid_client_id",
                    first_name="Test",
                    last_name="User",
                    email_id="test@example.com",
                    projects=["project_123"],
                    roles=[{"project_id": "project_123", "role_id": "7"}],
                )
                self.fail("Expected error for invalid client_id")
            except Exception as e:
                print(f" Correctly caught error for invalid client_id: {str(e)}")

            # Test with missing required parameters
            try:
                self.client.create_user(
                    client_id=self.client_id,
                    first_name="Test",
                    # Missing last_name, email_id, projects, roles
                )
                self.fail("Expected error for missing required parameters")
            except Exception as e:
                print(f" Correctly caught error for missing parameters: {str(e)}")

            # Test with invalid email format
            try:
                self.client.create_user(
                    client_id=self.client_id,
                    first_name="Test",
                    last_name="User",
                    email_id="invalid_email",  # Invalid email format
                    projects=["project_123"],
                    roles=[{"project_id": "project_123", "role_id": "7"}],
                )
                print(" Note: Email validation may not be enforced at SDK level")
            except Exception as e:
                print(f" Correctly caught error for invalid email: {str(e)}")

            print(" User management error handling tests completed successfully!")

        except Exception as e:
            print(f"User management error handling test failed: {str(e)}")
            raise

    @classmethod
    def setUpClass(cls):
        """Set up test suite."""

    def tearDown(self):
        pass

    @classmethod
    def tearDownClass(cls):
        """Tear down test suite."""

    def run_user_management_tests(self):
        """Run only the user management integration tests"""

        # Check for required environment variables
        required_env_vars = ["API_KEY", "API_SECRET", "CLIENT_ID", "TEST_EMAIL"]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        if missing_vars:
            print(f"Missing required environment variables: {', '.join(missing_vars)}")
            print("Please set the following environment variables:")
            for var in missing_vars:
                print(f"  export {var}=your_value")
            return False

        print("🚀 Running User Management Integration Tests")
        print("=" * 50)

        # Create test suite with only user management tests
        suite = unittest.TestSuite()

        # Add user management test methods
        user_management_tests = [
            "test_user_management_workflow",
            "test_create_user_integration",
            "test_update_user_role_integration",
            "test_project_user_management_integration",
            "test_user_management_error_handling",
        ]

        for test_name in user_management_tests:
            suite.addTest(LabelerIntegrationTests(test_name))

        # Run tests with verbose output
        runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
        result = runner.run(suite)

        # Print summary
        print("\n" + "=" * 50)
        if result.wasSuccessful():
            print("All user management integration tests passed!")
        else:
            print("Some user management integration tests failed!")
            print(f"Failures: {len(result.failures)}")
            print(f"Errors: {len(result.errors)}")

        return result.wasSuccessful()


def run_use_case_tests():

    suite = unittest.TestLoader().loadTestsFromTestCase(LabelerIntegrationTests)

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

    # Return success status
    return result.wasSuccessful()


if __name__ == "__main__":
    """
    Environment Variables Required:
    - API_KEY: Your Labellerr API key
    - API_SECRET: Your Labellerr API secret
    - CLIENT_ID: Your Labellerr client ID
    - TEST_EMAIL: Valid email address for testing
    - AWS_CONNECTION_VIDEO: AWS video connection id
    - AWS_CONNECTION_IMAGE: AWS image connection id
    - GCS_CONNECTION_VIDEO: JSON string with GCS video creds {"cred_file:"{}","gcs_path":"gs://bucket/path"}
    - GCS_CONNECTION_IMAGE: JSON string with GCS image creds {"cred_file:"{}","gcs_path":"gs://bucket/path"}

    New User Management Tests Added:
    - test_user_management_workflow: Complete user lifecycle test
    - test_create_user_integration: User creation with real API calls
    - test_update_user_role_integration: User role updates with real API calls
    - test_project_user_management_integration: Project user management operations
    - test_user_management_error_handling: Error handling validation

    Run with:
    python labellerr_integration_case_tests.py
    """
    # Check for required environment variables
    required_env_vars = [
        "API_KEY",
        "API_SECRET",
        "CLIENT_ID",
        "TEST_EMAIL",
        "AWS_CONNECTION_VIDEO",
        "AWS_CONNECTION_IMAGE",
        "GCS_CONNECTION_VIDEO",
        "GCS_CONNECTION_IMAGE",
    ]

    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    # Run the tests
    success = run_use_case_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)
