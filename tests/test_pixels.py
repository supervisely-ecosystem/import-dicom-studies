"""Pixel data of converted single-frame images."""

import io

import pydicom
from conftest import ROOT, dicom_bytes, folder_files


def test_single_frame_image_keeps_its_size_and_pixels(run_app, tmp_path):
    """Old: sly.image.rotate(270) + fliplr added a black column (and a black row for square
    images): a 128x128 CT became 129x129. The intended result is the transposed pixel array."""

    files = folder_files({"ds1": {"a.dcm": dicom_bytes(), "b.dcm": dicom_bytes(kind="mr")}})
    api, g, error = run_app(files, folder=ROOT + "/")
    assert error is None
    assert api.ann_by_name("a.dcm.nrrd").img_size == (128, 128)
    assert api.ann_by_name("b.dcm.nrrd").img_size == (64, 64)
    source = pydicom.dcmread(io.BytesIO(dicom_bytes())).pixel_array
    assert (api.pixels_by_name("a.dcm.nrrd") == source.T).all()
