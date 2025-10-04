import os
from scenedetect import detect, AdaptiveDetector
from PIL import Image
import cv2
from dataclasses import dataclass, asdict
from typing import List
import json


@dataclass
class SceneFrame:
    """Represents a detected scene with its extracted frame."""
    frame_path: str
    frame_no: int
    

@dataclass
class DetectionResult:
    """Contains all detection results for a video."""
    file_id: str
    output_folder: str
    total_frames: int
    selected_frames: List[SceneFrame]
    

class PySceneDetect:
    """Scene detection and frame extraction for videos."""
    
    def __init__(self, video_path: str, file_id: str):
        """
        Initialize the scene detector.
        
        Args:
            video_path: Path to the video file
            file_id: Unique identifier for the video (used as output folder name)
        """
        self.video_path = video_path
        self.file_id = file_id
        self.output_folder = file_id
        
    def detect_and_extract(self) -> DetectionResult:
        """
        Detect scenes and extract representative frames.
        
        Returns:
            DetectionResult containing file_id, output_folder, total_frames, and list of SceneFrame objects
        """
        # Detect scene transitions
        scenes = detect(self.video_path, AdaptiveDetector())
        
        # Create output folder
        os.makedirs(self.output_folder, exist_ok=True)
        
        # Open video for frame extraction
        video = cv2.VideoCapture(self.video_path)
        
        # Get total frames in video
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Extract and save frames
        scene_frames = []
        for scene in scenes:
            # Calculate middle frame number
            frame_no = (scene[1] - scene[0]).frame_num // 2 + scene[0].frame_num
            
            # Extract frame
            frame = self._get_frame(video, frame_no)
            
            # Save frame with frame number as filename
            frame_filename = f"{frame_no}.jpg"
            frame_path = os.path.join(self.output_folder, frame_filename)
            frame.save(frame_path)
            
            # Create SceneFrame object
            scene_frame = SceneFrame(
                frame_path=frame_path,
                frame_no=frame_no
            )
            scene_frames.append(scene_frame)
        
        video.release()
        
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
    
    def _get_frame(self, video: cv2.VideoCapture, frame_no: int) -> Image.Image:
        """
        Extract a specific frame from video.
        
        Args:
            video: OpenCV video capture object
            frame_no: Frame number to extract
            
        Returns:
            PIL Image of the frame
        """
        video.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        _, frame = video.read()
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
            "selected_frames": [asdict(frame) for frame in result.selected_frames]
        }
        
        json_path = os.path.join(self.output_folder, f"{self.file_id}_mapping.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        
        print(f"JSON mapping saved to: {json_path}")


if __name__ == "__main__":
    video_path = r"D:\professional\LABELLERR\Task\Python_SDK\services\video_sampling\video.mp4"
    result = PySceneDetect(video_path, "video_001").detect_and_extract()