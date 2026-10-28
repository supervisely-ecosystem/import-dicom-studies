"""The hardened image runs Python 3.14: no distutils, pydicom 3."""

import pydicom
from conftest import ROOT, dicom_bytes, folder_files


def test_settings_load_without_distutils(run_app):
    """distutils is gone from Python >= 3.12 (the hardened image runs 3.14)."""
    api, g, error = run_app(
        folder_files({"ds1": {"a.dcm": dicom_bytes()}}), folder=ROOT + "/", hide_distutils=True
    )
    assert error is None
    assert g.WITH_ANNS is False


def test_import_works_without_pydicom_read_file(run_app, monkeypatch):
    """pydicom 3 (installed with the SDK on Python >= 3.10) removed pydicom.read_file."""
    monkeypatch.delattr(pydicom, "read_file", raising=False)
    files = folder_files({"ds1": {"a.dcm": dicom_bytes(), "b.dcm": dicom_bytes(kind="mr")}})
    api, g, error = run_app(files, folder=ROOT + "/")
    assert error is None
    assert api.image_names("ds1") == ["a.dcm.nrrd", "b.dcm.nrrd"]
