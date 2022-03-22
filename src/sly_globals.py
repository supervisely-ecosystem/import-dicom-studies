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

ADD_DCM_TAGS: bool = bool(os.environ["modal.state.addTagsFromDcm"])
DCM_TAGS = os.environ["modal.state.dcmTags"].replace('\\', "")
if ADD_DCM_TAGS and DCM_TAGS is not None:
    DCM_TAGS = json.loads(DCM_TAGS)
    DCM_TAGS = DCM_TAGS["tags"]


PREPARED_GROUP_TAG_NAME: str = os.environ.get("modal.state.predefinedGroupTag")
MANUAL_GROUP_TAG_NAME: str = os.environ.get("modal.state.manualGroupTag")

GROUP_TAG_NAME = None
if TAG_MODE == "prepared":
    GROUP_TAG_NAME = PREPARED_GROUP_TAG_NAME
else:
    GROUP_TAG_NAME = MANUAL_GROUP_TAG_NAME


INPUT_DIR: str = os.environ.get("modal.state.slyFolder")
INPUT_FILE: str = os.environ.get("modal.state.slyFile")

STORAGE_DIR: str = my_app.data_dir
mkdir(STORAGE_DIR, True)

project_id: int = None
project_meta: sly.ProjectMeta = sly.ProjectMeta()
