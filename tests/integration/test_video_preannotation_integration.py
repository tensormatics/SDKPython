"""
Integration tests for video project pre-annotation functionality.

These tests require real API credentials and will make actual API calls.
Set environment variables: API_KEY, API_SECRET, CLIENT_ID

Run with: pytest tests/integration/test_video_preannotation_integration.py -m integration
"""

import json
import os
import tempfile
import time
from concurrent.futures import Future

import pytest

from labellerr.core.projects import LabellerrProject


@pytest.fixture(scope="module")
def video_annotation_data():
    """Sample video annotation data for testing"""
    return [
        {
            "file_name": "test_video.mp4",
            "annotations": [
                {
                    "question_name": "Object Detection",
                    "question_type": "BoundingBox",
                    "answer": [
                        {
                            "frames": {
                                "0": {
                                    "frame": 0,
                                    "answer": {
                                        "xmin": 100,
                                        "ymin": 100,
                                        "xmax": 300,
                                        "ymax": 300,
                                        "rotation": 0,
                                    },
                                    "timestamp": 0.0,
                                },
                                "30": {
                                    "frame": 30,
                                    "answer": {
                                        "xmin": 150,
                                        "ymin": 120,
                                        "xmax": 350,
                                        "ymax": 320,
                                        "rotation": 0,
                                    },
                                    "timestamp": 1.0,
                                },
                                "60": {
                                    "frame": 60,
                                    "answer": {
                                        "xmin": 180,
                                        "ymin": 150,
                                        "xmax": 380,
                                        "ymax": 350,
                                        "rotation": 0,
                                    },
                                    "timestamp": 2.0,
                                },
                            },
                        },
                        {
                            "frames": {
                                "0": {
                                    "frame": 0,
                                    "answer": {
                                        "xmin": 500,
                                        "ymin": 300,
                                        "xmax": 800,
                                        "ymax": 450,
                                        "rotation": 0,
                                    },
                                    "timestamp": 0.0,
                                },
                                "30": {
                                    "frame": 30,
                                    "answer": {
                                        "xmin": 550,
                                        "ymin": 300,
                                        "xmax": 850,
                                        "ymax": 450,
                                        "rotation": 0,
                                    },
                                    "timestamp": 1.0,
                                },
                            },
                        },
                    ],
                },
                {
                    "question_name": "Object Tracking",
                    "question_type": "polygon",
                    "answer": [
                        {
                            "frames": {
                                "0": {
                                    "frame": 0,
                                    "answer": [
                                        {"x": 0, "y": 600},
                                        {"x": 1920, "y": 600},
                                        {"x": 1920, "y": 1080},
                                        {"x": 0, "y": 1080},
                                    ],
                                    "timestamp": 0.0,
                                },
                            },
                        }
                    ],
                },
            ],
        }
    ]


@pytest.fixture(scope="module")
def video_annotation_file(video_annotation_data):
    """Create temporary video annotation file"""
    temp_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(video_annotation_data, temp_file)
    temp_file.close()

    yield temp_file.name

    # Cleanup
    try:
        os.unlink(temp_file.name)
    except OSError:
        pass


@pytest.fixture(scope="module")
def coco_annotation_file():
    """Create temporary COCO format annotation file"""
    coco_data = {
        "images": [
            {
                "id": 1,
                "file_name": "video_frame_001.jpg",
                "width": 1920,
                "height": 1080,
            }
        ],
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
        "categories": [{"id": 1, "name": "person", "supercategory": "human"}],
    }

    temp_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(coco_data, temp_file)
    temp_file.close()

    yield temp_file.name

    # Cleanup
    try:
        os.unlink(temp_file.name)
    except OSError:
        pass


@pytest.mark.integration
@pytest.mark.slow
class TestVideoProjectPreannotationIntegration:
    """Integration tests for video project pre-annotation"""

    @pytest.fixture(autouse=True)
    def setup(self, test_credentials, integration_client):
        """Setup for each test"""
        self.client = integration_client
        self.credentials = test_credentials

    def test_upload_preannotation_sync_video_answer_format(self, video_annotation_file):
        """Test synchronous upload of video annotations in video_json format"""
        # Get video project instance
        project_id = "murial_magnificent_swift_54305"
        project = LabellerrProject(self.client, project_id)

        # Verify it's a video project
        assert project.data_type == "video", "Test project must be a video project"

        # Upload pre-annotations
        result = project.upload_preannotation(
            annotation_format="video_json",
            annotation_file=video_annotation_file,
        )

        # Verify response structure
        assert "response" in result
        assert "status" in result["response"]
        assert result["response"]["status"] in ["completed", "pending", "processing"]

        # If job is completed, verify metadata
        if result["response"]["status"] == "completed":
            assert "metadata" in result["response"]
            metadata = result["response"]["metadata"]
            # Verify metadata contains expected fields
            assert isinstance(metadata, dict)

    def test_upload_preannotation_sync_with_confidence_bucket(
        self, video_annotation_file
    ):
        """Test synchronous upload with confidence bucket"""
        project_id = "murial_magnificent_swift_54305"
        project = LabellerrProject(self.client, project_id)

        # Test each confidence bucket
        for conf_bucket in ["low", "medium", "high"]:
            result = project.upload_preannotation(
                annotation_format="video_json",
                annotation_file=video_annotation_file,
                conf_bucket=conf_bucket,
            )

            assert "response" in result
            assert result["response"]["status"] in [
                "completed",
                "pending",
                "processing",
            ]

            # Add small delay between uploads to avoid rate limiting
            time.sleep(2)

    def test_upload_preannotation_async_returns_future(self, video_annotation_file):
        """Test asynchronous upload returns Future object"""
        project_id = "murial_magnificent_swift_54305"
        project = LabellerrProject(self.client, project_id)

        # Upload pre-annotations asynchronously
        future = project.upload_preannotation_async(
            annotation_format="video_json",
            annotation_file=video_annotation_file,
        )

        # Verify Future object is returned
        assert isinstance(future, Future), "Should return a Future object"

        # Wait for completion with timeout
        result = future.result(timeout=120)

        # Verify result
        assert "response" in result
        assert "status" in result["response"]
        assert result["response"]["status"] in ["completed", "pending", "processing"]

    def test_upload_preannotation_async_with_conf_bucket(self, video_annotation_file):
        """Test asynchronous upload with confidence bucket"""
        project_id = "murial_magnificent_swift_54305"
        project = LabellerrProject(self.client, project_id)

        future = project.upload_preannotation_async(
            annotation_format="video_json",
            annotation_file=video_annotation_file,
            conf_bucket="high",
        )

        # Wait for completion
        result = future.result(timeout=120)

        assert "response" in result
        assert result["response"]["status"] in ["completed", "pending", "processing"]

    def test_upload_preannotation_coco_format(self, coco_annotation_file):
        """Test upload with COCO JSON format"""
        project_id = "murial_magnificent_swift_54305"
        project = LabellerrProject(self.client, project_id)

        result = project.upload_preannotation(
            annotation_format="coco_json",
            annotation_file=coco_annotation_file,
        )

        assert "response" in result
        assert result["response"]["status"] in ["completed", "pending", "processing"]

    def test_upload_preannotation_invalid_format_fails(self, video_annotation_file):
        """Test that invalid annotation format raises error"""
        project_id = "murial_magnificent_swift_54305"
        project = LabellerrProject(self.client, project_id)

        with pytest.raises(Exception):
            project.upload_preannotation(
                annotation_format="invalid_format",
                annotation_file=video_annotation_file,
            )

    def test_upload_preannotation_invalid_conf_bucket_fails(
        self, video_annotation_file
    ):
        """Test that invalid confidence bucket raises error"""
        project_id = "murial_magnificent_swift_54305"
        project = LabellerrProject(self.client, project_id)

        with pytest.raises(AssertionError, match="Invalid confidence bucket"):
            project._upload_preannotation_sync(
                project.project_id,
                self.credentials["client_id"],
                "video_json",
                video_annotation_file,
                "invalid_bucket",
            )

    def test_upload_preannotation_nonexistent_file_fails(self):
        """Test that nonexistent file raises error"""
        project_id = "murial_magnificent_swift_54305"
        project = LabellerrProject(self.client, project_id)

        with pytest.raises(Exception):
            project.upload_preannotation(
                annotation_format="video_json",
                annotation_file="/nonexistent/path/to/file.json",
            )

    @pytest.mark.parametrize(
        "annotation_format",
        ["video_json", "coco_json", "json"],
    )
    def test_upload_preannotation_multiple_formats(
        self, video_annotation_file, annotation_format
    ):
        """Test upload with multiple annotation formats"""
        project_id = "murial_magnificent_swift_54305"
        project = LabellerrProject(self.client, project_id)

        result = project.upload_preannotation(
            annotation_format=annotation_format,
            annotation_file=video_annotation_file,
        )

        assert "response" in result
        assert result["response"]["status"] in ["completed", "pending", "processing"]

        # Add delay between uploads
        time.sleep(2)


@pytest.mark.integration
@pytest.mark.slow
class TestVideoPreannotationJobStatusMonitoring:
    """Integration tests for pre-annotation job status monitoring"""

    @pytest.fixture(autouse=True)
    def setup(self, test_credentials, integration_client):
        """Setup for each test"""
        self.client = integration_client
        self.credentials = test_credentials

    def test_job_status_monitoring_completes(self, video_annotation_file):
        """Test that job status monitoring waits for completion"""
        project_id = "murial_magnificent_swift_54305"
        project = LabellerrProject(self.client, project_id)

        # Start async upload
        future = project.upload_preannotation_async(
            annotation_format="video_json",
            annotation_file=video_annotation_file,
        )

        # Monitor status - this should block until complete
        start_time = time.time()
        result = future.result(timeout=120)
        elapsed_time = time.time() - start_time

        # Verify completion
        assert result["response"]["status"] in ["completed", "pending", "processing"]

        # If completed, verify it took some time (indicating actual processing)
        if result["response"]["status"] == "completed":
            # Processing should take at least 1 second
            assert elapsed_time >= 1.0, "Job completed too quickly, may not be real"

    def test_concurrent_uploads(self, video_annotation_file):
        """Test multiple concurrent pre-annotation uploads"""
        project_id = "murial_magnificent_swift_54305"
        project = LabellerrProject(self.client, project_id)

        # Start multiple async uploads
        futures = []
        for i in range(3):
            future = project.upload_preannotation_async(
                annotation_format="video_json",
                annotation_file=video_annotation_file,
            )
            futures.append(future)
            time.sleep(1)  # Small delay between requests

        # Wait for all to complete
        results = []
        for future in futures:
            try:
                result = future.result(timeout=120)
                results.append(result)
            except Exception as e:
                pytest.fail(f"Concurrent upload failed: {str(e)}")

        # Verify all completed
        assert len(results) == 3
        for result in results:
            assert "response" in result
            assert result["response"]["status"] in [
                "completed",
                "pending",
                "processing",
            ]


@pytest.mark.integration
class TestVideoPreannotationErrorHandling:
    """Integration tests for error handling in video pre-annotation"""

    @pytest.fixture(autouse=True)
    def setup(self, test_credentials, integration_client):
        """Setup for each test"""
        self.client = integration_client
        self.credentials = test_credentials

    def test_upload_with_malformed_json_fails(self):
        """Test that malformed JSON file raises appropriate error"""
        project_id = "murial_magnificent_swift_54305"
        project = LabellerrProject(self.client, project_id)

        # Create malformed JSON file
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        temp_file.write("{ invalid json content }")
        temp_file.close()

        try:
            # This might fail during upload or validation
            with pytest.raises(Exception):
                project.upload_preannotation(
                    annotation_format="video_json",
                    annotation_file=temp_file.name,
                )
        finally:
            os.unlink(temp_file.name)

    def test_upload_with_empty_file_fails(self):
        """Test that empty file raises appropriate error"""
        project_id = "murial_magnificent_swift_54305"
        project = LabellerrProject(self.client, project_id)

        # Create empty file
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        temp_file.close()

        try:
            with pytest.raises(Exception):
                project.upload_preannotation(
                    annotation_format="video_json",
                    annotation_file=temp_file.name,
                )
        finally:
            os.unlink(temp_file.name)

    def test_upload_to_nonexistent_project_fails(self, video_annotation_file):
        """Test upload to non-existent project raises error"""
        with pytest.raises(Exception):  # type: ignore[misc]
            fake_project = LabellerrProject(self.client, "nonexistent_project_id_12345")
            fake_project.upload_preannotation(
                annotation_format="video_json",
                annotation_file=video_annotation_file,
            )


@pytest.mark.integration
class TestVideoPreannotationDataFormats:
    """Integration tests for various video pre-annotation data formats"""

    @pytest.fixture(autouse=True)
    def setup(self, test_credentials, integration_client):
        """Setup for each test"""
        self.client = integration_client
        self.credentials = test_credentials

    def test_upload_single_frame_annotation(self):
        """Test upload of single frame annotation"""
        project_id = "murial_magnificent_swift_54305"
        project = LabellerrProject(self.client, project_id)

        single_frame_data = [
            {
                "file_name": "single_frame.mp4",
                "annotations": [
                    {
                        "question_name": "Detection",
                        "question_type": "BoundingBox",
                        "answer": [
                            {
                                "frames": {
                                    "0": {
                                        "frame": 0,
                                        "answer": {
                                            "xmin": 100,
                                            "ymin": 100,
                                            "xmax": 150,
                                            "ymax": 150,
                                            "rotation": 0,
                                        },
                                        "timestamp": 0.0,
                                    }
                                },
                            }
                        ],
                    }
                ],
            }
        ]

        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(single_frame_data, temp_file)
        temp_file.close()

        try:
            result = project.upload_preannotation(
                annotation_format="video_json",
                annotation_file=temp_file.name,
            )
            assert "response" in result
        finally:
            os.unlink(temp_file.name)

    def test_upload_multi_object_tracking(self):
        """Test upload of multiple object tracking annotations"""
        project_id = "murial_magnificent_swift_54305"
        project = LabellerrProject(self.client, project_id)

        multi_object_data = [
            {
                "file_name": "multi_object.mp4",
                "annotations": [
                    {
                        "question_name": "Multi-Object Tracking",
                        "question_type": "BoundingBox",
                        "answer": [
                            {
                                "frames": {
                                    str(frame): {
                                        "frame": frame,
                                        "answer": {
                                            "xmin": 100 + i * 50,
                                            "ymin": 100 + frame * 10,
                                            "xmax": 150 + i * 50,
                                            "ymax": 150 + frame * 10,
                                            "rotation": 0,
                                        },
                                        "timestamp": frame / 30.0,
                                    }
                                    for frame in range(0, 60, 10)
                                },
                            }
                            for i in range(3)
                        ],
                    }
                ],
            }
        ]

        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(multi_object_data, temp_file)
        temp_file.close()

        try:
            result = project.upload_preannotation(
                annotation_format="video_json",
                annotation_file=temp_file.name,
            )
            assert "response" in result
        finally:
            os.unlink(temp_file.name)
