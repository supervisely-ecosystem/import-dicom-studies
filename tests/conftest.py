"""Offline test harness for import-dicom-studies.

The real src/sly_globals.py is imported with `AppService` and `sly.Api.from_env` replaced by
in-memory fakes, so the modal-state parsing runs as in production but nothing talks to a
Supervisely server. DICOM files are real files built from pydicom's bundled test data.

App code is imported from ../src, or from $APP_SRC (run the same tests against an older checkout).

    pip install -r dev_requirements.txt pytest && python -m pytest tests
"""

import importlib
import io
import json
import os
import sys
import tarfile
from types import SimpleNamespace

import numpy as np
import pytest
import supervisely as sly

SRC = os.path.abspath(
    os.environ.get("APP_SRC", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
)
APP_MODULES = ("sly_globals", "sly_utils", "main", "workflow")


class FakeAppService:
    def __init__(self, *args, **kwargs):
        import supervisely as sly

        self.logger = sly.logger
        self.data_dir = os.environ["SLY_APP_DATA_DIR"]
        self.stopped = False

    def callback(self, name):
        return lambda fn: fn

    def stop(self, *args, **kwargs):
        self.stopped = True


class FakeFileApi:
    """Team Files as {"/abs/path": bytes}; directories are implicit."""

    def __init__(self, files):
        self.files = dict(files)
        self.removed = []

    @staticmethod
    def _prefix(path):
        return path.rstrip("/") + "/"

    def is_on_agent(self, path):
        return False

    def listdir(self, team_id, path, recursive=False):
        prefix = self._prefix(path)
        return sorted(
            {prefix + p[len(prefix) :].split("/")[0] for p in self.files if p.startswith(prefix)}
        )

    def exists(self, team_id, path):
        return path in self.files

    def dir_exists(self, team_id, path):
        return any(p.startswith(self._prefix(path)) for p in self.files)

    def get_directory_size(self, team_id, path):
        return sum(len(v) for p, v in self.files.items() if p.startswith(self._prefix(path)))

    def download_directory(self, team_id, remote_path, local_save_path, progress_cb=None):
        prefix = self._prefix(remote_path)
        for p, data in self.files.items():
            if p.startswith(prefix):
                dst = os.path.join(local_save_path, p[len(prefix) :])
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "wb") as fh:
                    fh.write(data)

    def get_info_by_path(self, team_id, path):
        return SimpleNamespace(sizeb=len(self.files[path]))

    def download(self, team_id, remote_path, local_save_path, cache=None, progress_cb=None):
        os.makedirs(os.path.dirname(local_save_path), exist_ok=True)
        with open(local_save_path, "wb") as fh:
            fh.write(self.files[remote_path])

    def remove(self, team_id, path):
        self.removed.append(path)


class FakeApi:
    def __init__(self, files):
        self.file = FakeFileApi(files)
        self.projects = {}  # id -> name
        self.datasets = {}  # id -> {"project": id, "name": str}
        self.images = {}  # id -> {"dataset": id, "name": str, "meta": dict}
        self.anns = {}  # image id -> sly.Annotation
        self.metas = {}  # project id -> meta json
        self.grouping = {}
        self.errors = []
        self.removed_datasets = []
        self.removed_projects = []
        self.project = SimpleNamespace(
            create=self._create_project,
            remove=self._remove_project,
            get_datasets_count=lambda pid: sum(
                1 for d in self.datasets.values() if d["project"] == pid
            ),
            update_meta=self._update_meta,
            images_grouping=lambda id, enable, tag_name: self.grouping.__setitem__(id, tag_name),
        )
        self.dataset = SimpleNamespace(create=self._create_dataset, remove=self._remove_dataset)
        self.image = SimpleNamespace(upload_paths=self._upload_paths)
        self.annotation = SimpleNamespace(upload_anns=self._upload_anns)
        self.task = SimpleNamespace(
            set_output_error=lambda task_id, title, description=None, **kw: self.errors.append(
                title
            ),
            set_output_project=lambda *a, **kw: None,
        )
        self.app = SimpleNamespace(
            workflow=SimpleNamespace(add_output_project=lambda *a, **kw: None)
        )

    def _create_project(self, workspace_id, name, change_name_if_conflict=False, **kw):
        pid = 100 + len(self.projects) + len(self.removed_projects)
        self.projects[pid] = name
        return SimpleNamespace(id=pid, name=name)

    def _remove_project(self, id):
        self.projects.pop(id)
        self.removed_projects.append(id)

    def _create_dataset(self, project_id, name, change_name_if_conflict=False, **kw):
        did = 1000 + len(self.datasets) + len(self.removed_datasets)
        self.datasets[did] = {"project": project_id, "name": name}
        return SimpleNamespace(id=did, name=name)

    def _remove_dataset(self, id):
        self.datasets.pop(id)
        self.removed_datasets.append(id)
        for iid in [i for i, im in self.images.items() if im["dataset"] == id]:
            self.images.pop(iid)

    def _update_meta(self, id, meta):
        self.metas[id] = meta

    def _upload_paths(self, dataset_id, names, paths, metas=None, **kw):
        assert len(names) == len(paths)
        infos = []
        for i, (name, path) in enumerate(zip(names, paths)):
            assert os.path.isfile(path), path
            iid = 5000 + len(self.images)
            import nrrd

            self.images[iid] = {
                "dataset": dataset_id,
                "name": name,
                "meta": (metas or [{}] * len(names))[i],
                "pixels": nrrd.read(path)[0],
            }
            infos.append(SimpleNamespace(id=iid, name=name))
        return infos

    def _upload_anns(self, img_ids, anns, **kw):
        # the SDK zips ids with annotations; a length mismatch is a bug in the caller
        assert len(img_ids) == len(anns), (len(img_ids), len(anns))
        for iid, ann in zip(img_ids, anns):
            self.anns[iid] = ann

    # helpers for assertions
    def image_names(self, dataset_name=None):
        return sorted(
            im["name"]
            for im in self.images.values()
            if dataset_name is None or self.datasets[im["dataset"]]["name"] == dataset_name
        )

    def pixels_by_name(self, name):
        (im,) = [im for im in self.images.values() if im["name"] == name]
        return im["pixels"]

    def ann_by_name(self, name):
        (iid,) = [i for i, im in self.images.items() if im["name"] == name]
        return self.anns.get(iid)


# ---------------------------------------------------------------- DICOM fixtures


def _testdata(name):
    from pydicom.data import get_testdata_file

    return get_testdata_file(name)


def dicom_bytes(kind="ct", corrupt=False, **attrs):
    """A real DICOM file. kind: ct (128x128), mr (64x64), multiframe (3 x 64x64)."""
    import pydicom

    ds = pydicom.dcmread(
        _testdata("MR_small.dcm" if kind in ("mr", "multiframe") else "CT_small.dcm")
    )
    if kind == "multiframe":
        frames = np.stack([ds.pixel_array + i for i in range(3)]).astype(ds.pixel_array.dtype)
        ds.NumberOfFrames = 3
        ds.PixelData = frames.tobytes()
    for key, value in attrs.items():
        setattr(ds, key, value)
    if corrupt:
        ds.PixelData = b"\x00\x01"  # header readable, pixel data unusable
    buf = io.BytesIO()
    ds.save_as(buf)
    return buf.getvalue()


def make_tar(members):
    """members: {arcname: bytes} -> tar bytes (arcnames are taken verbatim, '..' included)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


# ---------------------------------------------------------------- Team Files layouts

ROOT = "/studies/cardio"


def folder_files(datasets, root=ROOT):
    """{dataset_name: {file_name: bytes}} -> Team Files dict."""
    return {
        f"{root}/{ds}/{name}": data
        for ds, items in datasets.items()
        for name, data in items.items()
    }


def sly_project(anns, images, tag_name="note"):
    """Supervisely-format project with DICOM images. anns: {ann_file_name: tag value}."""
    meta = sly.ProjectMeta(tag_metas=[sly.TagMeta(tag_name, sly.TagValueType.ANY_STRING)])
    files = {f"{ROOT}/meta.json": json.dumps(meta.to_json()).encode()}
    for name, data in images.items():
        files[f"{ROOT}/ds1/img/{name}"] = data
    for ann_name, value in anns.items():
        ann = sly.Annotation((128, 128)).add_tag(sly.Tag(meta.get_tag_meta(tag_name), value))
        files[f"{ROOT}/ds1/ann/{ann_name}"] = json.dumps(ann.to_json()).encode()
    return files


def note(api, image_name):
    ann = api.ann_by_name(image_name)
    tag = ann.img_tags.get("note") if ann is not None else None
    return tag.value if tag is not None else None


# ---------------------------------------------------------------- app runner


@pytest.fixture
def run_app(tmp_path, monkeypatch):
    """run_app(files, folder=..., file=..., **state) -> (api, g, error).

    Imports the app with the given Team Files content and modal state and runs the
    import callback. `error` is the exception the callback raised (None on success).
    """
    import supervisely as sly
    import supervisely.app.v1.app_service as app_service

    def _run(
        files,
        folder=None,
        file=None,
        tag_mode="prepared",
        group_tag="StudyInstanceUID",
        add_tags="Do not add tags",
        dcm_tags='{"tags": ["Modality", "Manufacturer"]}',
        with_anns=False,
        hide_distutils=False,
    ):
        api = FakeApi(files)
        data_dir = tmp_path / "data"
        env = {
            "ENV": "production",
            "TASK_ID": "1",
            "context.teamId": "8",
            "context.workspaceId": "9",
            "SLY_APP_DATA_DIR": str(data_dir),
            "modal.state.tagMode": tag_mode,
            "modal.state.predefinedGroupTag": group_tag,
            "modal.state.manualGroupTag": group_tag,
            "modal.state.addTagsFromDcm": add_tags,
            "modal.state.dcmTags": dcm_tags,
            "modal.state.withAnns": "true" if with_anns else "false",
        }
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        for k, v in (("modal.state.slyFolder", folder), ("modal.state.slyFile", file)):
            if v is None:
                monkeypatch.delenv(k, raising=False)
            else:
                monkeypatch.setenv(k, v)
        if hide_distutils:
            monkeypatch.setitem(sys.modules, "distutils", None)
            monkeypatch.setitem(sys.modules, "distutils.util", None)
        monkeypatch.setattr(app_service, "AppService", FakeAppService)
        monkeypatch.setattr(sly.Api, "from_env", classmethod(lambda cls, *a, **k: api))
        monkeypatch.syspath_prepend(SRC)
        for mod in APP_MODULES:
            sys.modules.pop(mod, None)
        main = importlib.import_module("main")
        g = importlib.import_module("sly_globals")
        error = None
        try:
            main.import_dicom_studies(api, 1, {}, {}, sly.logger)
        except Exception as e:  # noqa: BLE001 - the test inspects it
            error = e
        return api, g, error

    yield _run
    for mod in APP_MODULES:
        sys.modules.pop(mod, None)
