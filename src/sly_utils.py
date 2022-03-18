import functools
import nrrd
import os
import shutil
from functools import partial
from typing import Callable, List, Tuple
import pydicom
from pathlib import Path

import supervisely as sly
from supervisely.io.fs import (dir_exists, file_exists, get_file_ext,
                               get_file_name, get_file_name_with_ext,
                               silent_remove)

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


def is_dicom_file(path, verbose=False):
    try:
        pydicom.read_file(str(Path(path).resolve()), stop_before_pixels=True)
        result = True
    except Exception as ex:
        if verbose:
            print("'{}' appears not to be a DICOM file\n({})".format(path, ex))
        result = False
    return result


def download_data_from_team_files(api: sly.Api, task_id, save_path: str) -> str:
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
            g.my_app.logger.error("There must be only 1 project directory in the archive")
            raise Exception("There must be only 1 project directory in the archive")

        project_name = os.listdir(save_path)[0]
        project_path = os.path.join(save_path, project_name)
    return project_path


def create_meta_with_tags():
    study_iuid_meta = sly.TagMeta("StudyInstanceUID", sly.TagValueType.ANY_STRING)
    series_iuid_meta = sly.TagMeta("SeriesInstanceUID", sly.TagValueType.ANY_STRING)
    project_meta = sly.ProjectMeta(tag_metas=sly.TagMetaCollection([study_iuid_meta, series_iuid_meta]))
    return project_meta, study_iuid_meta, series_iuid_meta


def create_ann_with_uid_tags(path_to_img, study_iuid, series_iuid, study_iuid_tag_meta, series_iui_tag_meta):
    study_iuid_tag = sly.Tag(study_iuid_tag_meta, study_iuid)
    series_iuid_tag = sly.Tag(series_iui_tag_meta, series_iuid)

    ann = sly.Annotation.from_img_path(path_to_img)
    ann = ann.add_tags(sly.TagCollection([study_iuid_tag, series_iuid_tag]))
    return ann


def dcm2nrrd(image_path, study_iuid_tag_meta, series_iui_tag_meta):
    # if is_dicom_file(image_path):
    dcm = pydicom.read_file(image_path)
    study_iuid = dcm.StudyInstanceUID
    series_iuid = dcm.SeriesInstanceUID
    pixel_data = dcm.pixel_array

    image_name = get_file_name(image_path) + ".nrrd"
    save_path = os.path.join(os.path.dirname(image_path), image_name)
    nrrd.write(save_path, pixel_data)
    ann = create_ann_with_uid_tags(save_path, study_iuid, series_iuid, study_iuid_tag_meta, series_iui_tag_meta)
    return save_path, image_name, ann
