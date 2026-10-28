"""Supervisely-format annotations next to DICOM files."""

import json

import supervisely as sly
from conftest import ROOT, dicom_bytes, note, sly_project


def test_annotations_are_matched_by_file_name(run_app):
    """Old: image and annotation lists were sorted separately and zipped, so a missing
    annotation shifted every later one to the wrong image and dropped the last image."""
    images = {"a.dcm": dicom_bytes(), "b.dcm": dicom_bytes(), "c.dcm": dicom_bytes()}
    files = sly_project({"a.dcm.json": "A", "c.dcm.json": "C"}, images)
    api, g, error = run_app(files, folder=ROOT + "/", with_anns=True)
    assert error is None
    assert api.image_names("ds1") == ["a.dcm.nrrd", "b.dcm.nrrd", "c.dcm.nrrd"]
    assert [note(api, n) for n in api.image_names("ds1")] == ["A", None, "C"]


def test_multiframe_with_annotation_tags(run_app):
    """Old: one annotation for three frames -> upload_anns length mismatch."""
    images = {"mf.dcm": dicom_bytes(kind="multiframe")}
    files = sly_project({}, images)
    meta = sly.ProjectMeta.from_json(json.loads(files[f"{ROOT}/meta.json"]))
    ann = sly.Annotation((64, 64)).add_tag(sly.Tag(meta.get_tag_meta("note"), "mf"))
    files[f"{ROOT}/ds1/ann/mf.dcm.json"] = json.dumps(ann.to_json()).encode()
    api, g, error = run_app(files, folder=ROOT + "/", with_anns=True)
    assert error is None
    assert [note(api, n) for n in api.image_names()] == ["mf", "mf", "mf"]


def test_multiframe_with_labels_is_reported_not_guessed(run_app):
    """Labels of one annotation file cannot be assigned to frames: the file fails visibly."""
    obj_class = sly.ObjClass("lesion", sly.Rectangle)
    meta = sly.ProjectMeta(obj_classes=[obj_class])
    ann = sly.Annotation((64, 64), [sly.Label(sly.Rectangle(1, 1, 10, 10), obj_class)])
    files = {
        f"{ROOT}/meta.json": json.dumps(meta.to_json()).encode(),
        f"{ROOT}/ds1/img/mf.dcm": dicom_bytes(kind="multiframe"),
        f"{ROOT}/ds1/img/a.dcm": dicom_bytes(),
        f"{ROOT}/ds1/ann/mf.dcm.json": json.dumps(ann.to_json()).encode(),
    }
    api, g, error = run_app(files, folder=ROOT + "/", with_anns=True)
    assert api.image_names() == ["a.dcm.nrrd"]
    assert error is not None and "mf.dcm" in str(error)
