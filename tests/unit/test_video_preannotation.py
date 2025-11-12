"""
Unit tests for video project pre-annotation functionality.

This module contains comprehensive unit tests for video project pre-annotation
upload methods, including synchronous and asynchronous operations.
"""

import json
import os
import tempfile
from concurrent.futures import Future
from unittest.mock import Mock, patch

import pytest

from labellerr.client import LabellerrClient
from labellerr.core.exceptions import LabellerrError


@pytest.fixture
def mock_client():
    """Create a mock client for testing"""
    client = LabellerrClient("test_api_key", "test_api_secret", "test_client_id")
    client.base_url = "https://api.labellerr.com"
    return client


@pytest.fixture
def mock_video_project(mock_client):
    """Create a mock video project instance"""
    from labellerr.core.projects.video_project import VideoProject

    # Create instance bypassing metaclass
    project = VideoProject.__new__(VideoProject)
    project.client = mock_client
    project.project_id = "test_project_id"
    project.project_data = {
        "project_id": "test_project_id",
        "data_type": "video",
        "attached_datasets": [],
    }
    return project


@pytest.fixture
def temp_annotation_file():
    """Create temporary annotation file for testing"""
    annotation_data = [
        {
            "file_name": "video1.mp4",
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
                                "25": {
                                    "frame": 25,
                                    "answer": {
                                        "xmin": 150,
                                        "ymin": 150,
                                        "xmax": 350,
                                        "ymax": 350,
                                        "rotation": 0,
                                    },
                                    "timestamp": 1.0,
                                },
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
    json.dump(annotation_data, temp_file)
    temp_file.close()

    yield temp_file.name

    # Cleanup
    try:
        os.unlink(temp_file.name)
    except OSError:
        pass


@pytest.mark.unit
class TestVideoProjectPreannotationUpload:
    """Unit tests for video project pre-annotation upload methods"""

    def test_upload_preannotation_delegates_to_base_method(
        self, mock_video_project, temp_annotation_file
    ):
        """Test that upload_preannotation delegates to upload_preannotations"""
        with patch.object(
            mock_video_project,
            "upload_preannotations",
            return_value={"status": "completed"},
        ) as mock_upload:
            result = mock_video_project.upload_preannotation(
                "video_json", temp_annotation_file, "medium"
            )

            mock_upload.assert_called_once_with(
                "video_json",
                temp_annotation_file,
                "medium",
                _async=False,
            )
            assert result == {"status": "completed"}

    def test_upload_preannotation_without_conf_bucket(
        self, mock_video_project, temp_annotation_file
    ):
        """Test upload_preannotation without confidence bucket"""
        with patch.object(
            mock_video_project,
            "upload_preannotations",
            return_value={"status": "completed"},
        ) as mock_upload:
            result = mock_video_project.upload_preannotation(
                "video_json", temp_annotation_file
            )

            mock_upload.assert_called_once_with(
                "video_json",
                temp_annotation_file,
                None,
                _async=False,
            )
            assert result == {"status": "completed"}

    @pytest.mark.parametrize(
        "annotation_format",
        ["video_json", "coco_json", "yolo", "json"],
    )
    def test_upload_preannotation_various_formats(
        self, mock_video_project, temp_annotation_file, annotation_format
    ):
        """Test upload_preannotation with various annotation formats"""
        with patch.object(
            mock_video_project,
            "upload_preannotations",
            return_value={"status": "completed"},
        ) as mock_upload:
            mock_video_project.upload_preannotation(
                annotation_format, temp_annotation_file
            )

            mock_upload.assert_called_once()
            assert mock_upload.call_args[0][0] == annotation_format

    @pytest.mark.parametrize(
        "conf_bucket",
        ["low", "medium", "high"],
    )
    def test_upload_preannotation_various_conf_buckets(
        self, mock_video_project, temp_annotation_file, conf_bucket
    ):
        """Test upload_preannotation with various confidence buckets"""
        with patch.object(
            mock_video_project,
            "upload_preannotations",
            return_value={"status": "completed"},
        ) as mock_upload:
            mock_video_project.upload_preannotation(
                "video_json", temp_annotation_file, conf_bucket
            )

            mock_upload.assert_called_once()
            assert mock_upload.call_args[0][2] == conf_bucket


@pytest.mark.unit
class TestVideoProjectPreannotationUploadAsync:
    """Unit tests for video project async pre-annotation upload"""

    def test_upload_preannotation_async_returns_future(
        self, mock_video_project, temp_annotation_file
    ):
        """Test that upload_preannotation_async returns a Future object"""
        mock_future = Mock(spec=Future)
        mock_future.result.return_value = {"status": "completed"}

        with patch.object(
            mock_video_project,
            "upload_preannotations",
            return_value=mock_future,
        ):
            result = mock_video_project.upload_preannotation_async(
                "video_json", temp_annotation_file
            )

            assert isinstance(result, Mock)  # Mock of Future

    def test_upload_preannotation_async_delegates_to_base(
        self, mock_video_project, temp_annotation_file
    ):
        """Test that async method delegates to upload_preannotations with _async=True"""
        mock_future = Mock(spec=Future)

        with patch.object(
            mock_video_project,
            "upload_preannotations",
            return_value=mock_future,
        ) as mock_base_async:
            result = mock_video_project.upload_preannotation_async(
                "video_json", temp_annotation_file, "high"
            )

            mock_base_async.assert_called_once_with(
                "video_json", temp_annotation_file, "high", _async=True
            )
            assert result == mock_future

    def test_upload_preannotation_async_without_conf_bucket(
        self, mock_video_project, temp_annotation_file
    ):
        """Test async upload without confidence bucket"""
        mock_future = Mock(spec=Future)

        with patch.object(
            mock_video_project,
            "upload_preannotations",
            return_value=mock_future,
        ) as mock_base_async:
            mock_video_project.upload_preannotation_async(
                "video_json", temp_annotation_file
            )

            mock_base_async.assert_called_once_with(
                "video_json", temp_annotation_file, None, _async=True
            )

    @pytest.mark.parametrize(
        "annotation_format,conf_bucket",
        [
            ("video_json", "low"),
            ("coco_json", "medium"),
            ("json", "high"),
            ("yolo", None),
        ],
    )
    def test_upload_preannotation_async_various_combinations(
        self, mock_video_project, temp_annotation_file, annotation_format, conf_bucket
    ):
        """Test async upload with various format and confidence bucket combinations"""
        mock_future = Mock(spec=Future)

        with patch.object(
            mock_video_project,
            "upload_preannotations",
            return_value=mock_future,
        ) as mock_base_async:
            mock_video_project.upload_preannotation_async(
                annotation_format, temp_annotation_file, conf_bucket
            )

            mock_base_async.assert_called_once_with(
                annotation_format, temp_annotation_file, conf_bucket, _async=True
            )


@pytest.mark.unit
class TestPreannotationSyncInternal:
    """Unit tests for preannotation upload internal behavior"""

    def test_upload_preannotation_with_valid_file(
        self,
        mock_video_project,
        temp_annotation_file,
    ):
        """Test upload with valid annotation file"""
        with patch.object(
            mock_video_project,
            "upload_preannotations",
            return_value={"status": "completed", "response": {"job_id": "job-123"}},
        ) as mock_upload:
            result = mock_video_project.upload_preannotation(
                "video_json",
                temp_annotation_file,
                "medium",
            )

            mock_upload.assert_called_once()
            assert result["status"] == "completed"

    def test_upload_preannotation_sync_missing_params(
        self, mock_video_project, temp_annotation_file
    ):
        """Test sync upload with missing required parameters"""
        with patch.object(
            mock_video_project,
            "upload_preannotations",
            side_effect=LabellerrError("Missing required parameter"),
        ):
            with pytest.raises(LabellerrError):
                mock_video_project.upload_preannotation(
                    None,  # Missing annotation_format
                    temp_annotation_file,
                )

    def test_upload_preannotation_sync_with_conf_bucket_url(
        self,
        mock_video_project,
        temp_annotation_file,
    ):
        """Test that conf_bucket is properly passed"""
        with patch.object(
            mock_video_project,
            "upload_preannotations",
            return_value={"status": "completed", "response": {"job_id": "job-123"}},
        ) as mock_upload:
            mock_video_project.upload_preannotation(
                "video_json",
                temp_annotation_file,
                "high",
            )

            # Verify conf_bucket was passed correctly
            call_args = mock_upload.call_args
            assert call_args[0][2] == "high"

    def test_upload_preannotation_sync_invalid_conf_bucket(
        self,
        mock_video_project,
        temp_annotation_file,
    ):
        """Test sync upload with invalid confidence bucket"""
        with patch.object(
            mock_video_project,
            "upload_preannotations",
            side_effect=AssertionError("Invalid confidence bucket"),
        ):
            with pytest.raises(AssertionError):
                mock_video_project.upload_preannotation(
                    "video_json",
                    temp_annotation_file,
                    "invalid_bucket",  # Invalid bucket
                )


@pytest.mark.unit
class TestPreannotationFileValidation:
    """Unit tests for pre-annotation file validation"""

    def test_video_json_format_with_json_file(self, mock_video_project):
        """Test that video_json format accepts JSON files"""
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        temp_file.write('{"test": "data"}')
        temp_file.close()

        try:
            with patch.object(
                mock_video_project,
                "upload_preannotations",
                return_value={"status": "completed"},
            ):
                # Should not raise any error
                mock_video_project.upload_preannotation("video_json", temp_file.name)
        finally:
            os.unlink(temp_file.name)

    def test_nonexistent_file(self, mock_video_project):
        """Test upload with nonexistent file"""
        with patch.object(
            mock_video_project,
            "upload_preannotations",
            side_effect=LabellerrError("File not found"),
        ):
            with pytest.raises(LabellerrError):
                mock_video_project.upload_preannotation(
                    "video_json",
                    "/nonexistent/file.json",
                )


@pytest.mark.unit
class TestPreannotationJobStatus:
    """Unit tests for pre-annotation job status monitoring"""

    @patch("labellerr.core.projects.base.concurrent.futures.ThreadPoolExecutor")
    def test_preannotation_job_status_async_calls_poll(
        self, mock_executor, mock_video_project
    ):
        """Test that job status monitoring uses polling mechanism"""
        mock_future = Mock(spec=Future)
        mock_executor.return_value.__enter__.return_value.submit.return_value = (
            mock_future
        )

        result = mock_video_project.preannotation_job_status_async("job-123")

        # Verify executor was used and Future was returned
        assert result == mock_future

    @patch("labellerr.core.projects.base.concurrent.futures.ThreadPoolExecutor")
    def test_async_upload_uses_thread_pool(
        self, mock_executor, mock_video_project, temp_annotation_file
    ):
        """Test that async upload returns a Future"""
        mock_future = Mock(spec=Future)

        with patch.object(
            mock_video_project,
            "upload_preannotations",
            return_value=mock_future,
        ):
            result = mock_video_project.upload_preannotation_async(
                "video_json", temp_annotation_file
            )
            # Verify it returns the future
            assert result == mock_future
