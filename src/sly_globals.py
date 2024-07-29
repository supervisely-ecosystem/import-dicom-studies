import json
import os
from distutils.util import strtobool

import supervisely as sly
from dotenv import load_dotenv
from supervisely.app.v1.app_service import AppService
from supervisely.io.fs import mkdir

from workflow import Workflow

if sly.is_development():
    load_dotenv("local.env")
    load_dotenv(os.path.expanduser("~/supervisely.env"))


my_app: AppService = AppService()
api = sly.Api.from_env()
workflow = Workflow(api)

TEAM_ID = sly.env.team_id()
WORKSPACE_ID = sly.env.workspace_id()

TAG_MODE: str = os.environ["modal.state.tagMode"]
ADD_DCM_TAGS = str(os.environ.get("modal.state.addTagsFromDcm"))

ADD_ALL = "All tags"
ADD_ONLY_SPECIFIED = "Only specified tags"
DO_NOT_ADD = "Do not add tags"

DCM_TAGS: list = []
if ADD_DCM_TAGS == ADD_ONLY_SPECIFIED:
    try:
        DCM_TAGS: list = json.loads(os.environ["modal.state.dcmTags"].replace("\\", ""))["tags"]
    except:
        my_app.logger.warn("Invalid JSON input in modal window editor")

PREPARED_GROUP_TAG_NAME: str = os.environ.get("modal.state.predefinedGroupTag")
MANUAL_GROUP_TAG_NAME: str = os.environ.get("modal.state.manualGroupTag")

GROUP_TAG_NAME = None
if TAG_MODE == "prepared":
    GROUP_TAG_NAME = PREPARED_GROUP_TAG_NAME
else:
    GROUP_TAG_NAME = MANUAL_GROUP_TAG_NAME

INPUT_DIR: str = os.environ.get("modal.state.slyFolder")
INPUT_FILE: str = os.environ.get("modal.state.slyFile")

if INPUT_DIR:
    IS_ON_AGENT = api.file.is_on_agent(INPUT_DIR)
else:
    IS_ON_AGENT = api.file.is_on_agent(INPUT_FILE)

WITH_ANNS: bool = bool(strtobool(os.environ.get("modal.state.withAnns")))

STORAGE_DIR: str = my_app.data_dir
mkdir(STORAGE_DIR, True)

SLY_FORMAT_DOCS = "https://docs.supervise.ly/data-organization/00_ann_format_navi"
project_id: int = None
project_meta: sly.ProjectMeta = sly.ProjectMeta()
project_meta_from_sly_format: sly.ProjectMeta = sly.ProjectMeta()
