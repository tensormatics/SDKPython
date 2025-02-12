# labellerr/client.py

from concurrent import futures
import requests
import uuid
from .exceptions import LabellerrError
from unique_names_generator import get_random_name
from unique_names_generator.data import ADJECTIVES, NAMES, ANIMALS
import random
import json
import logging 
from datetime import datetime 
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from multiprocessing import cpu_count
import concurrent.futures

FILE_BATCH_SIZE=15 * 1024 * 1024
FILE_BATCH_COUNT=900
TOTAL_FILES_SIZE_LIMIT_PER_DATASET=2.5*1024*1024*1024
TOTAL_FILES_COUNT_LIMIT_PER_DATASET=2500
ANNOTATION_FORMAT=['json', 'coco_json', 'csv', 'png']
LOCAL_EXPORT_FORMAT=['json', 'coco_json', 'csv', 'png']
LOCAL_EXPORT_STATUS=['review', 'r_assigned','client_review', 'cr_assigned','accepted']

## DATA TYPES: image, video, audio, document, text
DATA_TYPES=('image', 'video', 'audio', 'document', 'text')
DATA_TYPE_FILE_EXT = {
    'image': ['.jpg','.jpeg', '.png', '.tiff'],
    'video': ['.mp4'],
    'audio': ['.mp3', '.wav'],
    'document': ['.pdf'],
    'text': ['.txt']
}

SCOPE_LIST=['project','client','public']
OPTION_TYPE_LIST=['input', 'radio', 'boolean', 'select', 'dropdown', 'stt', 'imc', 'BoundingBox', 'polygon', 'dot', 'audio']


# python -m unittest discover -s tests --run
# python setup.py sdist bdist_wheel -- build
create_dataset_parameters={}

class LabellerrClient:
    """
    A client for interacting with the Labellerr API.
    """
    def __init__(self, api_key, api_secret):
        """
        Initializes the LabellerrClient with API credentials.

        :param api_key: The API key for authentication.
        :param api_secret: The API secret for authentication.
        """
        self.api_key = api_key
        self.api_secret = api_secret
        # self.base_url = "https://api-gateway-qcb3iv2gaa-uc.a.run.app" #--dev
        self.base_url = "https://api.labellerr.com" #--prod

    def get_dataset(self, workspace_id, dataset_id, project_id):
        """
        Retrieves a dataset from the Labellerr API.

        :param workspace_id: The ID of the workspace.
        :param dataset_id: The ID of the dataset.
        :param project_id: The ID of the project.
        :return: The dataset as JSON.
        """
        url = f"{self.base_url}?client_id={workspace_id}&dataset_id={dataset_id}&project_id={project_id}&uuid={str(uuid.uuid4())}"
        headers = {
            'api_key': self.api_key,
            'api_secret': self.api_secret,
            'source':'sdk',
            'Origin': 'https://pro.labellerr.com'
        }
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise LabellerrError(f"Error {response.status_code}: {response.text}")
        return response.json()

    

    def create_empty_project(self, client_id, project_name, data_type,created_by, rotation_config=None):
        """
        Creates an empty project on the Labellerr API.

        :param client_id: The ID of the client.
        :param project_name: The name of the project.
        :param data_type: The type of data for the project.
        :param rotation_config: The rotation configuration for the project.
        :return: A dictionary containing the project ID, response status, and project configuration.
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/projects/create?stage=1&client_id={client_id}&uuid={unique_id}"

            project_id = get_random_name(combo=[NAMES, ADJECTIVES, ANIMALS], separator="_", style="lowercase") + '_' + str(random.randint(10000, 99999))

            payload = json.dumps({
                "project_id": project_id,
                "project_name": project_name,
                "data_type": data_type,
                "created_by":created_by
            })

            print(f"Create Empty Project Payload: {payload}")

            headers = {
                'client_id': str(client_id),
                'content-type': 'application/json',
                'api_key':self.api_key,
                'api_secret': self.api_secret,
                'source':'sdk',
                'origin': 'https://dev.labellerr.com'
            }

            response = requests.request("POST", url, headers=headers, data=payload)

            if response.status_code not in [200, 201]:
                if response.status_code >= 400 and response.status_code < 500:
                    raise LabellerrError({'error' :response.json(),'code':response.status_code})
                elif response.status_code >= 500:
                    raise LabellerrError({
                        'status': 'internal server error',
                        'message': 'Please contact support with the request tracking id',
                        'request_id': unique_id
                    })


            print("Updating rotation configuration . . .")
            if rotation_config is None:
                rotation_config = {
                    'annotation_rotation_count':1,
                    'review_rotation_count':1,
                    'client_review_rotation_count':1
                }

            self.rotation_config=rotation_config
            self.project_id=project_id
            self.client_id=client_id
                
            rotation_request_response=self.update_rotation_count()
            print("Rotation configuration updated successfully.")
            return {'project_id': project_id, 'response': 'success','project_config':rotation_request_response}
        except LabellerrError as e:
            logging.error(f"Failed to create project: {e}")
            raise

    def update_rotation_count(self):

        """
        Updates the rotation count for a project.

        :return: A dictionary indicating the success of the operation.
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/projects/rotations/add?project_id={self.project_id}&client_id={self.client_id}&uuid={unique_id}"

            headers = {
                'client_id': self.client_id,
                'content-type': 'application/json',
                'api_key': self.api_key,
                'api_secret': self.api_secret,

                'origin': 'https://dev.labellerr.com'
                }

            payload = json.dumps(self.rotation_config)
            print(f"Update Rotation Count Payload: {payload}")

            response = requests.request("POST", url, headers=headers, data=payload)

            print("Rotation configuration updated successfully.")

            if response.status_code not in [200, 201]:
                if response.status_code >= 400 and response.status_code < 500:
                    raise LabellerrError({'error' :response.json(),'code':response.status_code})
                elif response.status_code >= 500:
                    raise LabellerrError({
                        'status': 'internal server error',
                        'message': 'Please contact support with the request tracking id',
                        'request_id': unique_id
                    })

            return {'msg': 'project rotation configuration updated'}
        except LabellerrError as e:
            logging.error(f"Project rotation update config failed: {e}")
            raise

    def create_dataset(self,dataset_config):
        """
        Creates an empty dataset.

        :param dataset_config: A dictionary containing the configuration for the dataset.
        :return: A dictionary containing the response status and the ID of the created dataset.
        """
        try:
            # dataset_config['data_type'] has to be one of the items from DATA_TYPES
            # Validate data_type
            if dataset_config.get('data_type') not in DATA_TYPES:
                raise LabellerrError(f"Invalid data_type. Must be one of {DATA_TYPES}")
            dataset_id=f"dataset-{dataset_config['data_type']}-{uuid.uuid4().hex[:8]}"

            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/datasets/create?client_id={dataset_config['client_id']}&uuid={unique_id}"
            headers = {
                'client_id': str(dataset_config['client_id']),
                'content-type': 'application/json',
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'source':'sdk',
                'origin': 'https://dev.labellerr.com'
                }
           
            payload = json.dumps(
                {
                    "dataset_id": dataset_id,
                    "dataset_name": dataset_config['dataset_name'],
                    "dataset_description": dataset_config['dataset_description'],
                    "data_type": dataset_config['data_type'],
                    "created_by": dataset_config['created_by'],
                    "permission_level": "project",
                    "type": "client",
                    "labelled": "unlabelled",
                    "data_copy": "false",
                    "isGoldDataset": False,
                    "files_count": 0,
                    "access": "write",
                    "created_at": datetime.now().isoformat(),
                    "id": f"dataset-{dataset_config['data_type']}-{uuid.uuid4().hex[:8]}",
                    "name": dataset_config['dataset_name'],
                    "description": dataset_config['dataset_description']
                }
            )

            response = requests.request("POST", url, headers=headers, data=payload)
            if response.status_code not in [200, 201]:
                if response.status_code >= 400 and response.status_code < 500:
                    raise LabellerrError({'error' :response.json(),'code':response.status_code})
                elif response.status_code >= 500:
                    raise LabellerrError({
                        'status': 'internal server error',
                        'message': 'Please contact support with the request tracking id',
                        'request_id': unique_id
                    })


            return {'response': 'success','dataset_id':dataset_id}

        except LabellerrError as e:
            logging.error(f"Failed to create dataset: {e}")
            raise

    def get_all_dataset(self,client_id,datatype,project_id,scope):
        """
        Retrieves a dataset by its ID.

        :param client_id: The ID of the client.
        :param datatype: The type of data for the dataset.
        :return: The dataset as JSON.
        """
        # validate parameters
        if not isinstance(client_id, str):
            raise LabellerrError("client_id must be a string")
        if not isinstance(datatype, str):
            raise LabellerrError("datatype must be a string")
        if not isinstance(project_id, str):
            raise LabellerrError("project_id must be a string")
        if not isinstance(scope, str):
            raise LabellerrError("scope must be a string")
        # scope value should on in the list SCOPE_LIST
        if scope not in SCOPE_LIST:
            raise LabellerrError(f"scope must be one of {', '.join(SCOPE_LIST)}")

        # get dataset
        try:
            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/datasets/list?client_id={client_id}&data_type={datatype}&permission_level={scope}&project_id={project_id}&uuid={unique_id}"
            headers = {
                'client_id': client_id,
                'content-type': 'application/json',
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'source':'sdk',
                'origin': 'https://dev.labellerr.com'
                }

            response = requests.request("GET", url, headers=headers)

            if response.status_code not in [200, 201]:
                if response.status_code >= 400 and response.status_code < 500:
                    raise LabellerrError({'error' :response.json(),'code':response.status_code})
                elif response.status_code >= 500:
                    raise LabellerrError({
                        'status': 'internal server error',
                        'message': 'Please contact support with the request tracking id',
                        'request_id': unique_id
                    })
            return response.json()
        except LabellerrError as e:
            logging.error(f"Failed to retrieve dataset: {e}")
            raise

    def get_total_folder_file_count_and_total_size(self,folder_path,data_type):
        """
        Retrieves the total count and size of files in a folder.

        :param folder_path: The path to the folder.
        :param data_type: The type of data for the files.
        :return: The total count and size of the files.
        """
        total_file_count=0
        total_file_size=0
        files_list=[]
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                # print('>>  ',file_path)
                try:
                    # check if the file extention matching based on datatype
                    if not any(file.endswith(ext) for ext in DATA_TYPE_FILE_EXT[data_type]):
                        continue
                    files_list.append(file_path)
                    file_size = os.path.getsize(file_path)
                    total_file_count += 1
                    total_file_size += file_size
                except Exception as e:
                    print(f"Error reading {file_path}: {str(e)}")

        return total_file_count, total_file_size, files_list
    

    def get_total_file_count_and_total_size(self,files_list,data_type):
        """
        Retrieves the total count and size of files in a list.

        :param files_list: The list of file paths.
        :param data_type: The type of data for the files.
        :return: The total count and size of the files.
        """
        total_file_count=0
        total_file_size=0
        # for root, dirs, files in os.walk(folder_path):
        for file_path in files_list:
            if file_path is None:
                continue
            try:
                # check if the file extention matching based on datatype
                if not any(file_path.endswith(ext) for ext in DATA_TYPE_FILE_EXT[data_type]):
                    continue
                file_size = os.path.getsize(file_path)
                total_file_count += 1
                total_file_size += file_size
            except OSError as e:
                print(f"Error reading {file_path}: {str(e)}")
            except Exception as e:
                print(f"Unexpected error reading {file_path}: {str(e)}")

        return total_file_count, total_file_size, files_list


    def upload_folder_files_to_dataset(self, data_config):
        """
        Uploads local files from a folder to a dataset using parallel processing.

        :param data_config: A dictionary containing the configuration for the data.
        :return: A dictionary containing the response status and the list of successfully uploaded files.
        :raises LabellerrError: If there are issues with file limits, permissions, or upload process
        """
        try:
            # Validate required fields in data_config
            required_fields = ['data_type', 'dataset_id', 'client_id', 'folder_path']
            missing_fields = [field for field in required_fields if field not in data_config]
            if missing_fields:
                raise LabellerrError(f"Missing required fields in data_config: {', '.join(missing_fields)}")

            # Validate folder path exists and is accessible
            if not os.path.exists(data_config['folder_path']):
                raise LabellerrError(f"Folder path does not exist: {data_config['folder_path']}")
            if not os.path.isdir(data_config['folder_path']):
                raise LabellerrError(f"Path is not a directory: {data_config['folder_path']}")
            if not os.access(data_config['folder_path'], os.R_OK):
                raise LabellerrError(f"No read permission for folder: {data_config['folder_path']}")

            unique_id = str(uuid.uuid4())
            try:
                url = f"{self.base_url}/connectors/upload/local?data_type={data_config['data_type']}&dataset_id={data_config['dataset_id']}&project_id=null&project_independent=false&client_id={data_config['client_id']}&uuid={unique_id}"
                data_config['url'] = url
            except KeyError as e:
                raise LabellerrError(f"Missing required field in data_config for URL construction: {str(e)}")
            
            success_queue = []
            fail_queue = []

            try:
                # Get files from folder
                total_file_count, total_file_volumn, filenames = self.get_total_folder_file_count_and_total_size(
                    data_config['folder_path'], 
                    data_config['data_type']
                )
            except Exception as e:
                raise LabellerrError(f"Failed to analyze folder contents: {str(e)}")
            
            # Check file limits
            if total_file_count > TOTAL_FILES_COUNT_LIMIT_PER_DATASET:
                raise LabellerrError(f"Total file count: {total_file_count} exceeds limit of {TOTAL_FILES_COUNT_LIMIT_PER_DATASET} files")
            if total_file_volumn > TOTAL_FILES_SIZE_LIMIT_PER_DATASET:
                raise LabellerrError(f"Total file size: {total_file_volumn/1024/1024:.1f}MB exceeds limit of {TOTAL_FILES_SIZE_LIMIT_PER_DATASET/1024/1024:.1f}MB")

            print(f"Total file count: {total_file_count}")
            print(f"Total file size: {total_file_volumn/1024/1024:.1f} MB")

            # Group files into batches based on FILE_BATCH_SIZE
            batches = []
            current_batch = []
            current_batch_size = 0

            for file_path in filenames:
                try:
                    file_size = os.path.getsize(file_path)
                    if current_batch_size + file_size > FILE_BATCH_SIZE or len(current_batch) >= FILE_BATCH_COUNT:
                        if current_batch:
                            batches.append(current_batch)
                        current_batch = [file_path]
                        current_batch_size = file_size
                    else:
                        current_batch.append(file_path)
                        current_batch_size += file_size
                except OSError as e:
                    print(f"Error accessing file {file_path}: {str(e)}")
                    fail_queue.append(file_path)
                except Exception as e:
                    print(f"Unexpected error processing {file_path}: {str(e)}")
                    fail_queue.append(file_path)

            if current_batch:
                batches.append(current_batch)

            if not batches:
                raise LabellerrError("No valid files found to upload in the specified folder")

            print('CPU count', cpu_count(), " Batch Count", len(batches))

            # Calculate optimal number of workers based on CPU count and batch count
            max_workers = min(
                cpu_count(),  # Number of CPU cores
                len(batches),  # Number of batches
                20
            )

            # Process batches in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_batch = {
                    executor.submit(self._process_batch, data_config, batch): batch 
                    for batch in batches
                }

                for future in as_completed(future_to_batch):
                    batch = future_to_batch[future]
                    try:
                        result = future.result()
                        if result['success']:
                            success_queue.extend(batch)
                        else:
                            fail_queue.extend(batch)
                    except Exception as e:
                        print(f"Batch upload failed: {str(e)}")
                        fail_queue.extend(batch)

            if not success_queue and fail_queue:
                raise LabellerrError("All file uploads failed. Check individual file errors above.")

            return {
                'track_id': unique_id,
                'success': success_queue,
                'fail': fail_queue
            }
        
        except LabellerrError:
            raise
        except Exception as e:
            raise LabellerrError(f"Failed to upload files: {str(e)}")

    def _process_batch(self, data_config, batch):
        """
        Helper method to process a batch of files.

        :param data_config: The data configuration dictionary
        :param batch: List of file paths to process
        :return: Dictionary indicating success/failure
        """
        files = []
        try:
            # Open all files in the batch
            for file_path in batch:
                try:
                    filename = os.path.basename(file_path)
                    file_obj = open(file_path, 'rb')
                    files.append(('file', (filename, file_obj, 'application/octet-stream')))
                except Exception as e:
                    print(f"Error reading file {file_path}: {str(e)}")
                    return {'success': False}

            print(f"processing a batch of {len(files)} files . . .")
            response = self.commence_files_upload(data_config, files)
            print('----------------------')
            print("Batch processing done ", response)
            return {'success': True if response.status_code == 200 else False}
        except Exception as e:
            print(f"Batch processing error: {str(e)}")
            raise LabellerrError(f"Batch processing error: {str(e)}")
        finally:
            # Ensure all files are properly closed
            for _, (_, file_obj, _) in files:
                try:
                    file_obj.close()
                except:
                    pass

    def commence_files_upload(self,data_config,files_to_send):
        """
        Commences the upload of files to the API.

        :param data_config: The dictionary containing the configuration for the data.
        :param files_to_send: The list of file tuples to send.
        :return: The response from the API.
        :raises LabellerrError: If the upload fails.
        """
        try:
            print(f"Uploading {len(files_to_send)} file(s)")
            # put a delay of 3 secs
            time.sleep(3)
            headers = {
                    'client_id': data_config['client_id'],
                    'api_key': self.api_key,
                    'api_secret': self.api_secret,
                    'source':'sdk',
                    'origin': 'https://dev.labellerr.com'
                }

            response = requests.post(
                data_config['url'], 
                headers=headers, 
                data={}, 
                files=files_to_send
            )
            
            if response.status_code not in [200, 201]:
                if response.status_code >= 400 and response.status_code < 500:
                    raise LabellerrError({'error' :response.json(),'code':response.status_code})
                elif response.status_code >= 500:
                    raise LabellerrError({
                        'status': 'internal server error',
                        'message': 'Please contact support with the request tracking id',
                        'request_id': unique_id
                    })
            return response
        except requests.exceptions.RequestException as e:
            raise LabellerrError(f"Request failed: {str(e)}")
        except Exception as e:
            raise LabellerrError(f"An error occurred during file upload: {str(e)}")

    def upload_files(self,client_id,dataset_id,data_type,files_list):
        """
        Uploads files to the API.

        :param client_id: The ID of the client.
        :param dataset_id: The ID of the dataset.
        :param data_type: The type of data.
        :param files_list: The list of files to upload or a comma-separated string of file paths.
        :return: The response from the API.
        :raises LabellerrError: If the upload fails.
        """
        try:
            # Convert string input to list if necessary
            if isinstance(files_list, str):
                files_list = files_list.split(',')
            elif not isinstance(files_list, list):
                raise LabellerrError("files_list must be either a list or a comma-separated string")

            if len(files_list) == 0:
                raise LabellerrError("No files to upload")

            # Validate files exist
            for file_path in files_list:
                if not os.path.exists(file_path):
                    raise LabellerrError(f"File does not exist: {file_path}")
                if not os.path.isfile(file_path):
                    raise LabellerrError(f"Path is not a file: {file_path}")

            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/connectors/upload/local?data_type={data_type}&dataset_id={dataset_id}&project_id=null&project_independent=false&client_id={client_id}&uuid={unique_id}"

            config = {
                'client_id': client_id,
                'dataset_id': dataset_id,
                'project_id': 'null',
                'data_type': data_type,
                'url': url,
                'project_independent': 'false'
            }

            # Prepare files for upload
            files = []
            try:
                for file_path in files_list:
                    file_name = os.path.basename(file_path)
                    file_obj = open(file_path, 'rb')
                    files.append(('file', (file_name, file_obj, 'application/octet-stream')))
                
                response = self.commence_files_upload(config, files)
                return response
            finally:
                # Ensure all files are closed
                for _, (_, file_obj, _) in files:
                    try:
                        file_obj.close()
                    except:
                        pass

        except Exception as e:
            logging.error(f"Failed to upload files : {str(e)}")
            raise LabellerrError(f"Failed to upload files : {str(e)}")

    

    def upload_folder_content(self,client_id,dataset_id,data_type,folder_path):

        """
        Uploads the content of a folder to the API.

        :param client_id: The ID of the client.
        :param dataset_id: The ID of the dataset.
        :param data_type: The type of data.
        :param folder_path: The path to the folder.
        :return: The response from the API.
        :raises LabellerrError: If the upload fails.
        """
        
        try:
            if not os.path.exists(folder_path) or not os.path.isdir(folder_path) or not os.listdir(folder_path):
                raise LabellerrError("Invalid or empty folder path")
            
            config = {
                'client_id': client_id,
                'dataset_id': dataset_id,
                'project_id': 'null',
                'data_type': data_type,
                'folder_path': folder_path,
                'project_independent':'false'
            }

            response = self.upload_folder_files_to_dataset(config)
            
            return response
        except Exception as e:
            logging.error(f"Failed to upload folder content: {str(e)}")
            raise LabellerrError(f"Failed to upload folder content: {str(e)}")
        
    
        

    def get_all_project_per_client_id(self,client_id):

        """
        Retrieves a list of projects associated with a client ID.

        :param client_id: The ID of the client.
        :return: A dictionary containing the list of projects.
        :raises LabellerrError: If the retrieval fails.
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/project_drafts/projects/detailed_list?client_id={client_id}&uuid={unique_id}"

            payload = {}
            headers = {
                'client_id': str(client_id),
                'content-type': 'application/json',
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'source':'sdk',
                'origin': 'https://dev.labellerr.com'
            }

            response = requests.request("GET", url, headers=headers, data=payload)

            if response.status_code not in [200, 201]:
                if response.status_code >= 400 and response.status_code < 500:
                    raise LabellerrError({'error' :response.json(),'code':response.status_code})
                elif response.status_code >= 500:
                    raise LabellerrError({
                        'status': 'internal server error',
                        'message': 'Please contact support with the request tracking id',
                        'request_id': unique_id
                    })

            print(response.text)
            return response.json()
        except Exception as e:
            logging.error(f"Failed to retrieve projects: {str(e)}")
            raise LabellerrError(f"Failed to retrieve projects: {str(e)}")

    
                        
    def link_dataset_to_project(self, client_id,project_id,dataset_id):
        """
        Links a dataset to a project.

        :param client_id: The ID of the client.
        :param project_id: The ID of the project.
        :param dataset_id: The ID of the dataset.
        :return: The response from the API.
        :raises LabellerrError: If the linking fails.
        """
        try:
            unique_id = str(uuid.uuid4())
            url = f"{self.base_url}/datasets/project/link?client_id={client_id}&dataset_id={dataset_id}&project_id={project_id}&uuid={unique_id}"

            payload = {}
            
            headers = {
                'client_id': str(client_id),
                'content-type': 'application/json',
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'source':'sdk',
                'origin': 'https://dev.labellerr.com'
            }            

            response = requests.request("GET", url, headers=headers, data=payload)

            if response.status_code not in [200, 201]:
                if response.status_code >= 400 and response.status_code < 500:
                    raise LabellerrError({'error' :response.json(),'code':response.status_code})
                elif response.status_code >= 500:
                    raise LabellerrError({
                        'status': 'internal server error',
                        'message': 'Please contact support with the request tracking id',
                        'request_id': unique_id
                    })
            response=response.json()
            return response
        except Exception as e:
            logging.error(f"Failed to link the data with the projects :{str(e)}")
            raise LabellerrError(f"Failed to link the data with the projects : {str(e)}")
    



    def update_project_annotation_guideline(self,config):

        """
        Updates the annotation guideline for a project.

        :param config: A dictionary containing the project ID, data type, client ID, autolabel status, and the annotation guideline.
        :return: None
        :raises LabellerrError: If the update fails.
        """
        unique_id = str(uuid.uuid4())

        url = f"{self.base_url}/annotations/add_questions?project_id={config['project_id']}&auto_label={config['autolabel']}&data_type={config['data_type']}&client_id={config['client_id']}&uuid={unique_id}"

        guide_payload = json.dumps(config['annotation_guideline'])
        
        headers = {
            'client_id': str(config['client_id']),
            'content-type': 'application/json',
            'api_key': self.api_key,
            'api_secret': self.api_secret,
            'source':'sdk',
            'origin': 'https://dev.labellerr.com'
        }    

        # print('annotation_guide -- ', guide_payload)
        try:
            response = requests.request("POST", url, headers=headers, data=guide_payload)
            
            if response.status_code not in [200, 201]:
                if response.status_code >= 400 and response.status_code < 500:
                    raise LabellerrError({'error' :response.json(),'code':response.status_code})
                elif response.status_code >= 500:
                    raise LabellerrError({
                        'status': 'internal server error',
                        'message': 'Please contact support with the request tracking id',
                        'request_id': unique_id
                    })
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to update project annotation guideline: {str(e)}")
            raise LabellerrError(f"Failed to update project annotation guideline: {str(e)}")
        
    

    def validate_rotation_config(self,rotation_config):
        """
        Validates a rotation configuration.

        :param rotation_config: A dictionary containing the configuration for the rotations.
        :raises LabellerrError: If the configuration is invalid.
        """
        annotation_rotation_count = rotation_config.get('annotation_rotation_count')
        review_rotation_count = rotation_config.get('review_rotation_count')
        client_review_rotation_count = rotation_config.get('client_review_rotation_count')

        # Validate review_rotation_count
        if review_rotation_count != 1:
            raise LabellerrError("review_rotation_count must be 1")

        # Validate client_review_rotation_count based on annotation_rotation_count
        if annotation_rotation_count == 0 and client_review_rotation_count != 0:
            raise LabellerrError("client_review_rotation_count must be 0 when annotation_rotation_count is 0")
        elif annotation_rotation_count == 1 and client_review_rotation_count not in [0, 1]:
            raise LabellerrError("client_review_rotation_count can only be 0 or 1 when annotation_rotation_count is 1")
        elif annotation_rotation_count > 1 and client_review_rotation_count != 0:
            raise LabellerrError("client_review_rotation_count must be 0 when annotation_rotation_count is greater than 1")


    def _upload_preannotation_sync(self, project_id, client_id, annotation_format, annotation_file):
        """
        Synchronous implementation of preannotation upload.

        :param project_id: The ID of the project.
        :param client_id: The ID of the client.
        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :return: The response from the API.
        :raises LabellerrError: If the upload fails.
        """
        try:
            # validate all the parameters
            required_params = ['project_id', 'client_id', 'annotation_format', 'annotation_file']
            for param in required_params:
                if param not in locals():
                    raise LabellerrError(f"Required parameter {param} is missing")
                
            if annotation_format not in ANNOTATION_FORMAT:
                raise LabellerrError(f"Invalid annotation_format. Must be one of {ANNOTATION_FORMAT}")
            
            url = f"{self.base_url}/actions/upload_answers?project_id={project_id}&answer_format={annotation_format}&client_id={client_id}"

            # validate if the file exist then extract file name from the path
            if os.path.exists(annotation_file):
                file_name = os.path.basename(annotation_file)
            else:
                raise LabellerrError("File not found")

            payload = {}
            with open(annotation_file, 'rb') as f:
                files = [
                    ('file', (file_name, f, 'application/octet-stream'))
                ]
                response = requests.request("POST", url, headers={
                    'client_id': client_id,
                    'api_key': self.api_key,
                    'api_secret': self.api_secret,
                    'origin': 'https://dev.labellerr.com',
                    'source':'sdk',
                    'email_id': self.api_key
                }, data=payload, files=files)
            response_data=response.json()

            if response.status_code not in [200, 201]:
                if response.status_code >= 400 and response.status_code < 500:
                    raise LabellerrError({'error' :response.json(),'code':response.status_code})
                elif response.status_code >= 500:
                    raise LabellerrError({
                        'status': 'internal server error',
                        'message': 'Please contact support with the request tracking id',
                        'request_id': unique_id
                    })

            print('response_data -- ', response_data)
            # read job_id from the response
            job_id = response_data['response']['job_id']
            self.client_id = client_id
            self.job_id = job_id
            self.project_id = project_id

            print(f"Preannotation upload successful. Job ID: {job_id}")
            if response.status_code != 200:
                raise LabellerrError(f"Failed to upload preannotation: {response.text}")
            
            return self.preannotation_job_status()
        except Exception as e:
            logging.error(f"Failed to upload preannotation: {str(e)}")
            raise LabellerrError(f"Failed to upload preannotation: {str(e)}")

    def upload_preannotation_by_project_id_async(self, project_id, client_id, annotation_format, annotation_file):
        """
        Asynchronously uploads preannotation data to a project.

        :param project_id: The ID of the project.
        :param client_id: The ID of the client.
        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :return: A Future object that will contain the response from the API.
        :raises LabellerrError: If the upload fails.
        """
        def upload_and_monitor():
            try:
                # validate all the parameters
                required_params = ['project_id', 'client_id', 'annotation_format', 'annotation_file']
                for param in required_params:
                    if param not in locals():
                        raise LabellerrError(f"Required parameter {param} is missing")
                    
                if annotation_format not in ANNOTATION_FORMAT:
                    raise LabellerrError(f"Invalid annotation_format. Must be one of {ANNOTATION_FORMAT}")
                
                url = f"{self.base_url}/actions/upload_answers?project_id={project_id}&answer_format={annotation_format}&client_id={client_id}"

                # validate if the file exist then extract file name from the path
                if os.path.exists(annotation_file):
                    file_name = os.path.basename(annotation_file)
                else:
                    raise LabellerrError("File not found")

                payload = {}
                with open(annotation_file, 'rb') as f:
                    files = [
                        ('file', (file_name, f, 'application/octet-stream'))
                    ]
                    response = requests.request("POST", url, headers={
                        'client_id': client_id,
                        'api_key': self.api_key,
                        'api_secret': self.api_secret,
                        'origin': 'https://dev.labellerr.com',
                        'source':'sdk',
                        'email_id': self.api_key
                    }, data=payload, files=files)
                response_data=response.json()
                if response.status_code not in [200, 201]:
                    if response.status_code >= 400 and response.status_code < 500:
                        raise LabellerrError({'error' :response.json(),'code':response.status_code})
                    elif response.status_code >= 500:
                        raise LabellerrError({
                            'status': 'internal server error',
                            'message': 'Please contact support with the request tracking id',
                            'request_id': unique_id
                        })                
                print('response_data -- ', response_data)
                # read job_id from the response
                job_id = response_data['response']['job_id']
                self.client_id = client_id
                self.job_id = job_id
                self.project_id = project_id

                print(f"Preannotation upload successful. Job ID: {job_id}")
                if response.status_code != 200:
                    raise LabellerrError(f"Failed to upload preannotation: {response.text}")
                
                # Now monitor the status
                headers = {
                    'client_id': str(self.client_id),
                    'Origin': 'https://app.labellerr.com',
                    'api_key': self.api_key,
                    'api_secret': self.api_secret
                }
                status_url = f"{self.base_url}/actions/upload_answers_status?project_id={self.project_id}&job_id={self.job_id}&client_id={self.client_id}"
                while True:
                    try:
                        response = requests.request("GET", status_url, headers=headers, data={})
                        status_data = response.json()
                        
                        print(' >>> ', status_data)

                        # Check if job is completed
                        if status_data.get('response', {}).get('status') == 'completed':
                            return status_data
                            
                        print('retrying after 5 seconds . . .')
                        time.sleep(5)
                        
                    except Exception as e:
                        logging.error(f"Failed to get preannotation job status: {str(e)}")
                        raise LabellerrError(f"Failed to get preannotation job status: {str(e)}")
                
            except Exception as e:
                logging.error(f"Failed to upload preannotation: {str(e)}")
                raise LabellerrError(f"Failed to upload preannotation: {str(e)}")

        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(upload_and_monitor)

    def preannotation_job_status_async(self):
        """
        Get the status of a preannotation job asynchronously.
        
        Returns:
            concurrent.futures.Future: A future that will contain the final job status
        """
        def check_status():
            headers = {
                'client_id': str(self.client_id),
                'Origin': 'https://app.labellerr.com',
                'api_key': self.api_key,
                'api_secret': self.api_secret
            }
            url = f"{self.base_url}/actions/upload_answers_status?project_id={self.project_id}&job_id={self.job_id}&client_id={self.client_id}"
            payload = {}
            while True:
                try:
                    response = requests.request("GET", url, headers=headers, data=payload)
                    response_data = response.json()
                    
                    # Check if job is completed
                    if response_data.get('response', {}).get('status') == 'completed':
                        return response_data
                        
                    print('retrying after 5 seconds . . .')
                    time.sleep(5)
                    
                except Exception as e:
                    logging.error(f"Failed to get preannotation job status: {str(e)}")
                    raise LabellerrError(f"Failed to get preannotation job status: {str(e)}")
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(check_status)

    def upload_preannotation_by_project_id(self,project_id,client_id,annotation_format,annotation_file):

        """
        Uploads preannotation data to a project.

        :param project_id: The ID of the project.
        :param client_id: The ID of the client.
        :param annotation_format: The format of the preannotation data.
        :param annotation_file: The file path of the preannotation data.
        :return: The response from the API.
        :raises LabellerrError: If the upload fails.
        """
        try:
            # validate all the parameters
            required_params = ['project_id', 'client_id', 'annotation_format', 'annotation_file']
            for param in required_params:
                if param not in locals():
                    raise LabellerrError(f"Required parameter {param} is missing")
                
            if annotation_format not in ANNOTATION_FORMAT:
                raise LabellerrError(f"Invalid annotation_format. Must be one of {ANNOTATION_FORMAT}")
            

            url = f"{self.base_url}/actions/upload_answers?project_id={project_id}&answer_format={annotation_format}&client_id={client_id}"

            # validate if the file exist then extract file name from the path
            if os.path.exists(annotation_file):
                file_name = os.path.basename(annotation_file)
            else:
                raise LabellerrError("File not found")

            payload = {}
            with open(annotation_file, 'rb') as f:
                files = [
                    ('file', (file_name, f, 'application/octet-stream'))
                ]
                response = requests.request("POST", url, headers={
                    'client_id': client_id,
                    'api_key': self.api_key,
                    'api_secret': self.api_secret,
                    'origin': 'https://dev.labellerr.com',
                    'source':'sdk',
                    'email_id': self.api_key
                }, data=payload, files=files)
            response_data=response.json()
            print('response_data -- ', response_data)
            # read job_id from the response
            job_id = response_data['response']['job_id']
            self.client_id = client_id
            self.job_id = job_id
            self.project_id = project_id

            print(f"Preannotation upload successful. Job ID: {job_id}")
            if response.status_code != 200:
                raise LabellerrError(f"Failed to upload preannotation: {response.text}")
            
            future = self.preannotation_job_status_async()
            return future.result() 
        except Exception as e:
            logging.error(f"Failed to upload preannotation: {str(e)}")
            raise LabellerrError(f"Failed to upload preannotation: {str(e)}")

    def create_local_export(self,project_id,client_id,export_config):

        required_params = ['export_name', 'export_description', 'export_format','statuses']

        if project_id is None:
            raise LabellerrError("project_id cannot be null")

        if client_id is None:
            raise LabellerrError("client_id cannot be null")

        if export_config is None:
            raise LabellerrError("export_config cannot be null")

        for param in required_params:
            if param not in export_config:
                raise LabellerrError(f"Required parameter {param} is missing")
            if param == 'export_format':
                if export_config[param] not in LOCAL_EXPORT_FORMAT:
                    raise LabellerrError(f"Invalid export_format. Must be one of {LOCAL_EXPORT_FORMAT}")
            if param == 'statuses':
                if not isinstance(export_config[param], list):
                    raise LabellerrError(f"Invalid statuses. Must be an array")
                for status in export_config[param]:
                    if status not in LOCAL_EXPORT_STATUS:
                        raise LabellerrError(f"Invalid status. Must be one of {LOCAL_EXPORT_STATUS}")


        try:
            export_config.update({
                "export_destination": "local",
                "question_ids": [
                    "all"
                ]
            })
            payload = json.dumps(export_config)
            response = requests.post(
                f"{self.base_url}/sdk/export/files?project_id={project_id}&client_id={client_id}",
                headers={
                    'api_key': self.api_key,
                    'api_secret': self.api_secret,
                    'Origin': 'https://dev.labellerr.com',
                    'Content-Type': 'application/json'
                },
                data=payload
            )

            if response.status_code not in [200, 201]:
                if response.status_code >= 400 and response.status_code < 500:
                    raise LabellerrError({'error' :response.json(),'code':response.status_code})
                elif response.status_code >= 500:
                    raise LabellerrError({
                        'status': 'internal server error',
                        'message': 'Please contact support with the request tracking id',
                        'request_id': unique_id
                    })
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to create local export: {str(e)}")
            raise LabellerrError(f"Failed to create local export: {str(e)}")

    def initiate_create_project(self,payload):

        # Creating an empty dataset by function call
        """
        Creates an empty project.

        :param payload: A dictionary containing the configuration for the project.
        :return: A dictionary containing the dataset ID, project ID, and project configuration.
        """
        
        try:
            result={}
            # print('Payload  >>> ',payload)

            # validate all the parameters
            required_params = ['client_id', 'dataset_name', 'dataset_description', 'data_type', 'created_by', 'project_name','annotation_guide','autolabel']
            for param in required_params:
                if param not in payload:
                    raise LabellerrError(f"Required parameter {param} is missing")
                if(param == 'client_id'):
                    # it should be an instance of string
                    if not isinstance(payload[param], str) or not payload[param].strip():
                        raise LabellerrError(f"client_id must be a string")
                if(param=='annotation_guide'):
                    annotation_guides=payload['annotation_guide']

                    # annotation_guides is an array and iterate 
                    for annotation_guide in annotation_guides:

                        if 'option_type' not in annotation_guide:
                            raise LabellerrError(f"option_type is required in annotation_guide")
                        else:
                            if annotation_guide['option_type'] not in OPTION_TYPE_LIST:
                                raise LabellerrError(f"option_type must be one of {OPTION_TYPE_LIST}")


                
            if  'folder_to_upload' in payload or 'files_to_upload' in payload:
                if 'folder_to_upload' in payload:
                    # make sure the folder path exist
                    if not os.path.exists(payload['folder_to_upload']):
                        raise LabellerrError(f"Folder {payload['folder_to_upload']} does not exist")
                    if not os.path.isdir(payload['folder_to_upload']):
                        raise LabellerrError(f"Folder {payload['folder_to_upload']} is not a directory")
                elif 'files_to_upload' in payload:
                    # make sure the files exist in the array payload['files_to_upload']
                    for file in payload['files_to_upload']:
                        if not os.path.exists(file):
                            raise LabellerrError(f"File {file} does not exist")
                        if not os.path.isfile(file):
                            raise LabellerrError(f"File {file} is not a file")

            if 'rotation_config' in payload:
                self.validate_rotation_config(payload['rotation_config'])
                print("Rotation configuration validated . . .")
            else:
                payload['rotation_config'] = {
                    'annotation_rotation_count':1,
                    'review_rotation_count':1,
                    'client_review_rotation_count':1
                }
            
            if payload['data_type'] not in DATA_TYPES:
                raise LabellerrError(f"Invalid data_type. Must be one of {DATA_TYPES}")

            if 'files_to_upload' in payload and 'folder_to_upload' in payload:
                raise LabellerrError("Both files_to_upload and folder_to_upload cannot be provided at the same time.")
            elif 'files_to_upload' not in payload and 'folder_to_upload' not in payload:
                raise LabellerrError("Either files_to_upload or folder_to_upload must be provided.")
            else:
                if 'files_to_upload' in payload:
                    if payload['files_to_upload'] is None and len(payload['files_to_upload'])==0:
                        raise LabellerrError("files_to_upload must be a non-empty string.")
                elif 'folder_to_upload' in payload:
                    if not isinstance(payload['folder_to_upload'], str) or not payload['folder_to_upload'].strip():
                        raise LabellerrError("folder_to_upload must be a non-empty string.")
                

            try:
                print("creating dataset . . .")
                response = self.create_dataset({
                    'client_id': payload['client_id'],
                    'dataset_name': payload['project_name'],
                    'data_type': payload['data_type'],
                    'dataset_description': payload['dataset_description'],
                    'created_by': payload['created_by']
                })
                print('Dataset created successfully.')

                dataset_id = response['dataset_id']
                result['dataset_id'] = dataset_id
            except KeyError as e:
                raise LabellerrError(f"Missing required field in payload: {str(e)}")
            except Exception as e:
                raise LabellerrError(str(e))

            # now upload local files/folder to dataset
            if 'files_to_upload' in payload and payload['files_to_upload'] is not None:
                try:
                    print("uploading file to a dataset . . .")
                    data = self.upload_files(
                        client_id=payload['client_id'],
                        dataset_id=dataset_id,
                        data_type=payload['data_type'],
                        files_list=payload['files_to_upload']
                    )
                    result['dataset_files'] = data
                    print("files uploaded to the dataset successfully.")
                except Exception as e:
                    raise LabellerrError(f"Failed to upload files to dataset: {str(e)}")

            elif 'folder_to_upload' in payload and payload['folder_to_upload'] is not None:
                try:
                    print("uploading folder to a dataset . . .")
                    data=self.upload_folder_files_to_dataset({
                        'client_id': payload['client_id'],
                        'dataset_id': dataset_id,
                        'data_type': payload['data_type'],
                        'folder_path': payload['folder_to_upload']
                    })
                    result['dataset_files'] = data
                except Exception as e:
                    raise LabellerrError(f"Failed to upload folder files to dataset: {str(e)}")

            print("Files added to dataset successfully.")
            # create empty project
            try:
                print("creating project . . .")
                response = self.create_empty_project(payload['client_id'], payload['project_name'], payload['data_type'],payload['created_by'],payload['rotation_config'])
                project_id = response['project_id']
                result['project_id'] = project_id
                result['project_config'] = response['project_config']
                print("Project created successfully.")
            except LabellerrError as e:
                raise LabellerrError(f"Failed to create project: {str(e)}")

            # update the project annotation guideline 
            # if 'annotation_guide' in payload and 'autolabel' in payload:
            try:
                print("updating project annotation guideline . . .")
                guideline={
                    "project_id":project_id,
                    "client_id":payload['client_id'],
                    "autolabel":payload['autolabel'],
                    "data_type": payload['data_type'],
                    "annotation_guideline":payload['annotation_guide']
                }
                guideline_update=self.update_project_annotation_guideline(guideline)
                result['annotation_guide']=guideline_update
                print('Project annotation guide is updated.')
            except Exception as e:
                logging.error(f"Failed to update project annotation guideline: {str(e)}")
                print(result)
                raise LabellerrError(f"Failed to update project annotation guideline: {str(e)}")
        

            # link dataset to project
            try:
                print("linking dataset to project . . .")
                data=self.link_dataset_to_project(payload['client_id'],project_id,dataset_id)
                result['dataset_project_link'] = data
                result['response'] = 'success'
                print("Dataset linked to project successfully.")
                return result
            except Exception as e:
                logging.error(f"Failed to link dataset to project: {str(e)}")
                print(result)
                raise LabellerrError(f"Failed to link dataset to project: {str(e)}")
        except Exception as e:
            logging.error(f"Failed to create project: {str(e)}")
            print(result)
            raise LabellerrError(f"Failed to create project: {str(e)}")
