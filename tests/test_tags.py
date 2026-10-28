"""DICOM metadata as image tags."""

from conftest import ROOT, dicom_bytes, folder_files


def test_only_specified_dicom_tags_are_added(run_app):
    """Old: since v1.2.x "Only specified tags" added no tags at all."""
    files = folder_files({"ds1": {"a.dcm": dicom_bytes(Manufacturer="ACME")}})
    api, g, error = run_app(
        files,
        folder=ROOT + "/",
        add_tags="Only specified tags",
        dcm_tags='{"tags": ["Modality", "Manufacturer"]}',
    )
    assert error is None
    tags = {t.meta.name: t.value for t in api.ann_by_name("a.dcm.nrrd").img_tags}
    assert tags.get("Modality") == "CT"
    assert tags.get("Manufacturer") == "ACME"
    assert "Rows" not in tags  # not requested
