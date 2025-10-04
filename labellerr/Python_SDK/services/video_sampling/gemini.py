import os
import cv2
from PIL import Image
from dataclasses import dataclass, asdict
from typing import List, Optional
import json
from google.cloud import videointelligence


@dataclass
class SceneFrame:
    """Represents a detected scene with its extracted frame."""
    frame_path: str
    frame_no: int
    start_time_offset: float
    end_time_offset: float
    

@dataclass
class DetectionResult:
    """Contains all detection results for a video."""
    file_id: str
    output_folder: str
    total_frames: int
    selected_frames: List[SceneFrame]
    

class GeminiSceneDetect:
    """Google Cloud Video Intelligence API scene detection and frame extraction."""
    
    def __init__(self, video_path: str, file_id: str, gcs_uri: Optional[str] = None, credentials_path: Optional[str] = None):
        """
        Initialize the Google Cloud Video Intelligence scene detector.
        
        Args:
            video_path: Path to the local video file (for frame extraction)
            file_id: Unique identifier for the video (used as output folder name)
            gcs_uri: Google Cloud Storage URI (gs://bucket/video.mp4) for API processing.
                    If None, the video will be uploaded as bytes (limited to 10MB)
            credentials_path: Path to service account JSON key file.
                            If None, uses GOOGLE_APPLICATION_CREDENTIALS environment variable
        """
        self.video_path = video_path
        self.file_id = file_id
        self.output_folder = file_id
        self.gcs_uri = gcs_uri
        
        # Set credentials if provided
        if credentials_path:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        
        # Initialize Video Intelligence client
        self.client = videointelligence.VideoIntelligenceServiceClient()
        
    def detect_and_extract(self) -> DetectionResult:
        """
        Detect scenes using Google Cloud Video Intelligence API and extract representative frames.
        
        Returns:
            DetectionResult containing file_id, output_folder, total_frames, and list of SceneFrame objects
        """
        print(f"Processing video: {self.video_path}")
        print("Detecting shot changes using Google Cloud Video Intelligence API...")
        
        # Detect shots using Video Intelligence API
        shots = self._detect_shots()
        
        if not shots:
            raise ValueError("No shot changes detected in the video")
        
        print(f"Detected {len(shots)} shots")
        
        # Create output folder
        os.makedirs(self.output_folder, exist_ok=True)
        
        # Open video for frame extraction
        video = cv2.VideoCapture(self.video_path)
        
        if not video.isOpened():
            raise ValueError(f"Cannot open video: {self.video_path}")
        
        # Get video properties
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = video.get(cv2.CAP_PROP_FPS)
        
        print(f"Total frames: {total_frames}")
        print(f"FPS: {fps}")
        
        # Extract and save frames
        scene_frames = []
        
        for idx, shot in enumerate(shots):
            # Calculate middle frame number from shot timestamps
            start_time = shot.start_time_offset.total_seconds()
            end_time = shot.end_time_offset.total_seconds()
            middle_time = (start_time + end_time) / 2
            frame_no = int(middle_time * fps)
            
            # Ensure frame number is within bounds
            frame_no = max(0, min(frame_no, total_frames - 1))
            
            # Extract frame
            frame = self._get_frame(video, frame_no)
            
            if frame is None:
                print(f"Warning: Could not extract frame {frame_no} for shot {idx}")
                continue
            
            # Save frame with frame number as filename
            frame_filename = f"{frame_no}.jpg"
            frame_path = os.path.join(self.output_folder, frame_filename)
            frame.save(frame_path)
            
            # Create SceneFrame object
            scene_frame = SceneFrame(
                frame_path=frame_path,
                frame_no=frame_no,
                start_time_offset=start_time,
                end_time_offset=end_time
            )
            scene_frames.append(scene_frame)
            
            print(f"Saved keyframe {idx} at frame {frame_no} (time: {middle_time:.2f}s)")
        
        video.release()
        
        print(f"\nExtracted {len(scene_frames)} keyframes from {total_frames} frames.")
        
        # Create result
        result = DetectionResult(
            file_id=self.file_id,
            output_folder=self.output_folder,
            total_frames=total_frames,
            selected_frames=scene_frames
        )
        
        # Save JSON mapping
        self._save_json_mapping(result)
        
        return result
    
    def _detect_shots(self) -> List:
        """
        Detect shot changes using Google Cloud Video Intelligence API.
        
        Returns:
            List of shot annotation objects
        """
        features = [videointelligence.Feature.SHOT_CHANGE_DETECTION]
        
        if self.gcs_uri:
            # Use GCS URI for large videos
            print(f"Analyzing video from GCS: {self.gcs_uri}")
            operation = self.client.annotate_video(
                request={
                    "input_uri": self.gcs_uri,
                    "features": features
                }
            )
        else:
            # Read video file and send as bytes (limited to 10MB)
            with open(self.video_path, "rb") as video_file:
                input_content = video_file.read()
            
            print(f"Analyzing video from local file (size: {len(input_content) / (1024*1024):.2f} MB)")
            
            if len(input_content) > 10 * 1024 * 1024:  # 10MB limit
                raise ValueError(
                    "Video file is larger than 10MB. Please upload to Google Cloud Storage "
                    "and provide gcs_uri parameter (gs://bucket/video.mp4)"
                )
            
            operation = self.client.annotate_video(
                request={
                    "input_content": input_content,
                    "features": features
                }
            )
        
        print("Waiting for operation to complete...")
        result = operation.result(timeout=600)  # 10 minute timeout
        
        # Get shot annotations
        annotation_result = result.annotation_results[0]
        shots = annotation_result.shot_annotations
        
        return shots
    
    def _get_frame(self, video: cv2.VideoCapture, frame_no: int) -> Optional[Image.Image]:
        """
        Extract a specific frame from video.
        
        Args:
            video: OpenCV video capture object
            frame_no: Frame number to extract
            
        Returns:
            PIL Image of the frame, or None if extraction fails
        """
        video.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        success, frame = video.read()
        
        if not success:
            return None
        
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    
    def _save_json_mapping(self, result: DetectionResult) -> None:
        """
        Save JSON mapping of file_id to extracted scenes.
        
        Args:
            result: DetectionResult object
        """
        mapping = {
            "file_id": result.file_id,
            "output_folder": result.output_folder,
            "total_frames": result.total_frames,
            "total_selected_frames": len(result.selected_frames),
            "detection_method": "Google Cloud Video Intelligence API - Shot Change Detection",
            "gcs_uri": self.gcs_uri if self.gcs_uri else "local file",
            "selected_frames": [asdict(frame) for frame in result.selected_frames]
        }
        
        json_path = os.path.join(self.output_folder, f"{self.file_id}_mapping.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        
        print(f"JSON mapping saved to: {json_path}")


if __name__ == "__main__":
    # Example usage - Local video file (must be < 10MB)
    video_path = r"D:\professional\LABELLERR\Task\Repos\SDKPython\labellerr\Python_SDK\services\video_sampling\video2.mp4"
    cred_json_path = r"D:\professional\LABELLERR\Task\Repos\SDKPython\labellerr\Python_SDK\services\video_sampling\yash-suman-prod.json"
    
    # ----------------------------------------------
    # Option 1: Process local video file (< 10MB)
    # ----------------------------------------------
    
    detector = GeminiSceneDetect(
        credentials_path=cred_json_path  # Uses GOOGLE_APPLICATION_CREDENTIALS env var
    )
    labellerr_file = LabellerrFile(
        file_id="video_001"
    )
    detector.detect_and_extract()
    
    # Detect and extract frames
    try:
        result = detector.detect_and_extract()
        print(f"\nDetection complete!")
        print(f"Total frames extracted: {len(result.selected_frames)}")
        print(f"Output folder: {result.output_folder}")
    except Exception as e:
        print(f"Error: {e}")
