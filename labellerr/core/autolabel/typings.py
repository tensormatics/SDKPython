from pydantic import BaseModel
from typing import Optional

class Hyperparameters(BaseModel):
    epochs: int = 10

class TrainingRequest(BaseModel):
    model_id: str
    projects: Optional[list[str]] = None
    hyperparameters: Optional[Hyperparameters] = Hyperparameters()
    slice_id: Optional[str] = None
    min_samples_per_class: Optional[int] = 100
    job_name: str