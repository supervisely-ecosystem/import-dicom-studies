import functools
import nrrd
import os
import json
import shutil
from functools import partial
from typing import Callable, List, Dict, Tuple
import pydicom
from pydicom import FileDataset
from pathlib import Path

import supervisely as sly
from supervisely.io.fs import get_file_ext, get_file_name, get_file_name_with_ext, silent_remove

import sly_globals as g


def update_progress(count, api: sly.Api, task_id: int, progress: sly.Progress) -> None:
    count = min(count, progress.total - progress.current)
    progress.iters_done(count)
    if progress.need_report():
        progress.report_progress()


def get_progress_cb(api: sly.Api, task_id: int, message: str, total: int, is_size: bool = False,
                    func: Callable = update_progress) -> functools.partial:
    progress = sly.Progress(message, total, is_size=is_size)
    progress_cb = partial(func, api=api, task_id=task_id, progress=progress)
    progress_cb(0)
    return progress_cb


def get_free_name(group_name: str, image_name: str) -> str:
    """Generates new name for duplicated group image name."""
    original_name = image_name
    image_name, image_ext = get_file_name(image_name), get_file_ext(image_name)
    res_name = '{}_{}{}'.format(
        image_name, group_name, image_ext)
    g.my_app.logger.warn(
        f"Duplicated group image name found. Image: {original_name} has been renamed to {res_name}")
    return res_name


def is_dicom_file(path: str, verbose: bool = False) -> bool:
    """Checks if file is dicom file by given path."""
    try:
        pydicom.read_file(str(Path(path).resolve()), stop_before_pixels=True)
        result = True
    except Exception as ex:
        if verbose:
            print("'{}' appears not to be a DICOM file\n({})".format(path, ex))
            g.my_app.logger.warn(
                "'{}' appears not to be a DICOM file\n({})".format(path, ex))
        result = False
    return result


def download_data_from_team_files(api: sly.Api, task_id: int, save_path: str) -> str:
    """Download data from remote directory in Team Files."""
    project_path = None
    if g.INPUT_DIR is not None:
        remote_path = g.INPUT_DIR
        project_path = os.path.join(
            save_path, os.path.basename(os.path.normpath(remote_path)))
        sizeb = api.file.get_directory_size(g.TEAM_ID, remote_path)
        progress_cb = get_progress_cb(api=api,
                                      task_id=task_id,
                                      message=f"Downloading {remote_path.lstrip('/').rstrip('/')}",
                                      total=sizeb,
                                      is_size=True)
        api.file.download_directory(team_id=g.TEAM_ID,
                                    remote_path=remote_path,
                                    local_save_path=project_path,
                                    progress_cb=progress_cb)

    elif g.INPUT_FILE is not None:
        remote_path = g.INPUT_FILE
        save_archive_path = os.path.join(
            save_path, get_file_name_with_ext(remote_path))
        sizeb = api.file.get_info_by_path(g.TEAM_ID, remote_path).sizeb
        progress_cb = get_progress_cb(api=api,
                                      task_id=task_id,
                                      message=f"Downloading {remote_path.lstrip('/')}",
                                      total=sizeb,
                                      is_size=True)
        api.file.download(team_id=g.TEAM_ID,
                          remote_path=remote_path,
                          local_save_path=save_archive_path,
                          progress_cb=progress_cb)
        shutil.unpack_archive(save_archive_path, save_path)
        silent_remove(save_archive_path)
        if len(os.listdir(save_path)) > 1:
            g.my_app.logger.error(
                "There must be only 1 project directory in the archive")
            raise Exception(
                "There must be only 1 project directory in the archive")

        project_name = os.listdir(save_path)[0]
        project_path = os.path.join(save_path, project_name)
    return project_path


def get_dcm_image_name(image_path: str) -> str:
    """Returns image name with .nrrd extention."""
    # to save original name of dcm file without ext
    image_name_with_ext, image_ext = get_file_name_with_ext(
        image_path), get_file_ext(image_path)
    if image_ext.lstrip('.').isnumeric():
        image_name = image_name_with_ext + ".nrrd"
    else:
        image_name = get_file_name(image_path) + ".nrrd"
    return image_name


def create_group_tag(group_tag_info: Dict[str, str]) -> sly.Tag:
    """Creates grouping tag."""
    group_tag_name = group_tag_info["name"]
    group_tag_value = group_tag_info["value"]
    group_tag_meta = g.project_meta.get_tag_meta(group_tag_name)
    if group_tag_meta is not None:
        group_tag = sly.Tag(group_tag_meta, group_tag_value)
    else:
        group_tag_meta = sly.TagMeta(
            group_tag_name, sly.TagValueType.ANY_STRING)
        g.project_meta = g.project_meta.add_tag_meta(group_tag_meta)
        g.api.project.update_meta(
            id=g.project_id, meta=g.project_meta.to_json())
        g.api.project.images_grouping(
            id=g.project_id, enable=True, tag_name=g.GROUP_TAG_NAME)
        group_tag = sly.Tag(group_tag_meta, group_tag_value)
    return group_tag


def create_dcm_tags(dcm: FileDataset) -> List[sly.Tag]:
    """Create tags from DICOM metadata."""
    dcm_tags = []
    for dcm_tag in g.DCM_TAGS:
        try:
            dcm_tag_name = str(dcm[dcm_tag].name)
            dcm_tag_value = str(dcm[dcm_tag].value)
        except:
            dcm_filename = get_file_name(dcm.filename)
            g.my_app.logger(f"Couldn't find key: {dcm_tag} in file: {dcm_filename}")
            continue
        if dcm_tag_value is None:
            continue
        dcm_tag_meta = g.project_meta.get_tag_meta(dcm_tag_name)
        if dcm_tag_meta is not None:
            dcm_tag = sly.Tag(dcm_tag_meta, dcm_tag_value)
        else:
            dcm_tag_meta = sly.TagMeta(
                dcm_tag_name, sly.TagValueType.ANY_STRING)
            g.project_meta = g.project_meta.add_tag_meta(dcm_tag_meta)
            g.api.project.update_meta(
                id=g.project_id, meta=g.project_meta.to_json())
            dcm_tag = sly.Tag(dcm_tag_meta, dcm_tag_value)
        dcm_tags.append(dcm_tag)
    return dcm_tags


def create_ann_with_tags(path_to_img: str, group_tag_info: dict, dcm_tags: List[sly.Tag] = None) -> sly.Annotation:
    """Creates annotation with tags."""
    group_tag = create_group_tag(group_tag_info)
    tags_to_add = [group_tag]
    if dcm_tags is not None:
        tags_to_add += dcm_tags
    ann = sly.Annotation.from_img_path(path_to_img)
    tags_with_values = []
    for tag in tags_to_add:
        if tag.value is not None:
            tags_with_values.append(tag)
    ann = ann.add_tags(sly.TagCollection(tags_with_values))
    return ann


def dcm2nrrd(image_path: str, group_tag_name: str) -> Tuple[str, str, sly.Annotation]:
    """Converts DICOM data to nrrd format and returns image path, image name, and image annotation."""
    dcm = pydicom.read_file(image_path)
    dcm_tags = None
    if g.ADD_DCM_TAGS:
        dcm_tags = create_dcm_tags(dcm)

    pixel_data = dcm.pixel_array
    pixel_data = sly.image.rotate(img=pixel_data, degrees_angle=270)
    original_name = get_file_name(image_path)
    image_name = get_dcm_image_name(image_path)
    save_path = os.path.join(os.path.dirname(image_path), image_name)
    nrrd.write(save_path, pixel_data)

    try:
        group_tag_value = str(dcm[group_tag_name].value)
        group_tag = {"name": group_tag_name, "value": group_tag_value}
        ann = create_ann_with_tags(save_path, group_tag, dcm_tags)
    except:
        g.my_app.logger.warn(
            f"{group_tag_name} not found in {original_name} metadata")
        ann = sly.Annotation.from_img_path(save_path)
        if g.ADD_DCM_TAGS:
            ann = ann.add_tags(sly.TagCollection(dcm_tags))

    return save_path, image_name, ann
