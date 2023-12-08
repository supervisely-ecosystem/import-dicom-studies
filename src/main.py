import os

import supervisely as sly
from supervisely.io.fs import remove_dir

import sly_globals as g
import sly_utils as f


@g.my_app.callback("import-dicom-studies")
@sly.timeit
def import_dicom_studies(
    api: sly.Api, task_id: int, context: dict, state: dict, app_logger
) -> None:
    """Converts DICOM data to .nrrd format and add tags from DICOM metadata."""

    # Create a new project in the workspace
    project_dir = f.download_data_from_team_files(api=api, task_id=task_id, save_path=g.STORAGE_DIR)
    project_name = os.path.basename(project_dir)
    project = api.project.create(
        workspace_id=g.WORKSPACE_ID, name=project_name, change_name_if_conflict=True
    )
    g.project_id = project.id

    f.check_image_project_structure(project_dir, with_anns=g.WITH_ANNS, img_ext=".dcm")
    if g.WITH_ANNS:
        g.project_meta_from_sly_format = sly.read_single_project(g.STORAGE_DIR).meta

    # Loop over the datasets in the project directory
    datasets_paths = [
        os.path.join(project_dir, item)
        for item in os.listdir(project_dir)
        if os.path.isdir(os.path.join(project_dir, item))
    ]

    ds_progress = sly.Progress(message="Importing Datasets", total_cnt=len(datasets_paths))
    for dataset_path in datasets_paths:
        try:
            f.import_dataset(api, dataset_path)
        except FileNotFoundError as e:
            if str(e) == "Nothing to import":
                sly.logger.warning(f"Skipping dataset '{dataset_path}', nothing to import")
                continue
        ds_progress.iter_done_report()
    if api.project.get_datasets_count(project.id) == 0:
        api.project.remove(project.id)
        title = f"Failed to import DICOM data."
        description = "Read the app overview to prepare your data for import."
        api.task.set_output_error(task_id, title=title, description=description)
        app_logger.warn(f"{title} {description}")
    remove_dir(project_dir)
    g.my_app.stop()


def main():
    sly.logger.info(
        "Script arguments", extra={"TEAM_ID": g.TEAM_ID, "WORKSPACE_ID": g.WORKSPACE_ID}
    )
    g.my_app.run(initial_events=[{"command": "import-dicom-studies"}])


if __name__ == "__main__":
    sly.main_wrapper("main", main)
