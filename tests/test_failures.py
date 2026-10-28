"""Files that cannot be converted must not be reported as a success."""

from conftest import ROOT, dicom_bytes, folder_files


def test_unreadable_file_fails_the_task_and_keeps_imported_images(run_app):
    """Old: the broken file was only logged and the task finished as a success."""
    files = folder_files(
        {
            "ds1": {
                "a.dcm": dicom_bytes(),
                "b.dcm": dicom_bytes(),
                "c.dcm": dicom_bytes(corrupt=True),
            }
        }
    )
    api, g, error = run_app(files, folder=ROOT + "/")
    assert api.image_names("ds1") == ["a.dcm.nrrd", "b.dcm.nrrd"]
    assert error is not None
    assert "1" in str(error) and "c.dcm" in str(error)


def test_failed_later_batch_keeps_earlier_batches(run_app):
    """Old: when every file of the 2nd upload batch (files 51+) failed, the whole dataset - with
    the 50 images already uploaded - was removed and the task still finished as a success."""
    good = {f"img_{i:03d}.dcm": dicom_bytes() for i in range(50)}
    bad = {"z1.dcm": dicom_bytes(corrupt=True), "z2.dcm": dicom_bytes(corrupt=True)}
    files = folder_files({"ds_ok": {"a.dcm": dicom_bytes()}, "ds_big": {**good, **bad}})
    api, g, error = run_app(files, folder=ROOT + "/")
    assert len(api.image_names("ds_big")) == 50
    assert api.image_names("ds_ok") == ["a.dcm.nrrd"]
    assert error is not None and "2" in str(error)
