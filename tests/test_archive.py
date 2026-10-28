"""Archive extraction from Team Files."""

import io

from conftest import dicom_bytes, make_tar


def test_tar_member_outside_target_is_not_extracted(run_app, tmp_path):
    """A teammate's crafted .tar must not write outside the app data dir."""
    archive = make_tar({"cardio/ds1/a.dcm": dicom_bytes(), "../escape.txt": b"pwned"})
    api, g, error = run_app({"/up/evil.tar": archive}, file="/up/evil.tar")
    assert not (tmp_path / "escape.txt").exists()
    assert error is not None
    assert not api.images


def test_tar_symlink_out_of_target_is_refused(run_app, tmp_path):
    import tarfile

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        link = tarfile.TarInfo("cardio/ds1/link")
        link.type, link.linkname = tarfile.SYMTYPE, str(tmp_path)
        tar.addfile(link)
        data = b"pwned"
        member = tarfile.TarInfo("cardio/ds1/link/escape.txt")
        member.size = len(data)
        tar.addfile(member, io.BytesIO(data))
    api, g, error = run_app({"/up/evil.tar": buf.getvalue()}, file="/up/evil.tar")
    assert not (tmp_path / "escape.txt").exists()
    assert error is not None


def test_zip_archive_is_imported(run_app):
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("cardio/ds1/a.dcm", dicom_bytes())
    api, g, error = run_app({"/up/ok.zip": buf.getvalue()}, file="/up/ok.zip")
    assert error is None
    assert api.image_names("ds1") == ["a.dcm.nrrd"]
