from ...client import LabellerrClient
from ...exceptions import LabellerrError
from ... import constants
import uuid
import os
import subprocess
import requests
import pprint


# https://api.labellerr.com/data/file_data?file_id=c44f38f6-0186-436f-8c2d-ffb50a539c76&include_answers=false&project_id=gabrila_artificial_duck_74237&uuid=1d4c9b58-c6a4-4ca8-9583-b6b6cd25ef12


class FileMetadataService:
    def __init__(self, client: LabellerrClient):
        self.client = client
        
    def get_file_metadata(self, client_id: str, file_id: str, project_id: str, include_answers: bool = False):
        """
        Retrieve file metadata from Labellerr API.
        """
        try:
            unique_id = str(uuid.uuid4())
            
            # Build query parameters - include client_id here
            params = {
                'file_id': file_id,
                'include_answers': str(include_answers).lower(),
                'project_id': project_id,
                'uuid': unique_id,
                'client_id': client_id
            }
            
            url = f"{constants.BASE_URL}/data/file_data"
            
            
            headers = self.client._build_headers(
                client_id=client_id,
                extra_headers={
                    "Content-Type": "application/json",
                    "Origin": constants.ALLOWED_ORIGINS 
                }
            )
            
            # Make request using client's session if available
            response = self.client._make_request("GET", url, headers=headers, params=params)
            
            # Use client's response handler
            return self.client._handle_response(response, request_id=unique_id)
                    
        except Exception as e:
            raise LabellerrError(f"Failed to fetch file metadata: {str(e)}")
        
    def get_video_frames(self, client_id: str, file_id: str, project_id: str, dataset_id: str, frame_start: int = 0, frame_end: int = None):
        """
        Retrieve video frames data from Labellerr API.
        
        :param client_id: Client ID 
        :param file_id: Unique file identifier in Labellerr
        :param project_id: The project ID to which the file belongs
        :param dataset_id: The dataset ID containing the video file
        :param frame_start: Starting frame index (default: 0)
        :param frame_end: Ending frame index (if None, retrieves all frames from frame_start)
        :return: Dictionary containing video frames data
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{constants.BASE_URL}/data/video_frames"
            
            # Build query parameters
            params = {
                'dataset_id': dataset_id,
                'file_id': file_id,
                'frame_start': frame_start,
                'project_id': project_id,
                'uuid': unique_id,
                'client_id': client_id
            }
            
            # Add frame_end only if specified
            if frame_end is not None:
                params['frame_end'] = frame_end
            
            # Build headers using client's build_headers method
            headers = self.client._build_headers(
                client_id=client_id,
                extra_headers={
                    "Content-Type": "application/json",
                    "Origin": constants.ALLOWED_ORIGINS
                }
            )
            
            # Make request using client's session
            response = self.client._make_request("GET", url, headers=headers, params=params)
            
            # Use client's response handler
            return self.client._handle_response(response, request_id=unique_id)
                    
        except Exception as e:
            raise LabellerrError(f"Failed to fetch video frames data: {str(e)}")
        
    def download_video_frames(self, frames_data: dict, output_folder: str = None, file_id: str = None):
        """
        Download video frames from URLs to a local folder.
        
        :param frames_data: Dictionary with frame numbers as keys and URLs as values
        :param output_folder: Base folder path where frames will be saved (default: current directory)
        :param file_id: File ID to use as folder name. If None, uses 'frames' as folder name
        :return: Dictionary with download statistics
        """
        try:
            # Determine folder name
            if file_id:
                folder_name = file_id
            else:
                folder_name = "frames"
            
            # Set base output folder
            if output_folder:
                save_path = os.path.join(output_folder, folder_name)
            else:
                save_path = folder_name
            
            # Create directory if it doesn't exist
            os.makedirs(save_path, exist_ok=True)
            
            success_count = 0
            failed_frames = []
            
            print(f"Downloading {len(frames_data)} frames to: {save_path}")
            
            for frame_number, frame_url in frames_data.items():
                try:
                    # Create filename with frame number
                    filename = f"{frame_number}.jpg"
                    filepath = os.path.join(save_path, filename)
                    
                    # Download the frame
                    response = requests.get(frame_url, timeout=30)
                    
                    if response.status_code == 200:
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        success_count += 1
                        print(f"Downloaded: {filename}")
                    else:
                        failed_frames.append({
                            'frame': frame_number,
                            'status': response.status_code
                        })
                        print(f"Failed to download frame {frame_number}: Status {response.status_code}")
                        
                except Exception as e:
                    failed_frames.append({
                        'frame': frame_number,
                        'error': str(e)
                    })
                    print(f"Error downloading frame {frame_number}: {str(e)}")
            
            result = {
                'total_frames': len(frames_data),
                'successful_downloads': success_count,
                'failed_downloads': len(failed_frames),
                'save_path': save_path,
                'failed_frames': failed_frames
            }
            
            print(f"\nDownload complete: {success_count}/{len(frames_data)} frames downloaded successfully")
            
            return result
                    
        except Exception as e:
            raise LabellerrError(f"Failed to download video frames: {str(e)}")



class JoinVideoFrames:
    def __init__(self, frames_folder, output_file="output.mp4", framerate=30):
        """
        Initialize the JoinFrames class.

        :param frames_folder: Path to folder containing sequential frames (e.g., 1.jpg, 2.jpg).
        :param output_file: Name of the output video file.
        :param framerate: Desired video framerate (default: 30 fps).
        """
        self.frames_folder = frames_folder
        self.output_file = output_file
        self.framerate = framerate

    def join(self, pattern="%d.jpg"):
        """
        Join frames into a video using ffmpeg.

        :param pattern: Pattern for sequential frames inside frames_folder 
                        (default: frame%03d.jpg → frame001.jpg, frame002.jpg, ...).
        """
        input_pattern = os.path.join(self.frames_folder, pattern)

        # FFmpeg command
        command = [
            "ffmpeg",
            "-y",  # Overwrite output file if exists
            "-framerate", str(self.framerate),
            "-i", input_pattern,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            self.output_file
        ]

        try:
            print("Running command:", " ".join(command))
            subprocess.run(command, check=True)
            print(f"Video saved as {self.output_file}")
        except subprocess.CalledProcessError as e:
            print("Error while joining frames:", e)
    
    
if __name__ == "__main__":
    
    api_key = ""
    api_secret = ""
    client_id = "14078"
    dataset_id = "16257fd6-b91b-4d00-a680-9ece9f3f241c"
    project_id = "gabrila_artificial_duck_74237"
    file_id = "c44f38f6-0186-436f-8c2d-ffb50a539c76"
    
    client = LabellerrClient(api_key=api_key, api_secret=api_secret)
    
    file_service = FileMetadataService(client)
    
    
    # try:
    #     metadata = file_service.get_file_metadata(
    #         client_id, 
    #         file_id, 
    #         project_id, 
    #         include_answers=False)
    #     # pprint.pprint(metadata)
        
    #     total_frames = metadata['file_metadata']['total_frames']
    #     print(total_frames)
    # except LabellerrError as e:
    #     print("Error:", e)
    
    # try:
    #     frames_data = file_service.get_video_frames(
    #         client_id=client_id,
    #         file_id=file_id,
    #         project_id=project_id,
    #         dataset_id=dataset_id,
    #         frame_start=0,
    #         frame_end=total_frames
    #     )
        
    #     print(len(frames_data.keys()))
    #     pprint.pprint(frames_data)
    # except LabellerrError as e:
    #     print("Error:", e)
        
    # try:
    #     download_result = file_service.download_video_frames(
    #     frames_data=frames_data,
    #     output_folder="labellerr\download",  # Optional: specify base folder
    #     file_id=file_id  # Will create folder named with file_id
    # )  
    #     # pprint.pprint(frames_data)
    # except LabellerrError as e:
    #     print("Error:", e)
    
    # frames = r"D:\professional\LABELLERR\Task\Repos\SDKPython\labellerr\download\c44f38f6-0186-436f-8c2d-ffb50a539c76"
    # try:
    #     JoinVideoFrames(frames, 
    #                     output_file="labellerr/download/resultjoinvideo.mp4", 
    #                     framerate=30).join()
        
    # except LabellerrError as e:
    #     print("Error:", e)

    
    
class ImageFileService(FileMetadataService):
    pass

class VideoFileService(FileMetadataService):
    
    def download_video_frames(self, client_id: str, file_id: str, project_id: str):
        pass
    def get_video_frames(self, client_id: str, file_id: str, project_id: str):
        pass
    def create_video_from_frames(self, client_id: str, file_id: str, project_id: str):
        pass