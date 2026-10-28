"""What a Team Files selection resolves to."""

import json

import supervisely as sly
from conftest import ROOT, dicom_bytes, folder_files, sly_project


def test_dicom_files_directly_in_selected_folder(run_app):
    api, g, error = run_app({f"{ROOT}/a.dcm": dicom_bytes()}, folder=ROOT + "/")
    assert error is None
    assert api.image_names() == ["a.dcm.nrrd"]


def test_selected_dicom_file_imports_its_folder(run_app):
    files = folder_files({"ds1": {"a.dcm": dicom_bytes(), "b.dcm": dicom_bytes()}})
    api, g, error = run_app(files, file=f"{ROOT}/ds1/a.dcm")
    assert error is None
    assert api.image_names() == ["a.dcm.nrrd", "b.dcm.nrrd"]


def test_selected_meta_json_imports_the_project(run_app):
    """Old: the check compared the full path with "meta.json", so selecting the meta.json of a
    Supervisely-format project ended with "file is not an archive"."""
    files = sly_project({"a.dcm.json": "A"}, {"a.dcm": dicom_bytes()})
    api, g, error = run_app(files, file=f"{ROOT}/meta.json", with_anns=True)
    assert error is None
    assert api.image_names() == ["a.dcm.nrrd"]


def test_sly_meta_tags_named_like_import_tags(run_app):
    """Old: two Supervisely meta tags in a row with the same names as import tags - the list was
    modified while iterating, the second duplicate stayed and the import failed."""
    meta = sly.ProjectMeta(
        tag_metas=[
            sly.TagMeta("StudyInstanceUID", sly.TagValueType.ANY_STRING),
            sly.TagMeta("Modality", sly.TagValueType.ANY_STRING),
        ]
    )
    files = {
        f"{ROOT}/meta.json": json.dumps(meta.to_json()).encode(),
        f"{ROOT}/ds1/img/a.dcm": dicom_bytes(),
        f"{ROOT}/ds1/ann/a.dcm.json": json.dumps(sly.Annotation((128, 128)).to_json()).encode(),
    }
    api, g, error = run_app(files, folder=ROOT + "/", with_anns=True, add_tags="All tags")
    assert error is None
    names = [t["name"] for t in next(iter(api.metas.values()))["tags"]]
    assert len(names) == len(set(names))
