from typing import List, Dict
from pydantic import BaseModel, Field
from ImageDatasetCreation import ImageDatasetCreation
from VideoFrameExractor import DatasetFrames


class VideoToImageProjectResponse(BaseModel):
    status: str = Field(..., description="Status of project conversion")
    video_project_id: str = Field(..., description="Original video project ID")
    image_project_id: str = Field(..., description="Created image project ID")
    datasets_converted: List[str] = Field(..., description="List of converted dataset IDs")


class VideoToImageProjectConverter:
    
    def __init__(self, video_project_id: str, client_id: str) -> None:
        """Initialize the video to image project conversion with project and client details.
   
        Args:
            video_project_id (str): The video project identifier in the cloud system.
            client_id (str): The client identifier for authentication.
            
        Example:
            >>> converter = VideoToImageProjectConverter("video_proj_123", "client456")
        """
        self.video_project_id = video_project_id
        self.client_id = client_id
        
    def verify_video_project(self, client_id: str, video_project_id: str) -> bool:
        """Verify if the video project exists with provided client_id.
        
        Args:
            client_id (str): The client identifier for authentication.
            video_project_id (str): The video project identifier in the cloud system.
            
        Returns:
            bool: True if project exists, False otherwise.
            
        Example:
            >>> verify_video_project("client456", "video_proj_123")
            True
        """
        return True  # TODO: Implement actual project verification logic
    
    def get_video_datasets(self, video_project_id: str) -> List[str]:
        """Get all video dataset IDs associated with the video project.
        
        Args:
            video_project_id (str): The video project identifier in the cloud system.
        
        Returns:
            List[str]: List of video dataset IDs associated with the project.
            
        Example:
            >>> get_video_datasets("video_proj_123")
            ["video_dataset_1", "video_dataset_2", "video_dataset_3"]
        """
        return []  # TODO: Implement logic to extract dataset IDs from the project
    
    def convert_dataset_to_images(self, video_dataset_id: str, image_project_name: str) -> str:
        """Convert single video dataset to image dataset.
        
        Args:
            video_dataset_id (str): Video dataset ID to be converted.
            image_project_name (str): Name for the image project.
        
        Returns:
            str: Created image dataset ID.
            
        Example:
            >>> convert_dataset_to_images("video_dataset_1", "my_image_project")
            "image_dataset_1"
            
        Note:
            This function uses ImageDatasetCreation class to perform the conversion.
        """
        return "image_dataset_id"  # TODO: Implement conversion using ImageDatasetCreation
    
    def convert_project(self, image_project_name: str) -> VideoToImageProjectResponse:
        """Convert entire video project to image project.
        
        Args:
            image_project_name (str): The name of the new image project to be created.
            
        Returns:
            VideoToImageProjectResponse: Project conversion status and details.
            
        Example:
            >>> convert_project("my_image_project")
            VideoToImageProjectResponse(
                status="success",
                video_project_id="video_proj_123",
                image_project_id="image_proj_456",
                datasets_converted=["image_dataset_1", "image_dataset_2", "image_dataset_3"]
            )
        """
        return VideoToImageProjectResponse(
            status="success",
            video_project_id=self.video_project_id,
            image_project_id="image_project_id",
            datasets_converted=[]
        )  # TODO: Implement complete project conversion logic