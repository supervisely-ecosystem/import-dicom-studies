import os

import supervisely as sly
from supervisely.app.v1.app_service import AppService
from supervisely.io.fs import mkdir

my_app: AppService = AppService()

TEAM_ID: int = int(os.environ['context.teamId'])
WORKSPACE_ID: int = int(os.environ['context.workspaceId'])
GROUP_TAG_NAME: str = os.environ.get("modal.state.groupTagName")

INPUT_DIR: str = os.environ.get("modal.state.slyFolder")
INPUT_FILE: str = os.environ.get("modal.state.slyFile")

SeriesInstanceUID_TAG = None
StudyInstanceUID_TAG = None

PROJECT_NAME: str = 'group-images'
STORAGE_DIR: str = my_app.data_dir
mkdir(STORAGE_DIR, True)

project_meta: sly.ProjectMeta = None
