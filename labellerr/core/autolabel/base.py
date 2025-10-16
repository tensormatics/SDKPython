from abc import ABCMeta
from ..client import LabellerrClient
from .typings import TrainingRequest
from .. import constants, client_utils
import uuid


class LabellerrAutoLabelMeta(ABCMeta):
    pass

class LabellerrAutoLabel(metaclass=LabellerrAutoLabelMeta):
    def __init__(self, client: LabellerrClient):
        self.client = client

    def train(self, training_request: TrainingRequest):
        # ------------------------------- [needs refactoring after we consolidate api_calls into one function ] ---------------------------------
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/ml_training/training/start?client_id={self.client.client_id}"
            f"&uuid={unique_id}"
        )
        headers = client_utils.build_headers(
            api_key=self.client.api_key,
            api_secret=self.client.api_secret,
            client_id=self.client.client_id,
            extra_headers={"content-type": "application/json"},
        )

        response = client_utils.request("POST", url, headers=headers, request_id=unique_id, json=training_request.model_dump())
        return response.get('response', None)
    
    def list_training_jobs(self):
        # ------------------------------- [needs refactoring after we consolidate api_calls into one function ] ---------------------------------
        unique_id = str(uuid.uuid4())
        url = (
            f"{constants.BASE_URL}/ml_training/training/list?client_id={self.client.client_id}"
            f"&uuid={unique_id}"
        )
        headers = client_utils.build_headers(
            api_key=self.client.api_key,
            api_secret=self.client.api_secret,
            client_id=self.client.client_id,
            extra_headers={"content-type": "application/json"},
        )

        response = client_utils.request("GET", url, headers=headers, request_id=unique_id)
        return response.get('response', None)