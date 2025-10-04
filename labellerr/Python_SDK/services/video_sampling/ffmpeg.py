import subprocess
import os

class FFMPEG:
    def __init__(self, video_path: str, file_id: str):
        self.video_path = video_path
        self.file_id = file_id
        self.save_folder = file_id
        
    def detect_and_extract(self):
        """Extract keyframes from video and save to file_id folder"""
        os.makedirs(self.save_folder, exist_ok=True)
        
        output_pattern = os.path.join(self.save_folder, "%d.jpg")
        
        command = [
            "ffmpeg",
            "-i", self.video_path,
            "-vf", "select='eq(pict_type,PICT_TYPE_I)',showinfo",
            "-vsync", "vfr",
            "-frame_pts", "1",
            output_pattern
        ]
        
        try:
            subprocess.run(command, check=True)
            print(f"Keyframes extracted to {self.save_folder}")
        except subprocess.CalledProcessError as e:
            print(f"Error extracting keyframes: {e}")


if __name__ == "__main__":
    video_path = r"D:\professional\LABELLERR\Task\Repos\SDKPython\labellerr\Python_SDK\services\video_sampling\video.mp4"
    result = FFMPEG(video_path, "FFMPEG_sample_video_011").detect_and_extract()