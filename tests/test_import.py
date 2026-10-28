"""End-to-end behaviour that already worked before the fixes (regression guard)."""

import io

import pydicom
from conftest import ROOT, dicom_bytes, folder_files, make_tar, note, sly_project


def test_folder_import_groups_by_study(run_app):
    files = folder_files({"ds1": {"a.dcm": dicom_bytes(), "b.dcm": dicom_bytes(kind="mr")}})
    api, g, error = run_app(files, folder=ROOT + "/")
    assert error is None
    assert list(api.projects.values()) == ["cardio"]
    ann = api.ann_by_name("a.dcm.nrrd")
    study = pydicom.dcmread(io.BytesIO(dicom_bytes())).StudyInstanceUID
    assert ann.img_tags.get("StudyInstanceUID").value == study
    assert api.grouping[next(iter(api.projects))] == "StudyInstanceUID"


def test_nested_folders_become_datasets(run_app):
    files = folder_files({"a": {"x.dcm": dicom_bytes()}, "a/b": {"y.dcm": dicom_bytes(kind="mr")}})
    api, g, error = run_app(files, folder=ROOT + "/")
    assert error is None
    assert sorted(d["name"] for d in api.datasets.values()) == ["a", "b"]
    assert api.image_names() == ["x.dcm.nrrd", "y.dcm.nrrd"]


def test_multiframe_file_is_split_into_frames(run_app):
    files = folder_files({"ds1": {"mf.dcm": dicom_bytes(kind="multiframe")}})
    api, g, error = run_app(files, folder=ROOT + "/")
    assert error is None
    assert api.image_names() == ["1_mf.dcm.nrrd", "2_mf.dcm.nrrd", "3_mf.dcm.nrrd"]


def test_tar_archive_is_imported(run_app):
    archive = make_tar(
        {"cardio/ds1/a.dcm": dicom_bytes(), "cardio/ds1/b.dcm": dicom_bytes(kind="mr")}
    )
    api, g, error = run_app({"/up/ok.tar": archive}, file="/up/ok.tar")
    assert error is None
    assert api.image_names("ds1") == ["a.dcm.nrrd", "b.dcm.nrrd"]


def test_all_dicom_tags_are_added(run_app):
    files = folder_files({"ds1": {"a.dcm": dicom_bytes(Manufacturer="ACME")}})
    api, g, error = run_app(files, folder=ROOT + "/", add_tags="All tags")
    assert error is None
    tags = {t.meta.name: t.value for t in api.ann_by_name("a.dcm.nrrd").img_tags}
    assert tags.get("Manufacturer") == "ACME"
    assert "Rows" in tags


def test_annotation_named_without_dicom_extension(run_app):
    """README layout: img/IMG-0001.dcm + ann/IMG-0001.json."""
    images = {"IMG-0001.dcm": dicom_bytes(), "IMG-0002.dcm": dicom_bytes()}
    files = sly_project({"IMG-0001.json": "one", "IMG-0002.json": "two"}, images)
    api, g, error = run_app(files, folder=ROOT + "/", with_anns=True)
    assert error is None
    assert note(api, "IMG-0001.dcm.nrrd") == "one"
    assert note(api, "IMG-0002.dcm.nrrd") == "two"


def test_folder_without_dicom_reports_error(run_app):
    api, g, error = run_app({f"{ROOT}/ds1/readme.txt": b"hello"}, folder=ROOT + "/")
    assert api.errors == ["No DICOM data found."]
    assert not api.projects
