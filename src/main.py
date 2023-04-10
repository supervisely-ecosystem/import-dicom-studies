import os

import supervisely as sly
from supervisely.io.fs import file_exists

import sly_globals as g
import sly_utils as f


@g.my_app.callback("import-dicom-studies")
@sly.timeit
def import_dicom_studies(
    api: sly.Api, task_id: int, context: dict, state: dict, app_logger
) -> None:
    """Converts DICOM data to .nrrd format and add tags from DICOM metadata."""

    project_dir = f.download_data_from_team_files(api=api, task_id=task_id, save_path=g.STORAGE_DIR)
    project_name = os.path.basename(project_dir)
    new_project = api.project.create(
        workspace_id=g.WORKSPACE_ID, name=project_name, change_name_if_conflict=True
    )
    g.project_id = new_project.id

    project_fs = sly.read_single_project(g.STORAGE_DIR)
    # if project_name is None:
    #     project_name = project_fs.name

    datasets_paths = [
        os.path.join(project_dir, item)
        for item in os.listdir(project_dir)
        if os.path.isdir(os.path.join(project_dir, item))
    ]

    ds_progress = sly.Progress(message="Importing Datasets", total_cnt=len(datasets_paths))
    for dataset_path in datasets_paths:

        dataset_name = os.path.basename(os.path.normpath(dataset_path))
        dataset = api.dataset.create(
            project_id=new_project.id, name=dataset_name, change_name_if_conflict=True
        )

        subfolders = os.listdir(dataset_path)  #  ['ann', 'img']

        for folder_name in subfolders:
            folder_path = os.path.join(dataset_path, folder_name)
            if not os.path.isdir(folder_path):
                raise ValueError(f"The '{folder_name}' folder does not exist.")

        img_dirname = os.path.join(dataset_path, "img")
        ann_dirname = os.path.join(dataset_path, "ann")

        ds_images_paths = sorted(
            [
                os.path.join(img_dirname, item)
                for item in os.listdir(img_dirname)
                if file_exists(os.path.join(img_dirname, item))
                and f.is_dicom_file(os.path.join(img_dirname, item))
            ]
        )

        batch_progress = sly.Progress(message="Processing images", total_cnt=len(ds_images_paths))

        ds_annotations_paths = sorted(
            [
                os.path.join(ann_dirname, item)
                for item in os.listdir(ann_dirname)
                if file_exists(os.path.join(ann_dirname, item))
                and f.is_json_file(os.path.join(ann_dirname, item))
            ]
        )

        for batch_imgs, batch_anns in zip(
            sly.batched(ds_images_paths, 50), sly.batched(ds_annotations_paths, 50)
        ):

            img_paths = []
            images_names = []
            anns = []  # anns

            for batch_image_path in batch_imgs:
                image_path, image_name, ann = f.dcm2nrrd(
                    image_path=batch_image_path, group_tag_name=g.GROUP_TAG_NAME
                )
                img_paths.append(image_path)
                images_names.append(image_name)
                anns.append(ann)

            dst_image_infos = api.image.upload_paths(
                dataset_id=dataset.id, names=images_names, paths=img_paths
            )
            dst_image_ids = [img_info.id for img_info in dst_image_infos]
            api.annotation.upload_anns(img_ids=dst_image_ids, anns=anns)

            batch_progress.iters_done_report(len(batch_imgs))

            api.project.update_meta(new_project.id, project_fs.meta.to_json())
            api.annotation.upload_paths(
                dst_image_ids,
                batch_anns,
            )

        ds_progress.iter_done_report()

    g.my_app.stop()


def main():
    sly.logger.info(
        "Script arguments", extra={"TEAM_ID": g.TEAM_ID, "WORKSPACE_ID": g.WORKSPACE_ID}
    )
    g.my_app.run(initial_events=[{"command": "import-dicom-studies"}])


if __name__ == "__main__":
    sly.main_wrapper("main", main)
