import os
import supervisely as sly

import sly_globals as g
import sly_utils

from supervisely.io.fs import file_exists


@g.my_app.callback("import-dicom-studies")
@sly.timeit
def import_images_groups(api: sly.Api, task_id: int, context: dict, state: dict, app_logger) -> None:
    """Converts DICOM data to .nrrd format and add tags from DICOM metadata."""
    project_dir = sly_utils.download_data_from_team_files(
        api=api, task_id=task_id, save_path=g.STORAGE_DIR)
    project_name = os.path.basename(os.path.normpath(project_dir))
    new_project = api.project.create(
        workspace_id=g.WORKSPACE_ID, name=project_name, change_name_if_conflict=True)
    g.project_id = new_project.id

    datasets_paths = [os.path.join(project_dir, item) for item in os.listdir(
        project_dir) if os.path.isdir(os.path.join(project_dir, item))]

    ds_progress = sly.Progress(message="Importing Datasets",
                               total_cnt=len(datasets_paths))
    for dataset_path in datasets_paths:
        dataset_name = os.path.basename(os.path.normpath(dataset_path))
        dataset = api.dataset.create(
            project_id=new_project.id, name=dataset_name, change_name_if_conflict=True)
        ds_images_paths = [os.path.join(dataset_path, item) for item in os.listdir(dataset_path) if
                           file_exists(os.path.join(dataset_path, item)) and sly_utils.is_dicom_file(
                               os.path.join(dataset_path, item))]

        batch_progress = sly.Progress(
            message="Processing images", total_cnt=len(ds_images_paths))
        for batch in sly.batched(ds_images_paths, 50):
            images_paths = []
            images_names = []
            anns = []

            for batch_image_path in batch:
                image_path, image_name, ann = sly_utils.dcm2nrrd(
                    image_path=batch_image_path, group_tag_name=g.GROUP_TAG_NAME)
                images_paths.append(image_path)
                images_names.append(image_name)
                anns.append(ann)

            dst_image_infos = api.image.upload_paths(
                dataset_id=dataset.id, names=images_names, paths=images_paths)
            dst_image_ids = [img_info.id for img_info in dst_image_infos]
            api.annotation.upload_anns(img_ids=dst_image_ids, anns=anns)

            batch_progress.iters_done_report(len(batch))
        ds_progress.iter_done_report()
    g.my_app.stop()


def main():
    sly.logger.info("Script arguments", extra={
        "TEAM_ID": g.TEAM_ID,
        "WORKSPACE_ID": g.WORKSPACE_ID
    })
    g.my_app.run(initial_events=[{"command": "import-dicom-studies"}])


if __name__ == '__main__':
    sly.main_wrapper("main", main)
