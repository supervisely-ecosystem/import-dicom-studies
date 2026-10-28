# import-dicom-studies: fixes 2026-10 (branch `ecosystem-fixes-2026-10`)

Base: `origin/master` @ 69f05d1 (v1.3.6, `supervisely/import-export:6.74.34`). Lifecycle `legacy`, headless
AppService (v1) app, ~750 lines: targeted fixes + image move, no rewrite. `config.json` `name`,
`context_menu`, modal state keys and defaults are unchanged.

## Behaviour contract

- **Started from** Team Files or agent storage: `files_folder`, `files_file`, `agent_folder`, `agent_file`
  (`modal.state.slyFolder` / `modal.state.slyFile`).
- **Input**
  - a folder with one sub-folder per dataset (any depth: every folder holding DICOM files becomes a dataset named
    after the folder; DICOMs directly in the selected folder make one dataset);
  - an archive (zip, tar, tar.gz, tar.xz) with exactly one project folder inside;
  - with "Add annotations": Supervisely format — `meta.json` + `<dataset>/img/*` (DICOM) + `<dataset>/ann/*.json`
    (`<name>.json` or `<name without extension>.json`).
  - Selecting a single `.dcm` imports its folder; selecting `meta.json` imports its project.
- **Options** (`modal.state.*`)
  - `tagMode` `prepared|manual`, `predefinedGroupTag` (StudyInstanceUID / SeriesInstanceUID),
    `manualGroupTag`: the DICOM key whose value becomes the grouping tag;
  - `addTagsFromDcm`: `All tags` | `Only specified tags` (keys from `dcmTags` JSON `{"tags": [...]}`) |
    `Do not add tags`;
  - `withAnns`: read Supervisely-format annotations.
- **Output**: a new images project named after the project folder (renamed on conflict) in the task's workspace;
  one `.nrrd` image per single-frame file (`<file name>.nrrd`) and per frame (`<n>_<file name>.nrrd`); the grouping
  tag on every image, images grouping enabled on it; image meta = DICOM elements (unless "Do not add tags");
  workflow output = the project. Nothing in Team Files is modified or removed (the app has no "remove source").

## Fixed (one commit each; tests offline, `python -m pytest tests`)

Old code = `origin/master` on its own stack (Python 3.8, pydicom 2.4.4, scikit-image), `APP_SRC=<old src>`.

| # | Commit | Problem | Tests old → new |
|---|---|---|---|
| 0 | 49e1fb0 | No tests. Harness: real `sly_globals` with fake `AppService`/`Api`, real DICOM files | 7/7 regression tests pass on old |
| 1 | a282da9 | `distutils.strtobool` (gone in 3.12) and `pydicom.read_file` (gone in pydicom 3): crash at import / "No DICOM data found" on the hardened image | 0/2 → 2/2 |
| 2 | 1e74252 | Single-frame images went through `sly.image.rotate(270)`+`fliplr`: one black column (and row for square images) added, 128×128 stored as 129×129; needed scikit-image | 0/1 → 1/1 |
| 3 | 69b8a4b | **Security**: archives unpacked with bare `shutil.unpack_archive` (no tar filter on Python 3.8): `../` members and symlink escapes wrote outside the data dir (audit 3.1 #1) | 1/3 → 3/3 |
| 4 | 11f4fd3 | **Wrong success / lost output**: a 50-file batch with nothing convertible removed the whole dataset incl. earlier batches; conversion failures only logged; other `FileNotFoundError`s swallowed | 0/2 → 2/2 |
| 5 | e9b05ee | Annotations paired by sorting two lists and zipping: one missing `.json` shifted all later annotations to the wrong images and dropped the last image; multi-frame + annotation crashed in `upload_anns` | 0/3 → 3/3 |
| 6 | a294633 | "Only specified tags" added no tags since May 2024 (aa14a36) | 0/1 → 1/1 |
| 7 | 4e825dd | Two consecutive Supervisely meta tags clashing with import tags: list mutated while iterating → "non-unique values" after images were uploaded | (in #8 file) fails → passes |
| 8 | 6221487 | Selecting `meta.json` compared the full path with `"meta.json"` → "file is not an archive" | 2/4 → 4/4 (file) |
| 9 | 918ce28 | Image move (below) + codec tests | codecs 3/3 → 3/3 |
| 10 | fe2571b | PR pylint workflow on Python 3.8 cannot install the new pinned codecs (need ≥ 3.10) → 3.14 | — |

Whole suite: old code 13/26, new code **26/26** on Python 3.8 + pydicom 2, Python 3.14 +
pydicom 3, and inside the image built from the template.

## Intentional behaviour changes

- Files that fail conversion now make the task **fail at the end** (after the project and workflow output are
  registered) with the number and the first 10 file names; the imported images stay. Before: warning only, task
  succeeded. Non-DICOM files next to DICOMs are still only warned about.
- An archive with any unsafe member (absolute path, `..`, link out of the folder, device) is refused as a whole.
- Single-frame images have their true size and no black border (128×128 instead of 129×129). Orientation is
  unchanged. Annotations made for the old, 1-px-larger images are 1 px off on re-import.
- Images without an annotation file in Supervisely format are imported with DICOM tags only (warning); before they
  received the next file's annotation. Multi-frame files get the annotation's image tags on every frame; a
  multi-frame file whose annotation has **labels** is reported as failed (labels cannot be assigned to frames).
- "Only specified tags" adds the listed keys again (matched by DICOM keyword, e.g. `ManufacturerModelName`, or
  element name); tag names are element names, as in "All tags".

## Image

`supervisely/import-export:6.74.34` (sdk_legacy, Python 3.8) → **`supervisely/import-dicom-studies:6.74.34`**,
per-app image from `workflows/docker/hardened/Dockerfile.tmpl` on `supervisely/base-py-sdk-hardened:6.74.34`
(Python 3.14.7, pydicom 3.0.2). `dev_requirements.txt`: `supervisely==6.74.34`, `pylibjpeg==2.1.0`,
`pylibjpeg-libjpeg==2.4.0`.

- Not the bare hardened image: it cannot decode JPEG Lossless (process 14) or JPEG-LS pixel data, which
  import-export could (gdcm/pylibjpeg). The two pylibjpeg packages restore that (checked on pydicom test files:
  RLE, JPEG 2000, JPEG-LS, JPEG Lossless OK; 12-bit JPEG Extended fails on both old and new). Note: pylibjpeg-libjpeg
  is GPLv3, as in import-export.
- `release.yml` and `release_branch.yml` gained a `build-image` job (`build_image_from_template.yml`,
  `cve_checks: false` like export-to-coco) that the release job `needs`; it builds the tag only if it is not on
  Docker Hub, so the first branch push builds `supervisely/import-dicom-studies:6.74.34`.
- SDK stays 6.74.34 (`instance_version` 6.17.22 → [6.74.29, 6.74.35)).
- Verified: image built locally from the template (not pushed, 2.0 GB); full suite 26/26 inside it.

## Found, not fixed

- Selecting a single `.dcm` file imports the whole folder (documented "switch to folder mode"); harmless here
  because nothing is removed.
- RGB single-frame DICOMs (`SamplesPerPixel=3`, no `NumberOfFrames`) are not supported; they now count as failed
  files instead of being silently skipped.
- Images grouping is enabled on the grouping tag even when no file had that key (the tag meta is then missing).
- `local.env` points to another team's agent folder; left as is (no secrets in it).
- Not a rewrite: AppService v1, module globals and `sly_globals` stay (works on the hardened base, as in
  export-videos-project-in-supervisely-format).

## Dev-check plan (do not run in this phase)

Fixtures: `/private/tmp/claude-501/-Users-vorozhkog-workapps/e813a6a6-06b5-41f3-a039-0dd120111c3a/scratchpad/batch2_fixtures/import-dicom-studies/`
(generated by `.../scratchpad/scripts/make_dicom_fixtures.py`). Upload to team 1 Team Files under
`/agents-sandbox/chk-imp/import-dicom-studies/` keeping the layout. Each case: new branch, then the same command
without `--version ... --branch` (published v1.3.6) for comparison. `P=/agents-sandbox/chk-imp/import-dicom-studies`.

| Case | Command | Expected (branch) | Published v1.3.6 |
|---|---|---|---|
| clean folder | `uv run ecosystem-fleet/fleet.py run import-dicom-studies --workspace 733 --folder $P/dcm_clean/cardio/ --version ecosystem-fixes-2026-10 --branch` | success; project "cardio", ds1 (a, b), ds2 (c, jpegls), 4 images; a.dcm.nrrd 128×128; StudyInstanceUID tags; grouping on | same images, a.dcm.nrrd 129×129 |
| existing series | `... --folder /agents-sandbox/chk-imp/import-dicom-volumes/dcm1_pub/175543hrt/data/ --state tagMode=prepared --state predefinedGroupTag=SeriesInstanceUID ...` | success; datasets series1 (12), series3 (10); series2 (8 files without extension) imported only if they carry a DICOM preamble, else skipped with a warning; source untouched | same datasets/counts, images 1 px larger |
| corrupt file | `... --folder $P/dcm_mixed/cardio/ ...` | task **error** "1 DICOM file(s) ... broken.dcm"; project kept with ds1 a, b, 3 frames of mf; ds2 c | success, same images, no error |
| only specified tags | `... --folder $P/dcm_clean/cardio/ --state addTagsFromDcm="Only specified tags" --state dcmTags='{"tags": ["Modality", "Manufacturer"]}' ...` | c.dcm.nrrd has tags Modality=CT, Manufacturer=ACME | only the grouping tag |
| Supervisely format | `... --folder $P/dcm_sly/cardio/ --state withAnns=true ...` | a→note A, b→no note, c→note C | b gets C, c missing |
| meta.json selected | `... --file $P/dcm_sly/cardio/meta.json --state withAnns=true ...` | same as previous case | error "file is not an archive" |
| tar archive | `... --file $P/dcm_archives/ok.tar ...` | success; ds1 a, b | same (+1 px) |
| unsafe tar | `... --file $P/dcm_archives/evil.tar ...` | task error "contains unsafe paths", no project | imports a.dcm, writes `/tmp/escape.txt` in the container |

Check after each run: task status/output, project tree and image sizes (`api.image.get_list`), tags of one image.
Source folders must be unchanged in every case.

## Branch image (test tag)

On this branch `config.json` uses `supervisely/import-dicom-studies:test-5a1eb1e8`. `release_branch.yml` follows
`workflows/templates/build_release_branch.yml`: on push it builds that tag, named by the sha256 of
`dev_requirements.txt`, and only if the tag is not on Docker Hub yet. Dev agents pull images "if not present", so
every dependency change gets a new tag. **Before merging, set `docker_image` back to `supervisely/import-dicom-studies:6.74.34`**; `release.yml`
builds that tag on the version release.
