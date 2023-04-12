import functools
import json
import os
import shutil
from functools import partial
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import nrrd
import pydicom
import supervisely as sly
from pydicom import FileDataset
from supervisely.io.fs import file_exists, get_file_name_with_ext, silent_remove

import sly_globals as g


def import_dataset(api, dataset_path):
    """Imports a single dataset into the project."""
    # Create a new dataset in the project
    dataset_name = os.path.basename(os.path.normpath(dataset_path))
    dataset = api.dataset.create(
        project_id=g.project_id, name=dataset_name, change_name_if_conflict=True
    )

    batch_size = 50
    # Process the images in batches
    ds_images_paths, ds_annotations_paths = get_paths(dataset_path, with_anns=g.WITH_ANNS)
    batch_progress = sly.Progress(message="Processing images", total_cnt=len(ds_images_paths))

    for batch_imgs, batch_anns in zip(
        sly.batched(ds_images_paths, batch_size),
        sly.batched(ds_annotations_paths, batch_size),
    ):
        import_images(api, dataset, batch_imgs, batch_anns)
        batch_progress.iters_done_report(len(batch_imgs))


def import_images(api, dataset, batch_imgs, batch_anns):
    img_paths = []
    img_names = []
    anns = []

    for image_path, annotation_path in zip(batch_imgs, batch_anns):
        image_path, image_name, ann_from_dcm = dcm2nrrd(
            image_path=image_path,
            group_tag_name=g.GROUP_TAG_NAME,
        )
        img_paths.append(image_path)
        img_names.append(image_name)

        if g.WITH_ANNS:
            ann = sly.Annotation.load_json_file(annotation_path, g.project_meta_from_sly_format)
            anns.append(ann.merge(ann_from_dcm))
        else:
            anns.append(ann_from_dcm)

    # Upload the images and annotations to the project
    dst_image_infos = api.image.upload_paths(
        dataset_id=dataset.id, names=img_names, paths=img_paths
    )
    dst_image_ids = [img_info.id for img_info in dst_image_infos]

    # Merge meta from annotations (if supervisely format) with other tags
    if g.WITH_ANNS:
        _meta_dct = g.project_meta_from_sly_format.to_json()
        _meta_dct["tags"] += g.project_meta.to_json()["tags"]
        check_unique_name(_meta_dct["tags"])
    else:
        _meta_dct = g.project_meta.to_json()

    # Update the project metadata and enable image grouping
    api.project.update_meta(id=g.project_id, meta=_meta_dct)
    api.project.images_grouping(id=g.project_id, enable=True, tag_name=g.GROUP_TAG_NAME)

    api.annotation.upload_anns(img_ids=dst_image_ids, anns=anns)


def get_paths(dataset_path, with_anns=False):
    if with_anns:
        subfolders = os.listdir(dataset_path)
        # check supervisely format
        # Learn more here: https://docs.supervise.ly/data-organization/00_ann_format_navi
        if "img" not in subfolders or "ann" not in subfolders:
            raise ValueError(
                "The 'img' and/or 'ann' folders do not exist in the dataset path. Learn more about supervisely format here: https://docs.supervise.ly/data-organization/00_ann_format_navi"
            )

        img_dirname, ann_dirname = os.path.join(dataset_path, "img"), os.path.join(
            dataset_path, "ann"
        )
        dataset_path = img_dirname

    ds_images_paths = sorted(
        [
            os.path.join(dataset_path, item)
            for item in os.listdir(dataset_path)
            if file_exists(os.path.join(dataset_path, item))
            and is_dicom_file(os.path.join(dataset_path, item))
        ]
    )

    if with_anns:
        ds_annotations_paths = sorted(
            [
                os.path.join(ann_dirname, item)
                for item in os.listdir(ann_dirname)
                if file_exists(os.path.join(ann_dirname, item))
                and is_json_file(os.path.join(ann_dirname, item))
            ]
        )
    else:
        ds_annotations_paths = [None for _ in ds_images_paths]

    return ds_images_paths, ds_annotations_paths


def check_unique_name(lst: list[dict[str, str]]) -> None:
    """
    Checks if the 'name' key in a list of dictionaries has only unique values.
    Raises a ValueError exception with a descriptive message if the values are not unique.
    """
    values = [d["name"] for d in lst]
    if len(values) != len(set(values)):
        non_unique_values = [v for v in set(values) if values.count(v) > 1]
        raise ValueError(
            f"The 'name' key in Project Meta has non-unique values: {non_unique_values}"
        )


def check_image_project_structure(root_dir, format, img_ext):
    if format == "supervisely":
        meta_file = os.path.join(root_dir, "meta.json")

        for dataset_dir in os.scandir(root_dir):
            if not dataset_dir.is_dir():
                if not os.path.exists(meta_file):
                    raise ValueError(
                        f"Missing meta.json file. Instead got: {dataset_dir.path}. Learn more about supervisely format here: https://docs.supervise.ly/data-organization/00_ann_format_navi"
                    )
                continue

            img_dir = os.path.join(dataset_dir.path, "img")
            ann_dir = os.path.join(dataset_dir.path, "ann")

            if not os.path.exists(img_dir):
                raise ValueError(
                    f"Missing 'img' directory in dataset directory: {dataset_dir.path}. Learn more about supervisely format here: https://docs.supervise.ly/data-organization/00_ann_format_navi"
                )
            if not os.path.exists(ann_dir):
                raise ValueError(
                    f"Missing 'ann' directory in dataset directory: {dataset_dir.path}. Learn more about supervisely format here: https://docs.supervise.ly/data-organization/00_ann_format_navi"
                )
            for data_file in os.scandir(img_dir):
                if data_file.is_file() and not data_file.name.endswith(img_ext):
                    g.my_app.logger.warn(
                        f"Unexpected file '{data_file.name}' in 'img' directory: {img_dir}"
                    )
            for json_file in os.scandir(ann_dir):
                if json_file.is_file() and not json_file.name.endswith(".json"):
                    g.my_app.logger.warn(
                        f"Unexpected file '{json_file.name}' in 'ann' directory: {ann_dir}"
                    )
    if format == "no_annotations":
        for dataset_dir in os.scandir(root_dir):
            if check_extension_in_folder(dataset_dir.path, img_ext):
                for data_file in os.scandir(dataset_dir.path):
                    if data_file.is_file() and not data_file.name.endswith(img_ext):
                        g.my_app.logger.warn(
                            f"Unexpected file '{data_file.name}' in directory: {dataset_dir.path}"
                        )
            else:
                raise ValueError(
                    f"Missing '{img_ext}' files in dataset directory: {dataset_dir.path}"
                )
    g.my_app.logger.info(f"Project structure is correct")


def check_extension_in_folder(folder_path, extension):
    files = os.listdir(folder_path)
    for file in files:
        if file.endswith(extension):
            return True
    return False


def update_progress(count, api: sly.Api, task_id: int, progress: sly.Progress) -> None:
    count = min(count, progress.total - progress.current)
    progress.iters_done(count)
    if progress.need_report():
        progress.report_progress()


def get_progress_cb(
    api: sly.Api,
    task_id: int,
    message: str,
    total: int,
    is_size: bool = False,
    func: Callable = update_progress,
) -> functools.partial:
    progress = sly.Progress(message, total, is_size=is_size)
    progress_cb = partial(func, api=api, task_id=task_id, progress=progress)
    progress_cb(0)
    return progress_cb


def is_dicom_file(path: str, verbose: bool = False) -> bool:
    """Checks if file is dicom file by given path."""
    try:
        pydicom.read_file(str(Path(path).resolve()), stop_before_pixels=True)
        result = True
    except Exception as ex:
        if verbose:
            print("'{}' appears not to be a DICOM file\n({})".format(path, ex))
            g.my_app.logger.warn("'{}' appears not to be a DICOM file\n({})".format(path, ex))
        result = False
    return result


def is_json_file(file_path):
    try:
        with open(file_path, "r") as f:
            json.load(f)
            return True
    except (ValueError, FileNotFoundError):
        return False


def download_data_from_team_files(api: sly.Api, task_id: int, save_path: str) -> str:
    """Download data from remote directory in Team Files."""
    project_path = None
    if g.INPUT_DIR is not None:
        remote_path = g.INPUT_DIR
        project_path = os.path.join(save_path, os.path.basename(os.path.normpath(remote_path)))
        sizeb = api.file.get_directory_size(g.TEAM_ID, remote_path)
        progress_cb = get_progress_cb(
            api=api,
            task_id=task_id,
            message=f"Downloading {remote_path.lstrip('/').rstrip('/')}",
            total=sizeb,
            is_size=True,
        )
        api.file.download_directory(
            team_id=g.TEAM_ID,
            remote_path=remote_path,
            local_save_path=project_path,
            progress_cb=progress_cb,
        )

    elif g.INPUT_FILE is not None:
        remote_path = g.INPUT_FILE
        save_archive_path = os.path.join(save_path, get_file_name_with_ext(remote_path))
        sizeb = api.file.get_info_by_path(g.TEAM_ID, remote_path).sizeb
        progress_cb = get_progress_cb(
            api=api,
            task_id=task_id,
            message=f"Downloading {remote_path.lstrip('/')}",
            total=sizeb,
            is_size=True,
        )
        api.file.download(
            team_id=g.TEAM_ID,
            remote_path=remote_path,
            local_save_path=save_archive_path,
            progress_cb=progress_cb,
        )
        shutil.unpack_archive(save_archive_path, save_path)
        silent_remove(save_archive_path)
        if len(os.listdir(save_path)) > 1:
            g.my_app.logger.error("There must be only 1 project directory in the archive")
            raise Exception("There must be only 1 project directory in the archive")

        project_name = os.listdir(save_path)[0]
        project_path = os.path.join(save_path, project_name)
    return project_path


def dcm2nrrd(
    image_path: str,
    group_tag_name: str,
) -> Tuple[str, str, sly.Annotation]:
    """Converts DICOM data to nrrd format and returns image path, image name, and image annotation."""
    dcm = pydicom.read_file(image_path)
    dcm_tags = None
    if g.ADD_DCM_TAGS:
        dcm_tags = create_dcm_tags(dcm)

    pixel_data = dcm.pixel_array
    pixel_data = sly.image.rotate(img=pixel_data, degrees_angle=270)
    original_name = get_file_name_with_ext(image_path)
    image_name = f"{original_name}.nrrd"
    save_path = os.path.join(os.path.dirname(image_path), image_name)
    nrrd.write(save_path, pixel_data)

    try:
        group_tag_value = str(dcm[group_tag_name].value)
        group_tag = {"name": group_tag_name, "value": group_tag_value}
        ann = create_ann_with_tags(
            save_path,
            group_tag,
            dcm_tags,
        )
    except:
        g.my_app.logger.warn(
            f"Couldn't find key: '{group_tag_name}' in file's metadata: '{original_name}'"
        )
        img_size = nrrd.read_header(save_path)["sizes"].tolist()[::-1]
        ann = sly.Annotation(img_size=img_size)
        if g.ADD_DCM_TAGS:
            ann = ann.add_tags(sly.TagCollection(dcm_tags))

    return save_path, image_name, ann


def create_dcm_tags(dcm: FileDataset) -> List[sly.Tag]:
    """Create tags from DICOM metadata."""
    dcm_tags = []
    for dcm_tag in g.DCM_TAGS:
        try:
            dcm_tag_name = str(dcm[dcm_tag].name)
            dcm_tag_value = str(dcm[dcm_tag].value)
        except:
            dcm_filename = get_file_name_with_ext(dcm.filename)
            g.my_app.logger.warn(
                f"Couldn't find key: '{dcm_tag}' in file's metadata: '{dcm_filename}'"
            )
            continue

        if dcm_tag_value is None:
            continue

        dcm_tag_meta = g.project_meta.get_tag_meta(dcm_tag_name)
        if dcm_tag_meta is None:
            dcm_tag_meta = sly.TagMeta(dcm_tag_name, sly.TagValueType.ANY_STRING)
            g.project_meta = g.project_meta.add_tag_meta(dcm_tag_meta)

        dcm_tag = sly.Tag(dcm_tag_meta, dcm_tag_value)
        dcm_tags.append(dcm_tag)
    return dcm_tags


def create_ann_with_tags(
    path_to_img: str, group_tag_info: dict, dcm_tags: List[sly.Tag] = None
) -> sly.Annotation:
    """Creates annotation with tags."""
    img_size = nrrd.read_header(path_to_img)["sizes"].tolist()[::-1]
    group_tag = create_group_tag(group_tag_info)
    tags_to_add = [tag for tag in [group_tag] + (dcm_tags or []) if tag.value is not None]
    return sly.Annotation(img_size=img_size).add_tags(sly.TagCollection(tags_to_add))


def create_group_tag(group_tag_info: Dict[str, str]) -> sly.Tag:
    """Creates grouping tag."""
    group_tag_name, group_tag_value = group_tag_info["name"], group_tag_info["value"]
    group_tag_meta = g.project_meta.get_tag_meta(group_tag_name)
    if group_tag_meta is None:
        group_tag_meta = sly.TagMeta(group_tag_name, sly.TagValueType.ANY_STRING)
        g.project_meta = g.project_meta.add_tag_meta(group_tag_meta)
    group_tag = sly.Tag(group_tag_meta, group_tag_value)
    return group_tag


def get_progress_cb(
    api: sly.Api,
    task_id: int,
    message: str,
    total: int,
    is_size: bool = False,
    func: Callable = update_progress,
) -> functools.partial:
    progress = sly.Progress(message, total, is_size=is_size)
    progress_cb = functools.partial(func, api=api, task_id=task_id, progress=progress)
    progress_cb(0)
    return progress_cb
