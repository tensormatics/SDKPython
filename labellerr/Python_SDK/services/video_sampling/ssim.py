import os
import cv2
import numpy as np
from PIL import Image
from dataclasses import dataclass, asdict
from typing import List
import json
from skimage.metrics import structural_similarity as ssim


@dataclass
class SceneFrame:
    """Represents a detected scene with its extracted frame."""
    frame_path: str
    frame_no: int
    ssim_score: float
    

@dataclass
class DetectionResult:
    """Contains all detection results for a video."""
    file_id: str
    output_folder: str
    total_frames: int
    selected_frames: List[SceneFrame]
    

class SSIMSceneDetect:
    """SSIM-based scene detection and frame extraction for videos."""
    
    def __init__(self, video_path: str, file_id: str, threshold: float = 0.6, resize_dim: tuple = (320, 240)):
        """
        Initialize the SSIM scene detector.
        
        Args:
            video_path: Path to the video file
            file_id: Unique identifier for the video (used as output folder name)
            threshold: SSIM threshold for scene detection (lower = stricter, default: 0.6)
            resize_dim: Dimensions to resize frames for SSIM calculation (default: (320, 240))
        """
        self.video_path = video_path
        self.file_id = file_id
        self.output_folder = file_id
        self.threshold = threshold
        self.resize_dim = resize_dim
        
    def detect_and_extract(self) -> DetectionResult:
        """
        Detect scenes using SSIM and extract representative frames.
        
        Returns:
            DetectionResult containing file_id, output_folder, total_frames, and list of SceneFrame objects
        """
        # Create output folder
        os.makedirs(self.output_folder, exist_ok=True)
        
        # Open video for processing
        video = cv2.VideoCapture(self.video_path)
        
        if not video.isOpened():
            raise ValueError(f"Cannot open video: {self.video_path}")
        
        # Get total frames in video
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"Processing video: {self.video_path}")
        print(f"Total frames: {total_frames}")
        print(f"SSIM threshold: {self.threshold}")
        
        # Read first frame
        success, prev_frame = video.read()
        if not success:
            video.release()
            raise ValueError(f"Cannot read first frame from: {self.video_path}")
        
        # Extract and save frames
        scene_frames = []
        frame_count = 0
        
        # Always save first frame
        self._save_frame(prev_frame, frame_count, 1.0, scene_frames)
        print(f"Saved keyframe 0 at frame {frame_count} (First frame)")
        
        # Process remaining frames
        while True:
            success, curr_frame = video.read()
            if not success:
                break
            
            frame_count += 1
            
            # Calculate SSIM between current and previous frame
            ssim_score = self._calculate_ssim(prev_frame, curr_frame)
            
            # If SSIM is below threshold, it's a scene change
            if ssim_score < self.threshold:
                self._save_frame(curr_frame, frame_count, ssim_score, scene_frames)
                print(f"Saved keyframe {len(scene_frames) - 1} at frame {frame_count} (SSIM: {ssim_score:.3f})")
                prev_frame = curr_frame
            elif frame_count % 100 == 0:
                print(f"Frame {frame_count}: SSIM = {ssim_score:.3f} (threshold: {self.threshold})")
        
        video.release()
        
        print(f"\nExtracted {len(scene_frames)} keyframes from {frame_count + 1} frames.")
        
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
    
    def _calculate_ssim(self, frame1: np.ndarray, frame2: np.ndarray) -> float:
        """
        Calculate SSIM score between two frames.
        
        Args:
            frame1: First frame (BGR format)
            frame2: Second frame (BGR format)
            
        Returns:
            SSIM score (0-1, where 1 is identical)
        """
        # Resize frames for faster computation
        gray1 = cv2.cvtColor(cv2.resize(frame1, self.resize_dim), cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(cv2.resize(frame2, self.resize_dim), cv2.COLOR_BGR2GRAY)
        
        # Calculate SSIM
        score, _ = ssim(gray1, gray2, full=True)
        
        return score
    
    def _save_frame(self, frame: np.ndarray, frame_no: int, ssim_score: float, scene_frames: List[SceneFrame]) -> None:
        """
        Save a frame to disk and add to scene_frames list.
        
        Args:
            frame: Frame to save (BGR format)
            frame_no: Frame number
            ssim_score: SSIM score that triggered this frame
            scene_frames: List to append SceneFrame object to
        """
        # Convert BGR to RGB for PIL
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        
        # Save frame with frame number as filename
        frame_filename = f"{frame_no}.jpg"
        frame_path = os.path.join(self.output_folder, frame_filename)
        pil_image.save(frame_path)
        
        # Create SceneFrame object
        scene_frame = SceneFrame(
            frame_path=frame_path,
            frame_no=frame_no,
            ssim_score=ssim_score
        )
        scene_frames.append(scene_frame)
    
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
            "threshold": self.threshold,
            "resize_dim": self.resize_dim,
            "selected_frames": [asdict(frame) for frame in result.selected_frames]
        }
        
        json_path = os.path.join(self.output_folder, f"{self.file_id}_mapping.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        
        print(f"JSON mapping saved to: {json_path}")


# if __name__ == "__main__":
#     # Example usage
#     video_path = r"D:\professional\LABELLERR\Task\Repos\SDKPython\labellerr\Python_SDK\services\video_sampling\video.mp4"
    
#     # Create detector with custom parameters
#     detector = SSIMSceneDetect(
#         video_path=video_path,
#         file_id="video_001",
#         threshold=0.6,  # Lower value = more sensitive to changes
#         resize_dim=(320, 240)
#     )
    
#     # Detect and extract frames
#     result = detector.detect_and_extract()
    
#     print(f"\nDetection complete!")
#     print(f"Total frames extracted: {len(result.selected_frames)}")
#     print(f"Output folder: {result.output_folder}")