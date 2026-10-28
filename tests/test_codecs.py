"""Compressed DICOM transfer syntaxes the published image (import-export) could decode."""

import pytest
from pydicom.data import get_testdata_file

from conftest import ROOT


@pytest.mark.parametrize(
    "name", ["MR_small_jpeg_ls_lossless.dcm", "MR_small_RLE.dcm", "JPEG2000.dcm"]
)
def test_compressed_dicom_is_imported(run_app, name):
    with open(get_testdata_file(name), "rb") as fh:
        data = fh.read()
    api, g, error = run_app({f"{ROOT}/ds1/{name}": data}, folder=ROOT + "/")
    assert error is None
    assert api.image_names() == [f"{name}.nrrd"]
