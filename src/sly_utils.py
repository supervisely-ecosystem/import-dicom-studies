import functools
import json
import os
import tarfile
import zipfile
from functools import partial
from os.path import basename, dirname, exists, join, normpath
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import nrrd
import numpy as np
import pydicom
import supervisely as sly
from pydicom import FileDataset
from supervisely.io.fs import (
    file_exists,
    get_file_ext,
    get_file_name_with_ext,
    silent_remove,
)
from tqdm import tqdm

import sly_globals as g


def import_dataset(api: sly.Api, dataset_path: str) -> None:
    """Imports a single dataset into the project."""
    # Create a new dataset in the project
    dataset_name = basename(normpath(dataset_path))
    dataset_info = api.dataset.create(
        project_id=g.project_id, name=dataset_name, change_name_if_conflict=True
    )

    batch_size = 50
    # Process the images in batches
    ds_images_paths, ds_annotations_paths = get_paths(dataset_path, with_anns=g.WITH_ANNS)
    batch_progress = tqdm(total=len(ds_images_paths), desc="Processing Images", unit="image")

    for batch_imgs, batch_anns in zip(
        sly.batched(ds_images_paths, batch_size),
        sly.batched(ds_annotations_paths, batch_size),
    ):
        import_images(api, dataset_info, batch_imgs, batch_anns)
        batch_progress.update(len(batch_imgs))
    batch_progress.close()


def import_images(
    api: sly.Api, dataset: sly.DatasetInfo, batch_imgs: list, batch_anns: list
) -> None:
    img_paths = []
    img_names = []
    anns = []
    img_metas = []

    for image_path, annotation_path in zip(batch_imgs, batch_anns):
        try:
            image_paths, image_names, anns_from_dcm, dcm_meta = dcm2nrrd(
                image_path=image_path,
                group_tag_name=g.GROUP_TAG_NAME,
            )
        except Exception as e:
            sly.logger.warning(f"File '{image_path}' will be skipped due to: {repr(e)}")
            continue

        img_paths.extend(image_paths)
        img_names.extend(image_names)
        img_metas.extend([dcm_meta for _ in image_paths])

        if g.WITH_ANNS:
            ann = sly.Annotation.load_json_file(annotation_path, g.project_meta_from_sly_format)

            for ann_dcm in anns_from_dcm:
                ann = ann.merge(ann_dcm)
            anns.append(ann)
        else:
            anns.extend(anns_from_dcm)

    if len(img_paths) == 0:
        api.dataset.remove(dataset.id)
        raise FileNotFoundError("Nothing to import")

    dst_image_infos = api.image.upload_paths(
        dataset_id=dataset.id, names=img_names, paths=img_paths, metas=img_metas
    )
    dst_image_ids = [img_info.id for img_info in dst_image_infos]

    # Merge meta from annotations (if supervisely format) with other tags
    if g.WITH_ANNS:
        _meta_dct = g.project_meta_from_sly_format.to_json()
        _new_meta_cct = g.project_meta.to_json()
        remove_sly_tag_name_if_not_unique(_meta_dct, _new_meta_cct)
        _meta_dct["tags"] += _new_meta_cct["tags"]
        check_unique_name(_meta_dct["tags"])  # left for emergency cases
    else:
        _meta_dct = g.project_meta.to_json()

    # Update the project metadata and enable image grouping
    api.project.update_meta(id=g.project_id, meta=_meta_dct)
    api.project.images_grouping(id=g.project_id, enable=True, tag_name=g.GROUP_TAG_NAME)

    api.annotation.upload_anns(img_ids=dst_image_ids, anns=anns)


def get_paths(dataset_path: str, with_anns: bool = False) -> Tuple[List[str], List[str]]:
    if with_anns:
        subfolders = os.listdir(dataset_path)
        # check supervisely format
        # Learn more here: https://docs.supervise.ly/data-organization/00_ann_format_navi
        if "img" not in subfolders or "ann" not in subfolders:
            raise ValueError(
                "The 'img' and/or 'ann' folders do not exist in the dataset path. "
                f"Learn more about <a href='{g.SLY_FORMAT_DOCS}'>Supervisely format</a>."
            )

        img_dirname, ann_dirname = join(dataset_path, "img"), join(dataset_path, "ann")
        dataset_path = img_dirname

    ds_images_paths = sorted(
        [
            join(dataset_path, item)
            for item in os.listdir(dataset_path)
            if file_exists(join(dataset_path, item)) and is_dicom_file(join(dataset_path, item))
        ]
    )

    if with_anns:
        ds_annotations_paths = sorted(
            [
                join(ann_dirname, item)
                for item in os.listdir(ann_dirname)
                if file_exists(join(ann_dirname, item)) and is_json_file(join(ann_dirname, item))
            ]
        )
    else:
        ds_annotations_paths = [None for _ in ds_images_paths]

    return ds_images_paths, ds_annotations_paths


def remove_sly_tag_name_if_not_unique(sly_meta, new_meta):
    for s_tag in sly_meta["tags"]:
        for n_tag in new_meta["tags"]:
            if s_tag["name"] == n_tag["name"]:
                sly_meta["tags"].remove(s_tag)
                sly.logger.warning(
                    f"There was tag [{s_tag['name']}] in Supervisely meta with the same name as the grouping tag on the import! Supervisely tag was replaced with import tag. If you want to separate them, you need to manually correct the annotation and meta .json files, or select a different grouping tag on import."
                )


def check_unique_name(lst: List[Dict[str, str]]) -> None:
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


def is_dicom_folder(dir_path: str) -> List[str]:
    return any([is_dicom_file(f.path) for f in os.scandir(dir_path)])


def check_image_project_structure(root_dir: str, with_anns: bool) -> None:
    if with_anns:
        try:
            meta_file = join(root_dir, "meta.json")

            if not exists(meta_file):
                raise Exception(
                    f"Missing meta.json file. Learn more about <a href='{g.SLY_FORMAT_DOCS}'>Supervisely format</a>."
                )
            for dataset_dir in os.scandir(root_dir):
                if not dataset_dir.is_dir():
                    continue

                img_dir = join(dataset_dir.path, "img")
                ann_dir = join(dataset_dir.path, "ann")

                if not exists(img_dir):
                    raise Exception(
                        f"Missing 'img' directory in dataset directory: {dataset_dir.path}. "
                        f"Learn more about <a href='{g.SLY_FORMAT_DOCS}'>Supervisely format</a>."
                    )
                if not exists(ann_dir):
                    raise Exception(
                        f"Missing 'ann' directory in dataset directory: {dataset_dir.path}. "
                        f"Learn more about <a href='{g.SLY_FORMAT_DOCS}'>Supervisely format</a>."
                    )
                for data_file in os.scandir(img_dir):
                    if data_file.is_file():
                        if not is_dicom_file(data_file.path):
                            g.my_app.logger.warn(
                                f"Unexpected file '{data_file.name}' in 'img' directory: {img_dir}"
                            )
                for json_file in os.scandir(ann_dir):
                    if json_file.is_file() and not json_file.name.lower().endswith(".json"):
                        g.my_app.logger.warn(
                            f"Unexpected file '{json_file.name}' in 'ann' directory: {ann_dir}"
                        )
            g.my_app.logger.info(f"Project structure is correct")
        except Exception as e:
            sly.logger.warn("Failed checking Supervisely format.")
            sly.logger.warn(str(e))
            g.WITH_ANNS = False


def check_ds_dirs(dataset_dirs: list) -> List[str]:
    valid_dataset_dirs = []
    for dataset_dir in dataset_dirs:
        if not sly.fs.dir_exists(dataset_dir):
            continue
        dicom_files_count = 0
        for data_file in os.scandir(dataset_dir):
            if data_file.is_file() and is_dicom_file(data_file.path):
                dicom_files_count += 1
            else:
                g.my_app.logger.warn(
                    f"Unexpected file '{data_file.name}' in directory: {dataset_dir}"
                )
        if dicom_files_count > 0:
            valid_dataset_dirs.append(dataset_dir)
    return valid_dataset_dirs


def check_extension_in_folder(folder_path: str, extension: str) -> bool:
    for item in os.scandir(folder_path):
        if item.is_file() and item.path.lower().endswith(extension):
            return True
    return False


def is_dicom_file(path: str, verbose: bool = False) -> bool:
    """Checks if file is DICOM file by given path."""
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


def is_archive(path, local=True):
    if local and tarfile.is_tarfile(path):
        return True
    elif local and zipfile.is_zipfile(path):
        return True
    return get_file_ext(path) in [".zip", ".tar"] or path.endswith(".tar.gz")


def handle_input_path(api: sly.Api) -> str:
    """Handle input path."""
    if not g.IS_ON_AGENT:
        if g.INPUT_DIR:
            listdir = api.file.listdir(g.TEAM_ID, g.INPUT_DIR)
            if len(listdir) == 1 and is_archive(listdir[0], local=False):
                sly.logger.info("Folder mode is selected, but archive file is uploaded.")
                sly.logger.info("Switching to file mode.")
                g.INPUT_DIR, g.INPUT_FILE = None, join(g.INPUT_DIR, listdir[0])
        elif g.INPUT_FILE:
            if not is_archive(g.INPUT_FILE, local=False):
                sly.logger.info("File mode is selected, but uploaded file is not archive.")
                if g.INPUT_FILE.lower() == "meta.json":
                    sly.logger.info("Switching to folder mode.")
                    g.INPUT_FILE, g.INPUT_DIR = None, dirname(g.INPUT_FILE)
                elif get_file_ext(g.INPUT_FILE) in [".json", ".dcm"]:
                    possible_ds_dir = dirname(dirname(g.INPUT_FILE))
                    possible_img_dir = join(possible_ds_dir, "img")
                    possible_ann_dir = join(possible_ds_dir, "ann")
                    possible_proj_dir = dirname(possible_ds_dir)

                    ds_listdir = api.file.listdir(g.TEAM_ID, possible_ds_dir)
                    ann_listdir = api.file.listdir(g.TEAM_ID, possible_ann_dir)

                    contains_json = any([get_file_ext(f) == ".json" for f in ann_listdir])
                    is_ds_dir = all([basename(normpath(f)) in ["img", "ann"] for f in ds_listdir])
                    meta_exists = api.file.exists(g.TEAM_ID, join(possible_proj_dir, "meta.json"))

                    if contains_json and is_ds_dir and meta_exists:
                        sly.logger.info("Supervisely format is detected. Switching to folder mode.")
                        g.INPUT_FILE, g.INPUT_DIR = None, possible_proj_dir
                    elif api.file.dir_exists(g.TEAM_ID, possible_img_dir):
                        sly.logger.info("Supervisely format is not detected.")
                        sly.logger.info("Found 'img' directory. Switching to folder mode.")
                        g.INPUT_FILE, g.INPUT_DIR = None, possible_img_dir
                        g.WITH_ANNS = False
                    elif get_file_ext(g.INPUT_FILE) == ".dcm":
                        sly.logger.info("Supervisely format is not detected.")
                        g.INPUT_FILE, g.INPUT_DIR = None, dirname(g.INPUT_FILE)
                        g.WITH_ANNS = False


def download_data_from_team_files(api: sly.Api, task_id: int, save_path: str) -> str:
    """Download data from remote directory in Team Files."""
    handle_input_path(api)
    project_path = None
    if g.INPUT_DIR is not None:
        sly.logger.info(f"Input directory: {g.INPUT_DIR}")
        if g.IS_ON_AGENT:
            _, cur_files_path = api.file.parse_agent_id_and_path(g.INPUT_DIR)
        else:
            cur_files_path = g.INPUT_DIR

        remote_path = g.INPUT_DIR
        project_path = join(save_path, basename(normpath(cur_files_path)))
        sizeb = api.file.get_directory_size(g.TEAM_ID, remote_path)
        progress_cb = tqdm(
            total=sizeb,
            desc=f"Downloading {remote_path.lstrip('/').rstrip('/')}",
            unit="B",
            unit_scale=True,
        )
        api.file.download_directory(
            team_id=g.TEAM_ID,
            remote_path=remote_path,
            local_save_path=project_path,
            progress_cb=progress_cb,
        )
        progress_cb.close()
        sly.fs.remove_junk_from_dir(project_path)

    elif g.INPUT_FILE is not None:
        sly.logger.info(f"Input file: {g.INPUT_FILE}")
        if g.IS_ON_AGENT:
            _, cur_files_path = api.file.parse_agent_id_and_path(g.INPUT_FILE)
        else:
            cur_files_path = g.INPUT_FILE

        remote_path = g.INPUT_FILE
        save_archive_path = join(save_path, get_file_name_with_ext(normpath(cur_files_path)))
        sizeb = api.file.get_info_by_path(g.TEAM_ID, remote_path).sizeb
        progress_cb = tqdm(
            total=sizeb,
            desc=f"Downloading {remote_path.lstrip('/')}",
            unit="B",
            unit_scale=True,
        )
        api.file.download(
            team_id=g.TEAM_ID,
            remote_path=remote_path,
            local_save_path=save_archive_path,
            progress_cb=progress_cb,
        )
        progress_cb.close()
        if is_archive(save_archive_path):
            sly.fs.unpack_archive(save_archive_path, save_path, remove_junk=True)
        else:
            silent_remove(save_archive_path)
            title = "Incorrect input data: file is not an archive."
            description = "Read more in the app description."
            api.task.set_output_error(task_id, title=title, description=description)
            g.my_app.logger.error(f"{title} {description}")
            g.my_app.stop()
            return None
        silent_remove(save_archive_path)
        if len(os.listdir(save_path)) > 1:
            g.my_app.logger.error("There must be only 1 project directory in the archive")
            raise Exception("There must be only 1 project directory in the archive")

        project_name = os.listdir(save_path)[0]
        project_path = join(save_path, project_name)
    return project_path


def find_frame_axis(pixel_data: np.ndarray, frames: int):
    for axis in range(len(pixel_data.shape)):
        if pixel_data.shape[axis] == frames:
            return axis
    raise ValueError("Unable to recognize the frame axis for splitting a set of images")


def create_pixel_data_set(dcm: FileDataset, frame_axis):
    if frame_axis == 0:
        pixel_array = np.transpose(dcm.pixel_array, (2, 1, 0))
    elif frame_axis == 1:
        pixel_array = np.transpose(dcm.pixel_array, (2, 0, 1))
    else:
        pixel_array = dcm.pixel_array
    frame_axis = 2
    list_of_images = np.split(pixel_array, int(dcm.NumberOfFrames), axis=frame_axis)
    return list_of_images, frame_axis


def get_nrrd_header(image_path: str, frame_axis: int = 2):
    _, meta = sly.volume.read_dicom_serie_volume([image_path], False)
    dimensions: Dict = meta.get("dimensionsIJK")
    header = {
        "type": "float",
        "sizes": [dimensions.get("x"), dimensions.get("y")],
        "dimension": 2,
        "space": "right-anterior-superior",
    }

    if frame_axis == 0:
        spacing = meta["spacing"][1:]
        header["space directions"] = [[spacing[0], 0], [0, spacing[1]]]
    if frame_axis == 1:
        spacing = meta["spacing"][0::2]
        header["space directions"] = [[spacing[0], 0], [0, spacing[1]]]
    if frame_axis == 2:
        spacing = meta["spacing"][0:2]
        header["space directions"] = [[spacing[0], 0], [0, spacing[1]]]
    return header


def dcm2nrrd(
    image_path: str,
    group_tag_name: str,
) -> Tuple[str, str, sly.Annotation]:
    """Converts DICOM data to nrrd format and returns image paths, image names, and image annotations."""
    dcm = pydicom.read_file(image_path)
    dcm_tags, dcm_meta = create_dcm_tags(dcm)
    
    pixel_data_list = [dcm.pixel_array]

    if len(dcm.pixel_array.shape) == 3:
        if dcm.pixel_array.shape[0] == 1 and not hasattr(dcm, "NumberOfFrames"):
            frames = 1
            pixel_data_list = [
                dcm.pixel_array.reshape((dcm.pixel_array.shape[1], dcm.pixel_array.shape[2]))
            ]
            header = get_nrrd_header(image_path)
        else:
            try:
                frames = int(dcm.NumberOfFrames)
            except AttributeError as e:
                if str(e) == "'FileDataset' object has no attribute 'NumberOfFrames'":
                    e.args = ("can't get 'NumberOfFrames' from dcm meta.",)
                    raise e
            frame_axis = find_frame_axis(dcm.pixel_array, frames)
            pixel_data_list, frame_axis = create_pixel_data_set(dcm, frame_axis)
            header = get_nrrd_header(image_path, frame_axis)
    elif len(dcm.pixel_array.shape) == 2:
        frames = 1
        header = get_nrrd_header(image_path)
    else:
        raise NotImplementedError(
            f"this type of dcm data is not supported, pixel_array.shape = {len(dcm.pixel_array.shape)}"
        )

    save_paths = []
    image_names = []
    anns = []
    frames_list = [f"{i:0{len(str(frames))}d}" for i in range(1, frames + 1)]

    for pixel_data, frame_number in zip(pixel_data_list, frames_list):
        original_name = get_file_name_with_ext(image_path)

        if frames == 1:
            pixel_data = sly.image.rotate(img=pixel_data, degrees_angle=270)
            pixel_data = sly.image.fliplr(pixel_data)
            image_name = f"{original_name}.nrrd"
        else:
            pixel_data = np.squeeze(pixel_data, frame_axis)
            image_name = f"{frame_number}_{original_name}.nrrd"

        save_path = join(dirname(image_path), image_name)
        nrrd.write(save_path, pixel_data, header)
        save_paths.append(save_path)
        image_names.append(image_name)
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
            if dcm_tags is not None:
                ann = ann.add_tags(sly.TagCollection(dcm_tags))
        anns.append(ann)
    return save_paths, image_names, anns, dcm_meta


def create_dcm_tags(dcm: FileDataset) -> List[sly.Tag]: # ! Incorrect return type, to fix.
    """Create tags from DICOM metadata."""
    if g.ADD_DCM_TAGS == g.DO_NOT_ADD:
        return [], {}

    tags_from_dcm, dcm_tags_dict = [], {}
    if g.ADD_DCM_TAGS == g.ADD_ALL:
        g.DCM_TAGS = list(dcm.keys())
    for dcm_tag in list(dcm.keys()):
        try:
            curr_tag = dcm[dcm_tag]
            dcm_tag_name = str(curr_tag.name)
            dcm_tag_value = str(curr_tag.value)
            if dcm_tag_value in ["", None]:
                sly.logger.warn(f"Tag [{dcm_tag_name}] has empty value. Skipping tag.")
                continue
            if len(dcm_tag_value) > 255:
                sly.logger.warn(f"Tag [{dcm_tag_name}] has too long value. Skipping tag.")
                continue
            if g.ADD_DCM_TAGS == g.ADD_ALL:
                tags_from_dcm.append((dcm_tag_name, dcm_tag_value))
            dcm_tags_dict[dcm_tag_name] = dcm_tag_value
        except:
            dcm_filename = get_file_name_with_ext(dcm.filename)
            g.my_app.logger.warn(
                f"Couldn't find key: '{dcm_tag}' in file's metadata: '{dcm_filename}'"
            )
            continue

    dcm_sly_tags = []
    for dcm_tag_name, dcm_tag_value in tags_from_dcm:
        dcm_tag_meta = g.project_meta.get_tag_meta(dcm_tag_name)
        if dcm_tag_meta is None:
            dcm_tag_meta = sly.TagMeta(dcm_tag_name, sly.TagValueType.ANY_STRING)
            g.project_meta = g.project_meta.add_tag_meta(dcm_tag_meta)

        dcm_tag = sly.Tag(dcm_tag_meta, dcm_tag_value)
        dcm_sly_tags.append(dcm_tag)

    return dcm_sly_tags, dcm_tags_dict


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
