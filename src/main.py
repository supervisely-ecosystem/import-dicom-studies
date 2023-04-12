import os

import supervisely as sly

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

    if g.WITH_ANNS:
        f.check_image_project_structure(project_dir, format="supervisely", img_ext=".dcm")
        g.project_meta_from_sly_format = sly.read_single_project(g.STORAGE_DIR).meta
    else:
        f.check_image_project_structure(project_dir, format="no_annotations", img_ext=".dcm")

    # Loop over the datasets in the project directory
    datasets_paths = [
        os.path.join(project_dir, item)
        for item in os.listdir(project_dir)
        if os.path.isdir(os.path.join(project_dir, item))
    ]

    ds_progress = sly.Progress(message="Importing Datasets", total_cnt=len(datasets_paths))
    for dataset_path in datasets_paths:
        f.import_dataset(api, dataset_path)
        ds_progress.iter_done_report()

    g.my_app.stop()


def main():
    sly.logger.info(
        "Script arguments", extra={"TEAM_ID": g.TEAM_ID, "WORKSPACE_ID": g.WORKSPACE_ID}
    )
    g.my_app.run(initial_events=[{"command": "import-dicom-studies"}])


if __name__ == "__main__":
    sly.main_wrapper("main", main)
