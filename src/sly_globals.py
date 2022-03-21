import os
import json
import supervisely as sly
from supervisely.app.v1.app_service import AppService
from supervisely.io.fs import mkdir

my_app: AppService = AppService()
api: sly.Api = my_app.public_api

TEAM_ID: int = int(os.environ['context.teamId'])
WORKSPACE_ID: int = int(os.environ['context.workspaceId'])

TAG_MODE: str = os.environ["modal.state.tagMode"]
GROUP_TAG_NAME: str = os.environ.get("modal.state.groupTag")
UPLOAD_META: bool = bool(os.environ["modal.state.uploadMeta"])
ADD_DCM_TAGS: bool = bool(os.environ["modal.state.addTagsFromDcm"])
DCM_TAGS: list = json.loads(os.environ["modal.state.dcmTags"])["tags"]

INPUT_DIR: str = os.environ.get("modal.state.slyFolder")
INPUT_FILE: str = os.environ.get("modal.state.slyFile")

STORAGE_DIR: str = my_app.data_dir
mkdir(STORAGE_DIR, True)

project_id: int = None
project_meta: sly.ProjectMeta = sly.ProjectMeta()

