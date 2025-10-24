import json
import uuid

from labellerr import schemas, LabellerrClient
from labellerr.core import constants
from labellerr.core.base.singleton import Singleton
from labellerr_integration_case_tests import client


class LabellerrUsers(Singleton):

    def __init__(self, client: "LabellerrClient", *args):
        super().__init__(*args)
        self.client = client

    def create_user(
        self,
        client_id,
        first_name,
        last_name,
        email_id,
        projects,
        roles,
        work_phone="",
        job_title="",
        language="en",
        timezone="GMT",
    ):
        """
        Creates a new user in the system.

        :param client_id: The ID of the client
        :param first_name: User's first name
        :param last_name: User's last name
        :param email_id: User's email address
        :param projects: List of project IDs to assign the user to
        :param roles: List of role objects with project_id and role_id
        :param work_phone: User's work phone number (optional)
        :param job_title: User's job title (optional)
        :param language: User's preferred language (default: "en")
        :param timezone: User's timezone (default: "GMT")
        :return: Dictionary containing user creation response
        :raises LabellerrError: If the creation fails
        """
        # Validate parameters using Pydantic
        params = schemas.CreateUserParams(
            client_id=client_id,
            first_name=first_name,
            last_name=last_name,
            email_id=email_id,
            projects=projects,
            roles=roles,
            work_phone=work_phone,
            job_title=job_title,
            language=language,
            timezone=timezone,
        )
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/register?client_id={params.client_id}&uuid={unique_id}"

        payload = json.dumps(
            {
                "first_name": params.first_name,
                "last_name": params.last_name,
                "work_phone": params.work_phone,
                "job_title": params.job_title,
                "language": params.language,
                "timezone": params.timezone,
                "email_id": params.email_id,
                "projects": params.projects,
                "client_id": params.client_id,
                "roles": params.roles,
            }
        )

        return self.client.make_request(
            "POST",
            url,
            client_id=params.client_id,
            extra_headers={
                "content-type": "application/json",
                "accept": "application/json, text/plain, */*",
            },
            request_id=unique_id,
            data=payload,
        )

    def update_user_role(
        self,
        client_id,
        project_id,
        email_id,
        roles,
        first_name=None,
        last_name=None,
        work_phone="",
        job_title="",
        language="en",
        timezone="GMT",
        profile_image="",
    ):
        """
        Updates a user's role and profile information.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param email_id: User's email address
        :param roles: List of role objects with project_id and role_id
        :param first_name: User's first name (optional)
        :param last_name: User's last name (optional)
        :param work_phone: User's work phone number (optional)
        :param job_title: User's job title (optional)
        :param language: User's preferred language (default: "en")
        :param timezone: User's timezone (default: "GMT")
        :param profile_image: User's profile image (optional)
        :return: Dictionary containing update response
        :raises LabellerrError: If the update fails
        """
        # Validate parameters using Pydantic
        params = schemas.UpdateUserRoleParams(
            client_id=client_id,
            project_id=project_id,
            email_id=email_id,
            roles=roles,
            first_name=first_name,
            last_name=last_name,
            work_phone=work_phone,
            job_title=job_title,
            language=language,
            timezone=timezone,
            profile_image=profile_image,
        )
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/update?client_id={params.client_id}&project_id={params.project_id}&uuid={unique_id}"

        # Build the payload with all provided information
        # Extract project_ids from roles for API requirement
        project_ids = [
            role.get("project_id") for role in params.roles if "project_id" in role
        ]

        payload_data = {
            "profile_image": params.profile_image,
            "work_phone": params.work_phone,
            "job_title": params.job_title,
            "language": params.language,
            "timezone": params.timezone,
            "email_id": params.email_id,
            "client_id": params.client_id,
            "roles": params.roles,
            "projects": project_ids,  # API requires projects list extracted from roles (same format as create_user)
        }

        # Add optional fields if provided
        if params.first_name is not None:
            payload_data["first_name"] = params.first_name
        if params.last_name is not None:
            payload_data["last_name"] = params.last_name

        payload = json.dumps(payload_data)

        return self.client.make_request(
            "POST",
            url,
            client_id=params.client_id,
            extra_headers={
                "content-type": "application/json",
                "accept": "application/json, text/plain, */*",
            },
            request_id=unique_id,
            data=payload,
        )

    def delete_user(
        self,
        client_id,
        project_id,
        email_id,
        user_id,
        first_name=None,
        last_name=None,
        is_active=1,
        role="Annotator",
        user_created_at=None,
        max_activity_created_at=None,
        image_url="",
        name=None,
        activity="No Activity",
        creation_date=None,
        status="Activated",
    ):
        """
        Deletes a user from the system.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param email_id: User's email address
        :param user_id: User's unique identifier
        :param first_name: User's first name (optional)
        :param last_name: User's last name (optional)
        :param is_active: User's active status (default: 1)
        :param role: User's role (default: "Annotator")
        :param user_created_at: User creation timestamp (optional)
        :param max_activity_created_at: Max activity timestamp (optional)
        :param image_url: User's profile image URL (optional)
        :param name: User's display name (optional)
        :param activity: User's activity status (default: "No Activity")
        :param creation_date: User creation date (optional)
        :param status: User's status (default: "Activated")
        :return: Dictionary containing deletion response
        :raises LabellerrError: If the deletion fails
        """
        # Validate parameters using Pydantic
        params = schemas.DeleteUserParams(
            client_id=client_id,
            project_id=project_id,
            email_id=email_id,
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            is_active=is_active,
            role=role,
            user_created_at=user_created_at,
            max_activity_created_at=max_activity_created_at,
            image_url=image_url,
            name=name,
            activity=activity,
            creation_date=creation_date,
            status=status,
        )
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/delete?client_id={params.client_id}&project_id={params.project_id}&uuid={unique_id}"

        # Build the payload with all provided information
        payload_data = {
            "email_id": params.email_id,
            "is_active": params.is_active,
            "role": params.role,
            "user_id": params.user_id,
            "imageUrl": params.image_url,
            "email": params.email_id,
            "activity": params.activity,
            "status": params.status,
        }

        # Add optional fields if provided
        if params.first_name is not None:
            payload_data["first_name"] = params.first_name
        if params.last_name is not None:
            payload_data["last_name"] = params.last_name
        if params.user_created_at is not None:
            payload_data["user_created_at"] = params.user_created_at
        if params.max_activity_created_at is not None:
            payload_data["max_activity_created_at"] = params.max_activity_created_at
        if params.name is not None:
            payload_data["name"] = params.name
        if params.creation_date is not None:
            payload_data["creationDate"] = params.creation_date

        payload = json.dumps(payload_data)

        return self.client.make_request(
            "POST",
            url,
            client_id=params.client_id,
            extra_headers={
                "content-type": "application/json",
                "accept": "application/json, text/plain, */*",
            },
            request_id=unique_id,
            data=payload,
        )

    def add_user_to_project(self, client_id, project_id, email_id, role_id=None):
        """
        Adds a user to a project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param email_id: User's email address
        :param role_id: Optional role ID to assign to the user
        :return: Dictionary containing addition response
        :raises LabellerrError: If the addition fails
        """
        # Validate parameters using Pydantic
        params = schemas.AddUserToProjectParams(
            client_id=client_id,
            project_id=project_id,
            email_id=email_id,
            role_id=role_id,
        )
        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/add_user_to_project?client_id={params.client_id}&project_id={params.project_id}&uuid={unique_id}"

        payload_data = {"email_id": params.email_id, "uuid": unique_id}

        if params.role_id is not None:
            payload_data["role_id"] = params.role_id

        payload = json.dumps(payload_data)
        return self.client.make_request(
            "POST",
            url,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )

    def remove_user_from_project(self, client_id, project_id, email_id):
        """
        Removes a user from a project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param email_id: User's email address
        :return: Dictionary containing removal response
        :raises LabellerrError: If the removal fails
        """
        # Validate parameters using Pydantic
        params = schemas.RemoveUserFromProjectParams(
            client_id=client_id, project_id=project_id, email_id=email_id
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/remove_user_from_project?client_id={params.client_id}&project_id={params.project_id}&uuid={unique_id}"

        payload_data = {"email_id": params.email_id, "uuid": unique_id}

        payload = json.dumps(payload_data)
        return self.client.make_request(
            "POST",
            url,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )

    # TODO: this is not working from UI
    def change_user_role(self, client_id, project_id, email_id, new_role_id):
        """
        Changes a user's role in a project.

        :param client_id: The ID of the client
        :param project_id: The ID of the project
        :param email_id: User's email address
        :param new_role_id: The new role ID to assign to the user
        :return: Dictionary containing role change response
        :raises LabellerrError: If the role change fails
        """
        # Validate parameters using Pydantic
        params = schemas.ChangeUserRoleParams(
            client_id=client_id,
            project_id=project_id,
            email_id=email_id,
            new_role_id=new_role_id,
        )

        unique_id = str(uuid.uuid4())
        url = f"{constants.BASE_URL}/users/change_user_role?client_id={params.client_id}&project_id={params.project_id}&uuid={unique_id}"

        payload_data = {
            "email_id": params.email_id,
            "new_role_id": params.new_role_id,
            "uuid": unique_id,
        }

        payload = json.dumps(payload_data)
        return self.client.make_request(
            "POST",
            url,
            client_id=params.client_id,
            extra_headers={"content-type": "application/json"},
            request_id=unique_id,
            data=payload,
        )


def main():
    LabellerrUsers(LabellerrClient("", "", ""))


if __name__ == "__main__":
    main()
