<div align="center" markdown>
<img src="https://i.imgur.com/o8bm60f.png"/>

# Import DICOM Studies

<p align="center">
  <a href="#Overview">Overview</a> •
  <a href="#Preparation">Preparation</a> •
  <a href="#How-To-Run">How To Run</a> •
  <a href="#How-To-Use">How To Use</a>
</p>
  
[![](https://img.shields.io/badge/supervisely-ecosystem-brightgreen)](https://ecosystem.supervise.ly/apps/supervisely-ecosystem/import-dicom-studies)
[![](https://img.shields.io/badge/slack-chat-green.svg?logo=slack)](https://supervise.ly/slack)
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/supervisely-ecosystem/import-dicom-studies)
[![views](https://app.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/import-dicom-studies&counter=views&label=views)](https://supervise.ly)
[![used by teams](https://app.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/import-dicom-studies&counter=downloads&label=used%20by%20teams)](https://supervise.ly)
[![runs](https://app.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/import-dicom-studies&counter=runs&label=runs&123)](https://supervise.ly)

</div>

# Overview
Converts `DICOM` data to `nrrd` format and creates a new project with tagged images in the current `Team` -> `Workspace`.

Application key points:
* Select grouping tag from prepared tags or manually input tag name
* Tag name must match DICOM metadata field name
* Tag value is defined by metadata from `DICOM` file
* Manually inputted tag must match name of the `DICOM` metadata field e.g `AcquisitionDate`
* `Images Grouping` option will be turned on by default in the created project
* Images will be grouped by selected tag's value
* Supports `DICOM` files without extention e.g. `1.2.3.4.5.6.10.10.100.110.10000.00000000000000.0000`
* Converts `DICOM` to `nrrd` format

# Preparation

**Archive** `zip`, `tar`, `tar.xz`, `tar.gz`

Archive structure:

```text
.
└── my_project.zip
    └── cardio 
        └── research_1 
            ├── IMG-0001-00001.dcm
            ├── IMG-0001-00002.dcm
            ├── IMG-0001-00003.dcm
            ├── IMG-0001-00004.dcm
            └── 1.2.3.4.5.6.10.10.100.110.10000.00000000000000.0000
```

**Folder**

Folder structure:

```text
.
└── cardio 
    └── research_1 
        ├── IMG-0001-00001.dcm
        ├── IMG-0001-00002.dcm
        ├── IMG-0001-00003.dcm
        ├── IMG-0001-00004.dcm
        └── 1.2.3.4.5.6.10.10.100.110.10000.00000000000000.0000
```

Structure explained:

1. Archive must contain only 1 project directory. Name of the project directory will be used for created supervisely project.
2. Inside project directory must be dataset directory. Name of the dataset directory will be used for created dataset. 
3. Files will be grouped using `DICOM` metadata. If `DICOM` file doesn't contain inputted metadata field, it will be uploaded without tag.

Example of created project using the example below and tag `car id` as user input:
* Project name: cardio
* Dataset name: research_1
* Images:

Image name  |  Tag
:-------------------------:|:-----------------------------------:
IMG-0001-00001.nrrd  | `AcquisitionDate`: `20200928`
IMG-0001-00002.nrrd    | `AcquisitionDate`: `20200928`
IMG-0001-00003.nrrd  | `AcquisitionDate`: `20200928`
IMG-0001-00004.nrrd    | `AcquisitionDate`: `20200928`
1.2.3.4.5.6.10.10.100.110.10000.00000000000000.0000.nrrd  |


Prepare project and drag and drop it to `Team Files`.

<img src="https://github.com/supervisely-ecosystem/import-dicom-studies/releases/download/v0.0.1/drag-and-drop.gif?raw=true"/>

# How To Run 
**Step 1.** Add [Import DICOM studies](https://ecosystem.supervise.ly/apps/import-dicom-studies) app to your team from Ecosystem

<img data-key="sly-module-link" data-module-slug="supervisely-ecosystem/import-dicom-studies" src="https://i.imgur.com/hEeXmrM.png" width="70%"/>


**Step 2.** Run app from the context menu of your data on Team Files page:
<img src="https://i.imgur.com/OQh3oa3.png"/>


**Step 3.** Define group tag in modal window by selecting one of the prepared DICOM metadata fields, or type metadata field name manually.

<img src="https://i.imgur.com/jLbh2ot.png" width="70%"/>


**Step 4.** Once app is started, new task will appear in workspace tasks. Wait for the app to process your data.

# How To Use

**Step 1.** Open imported project.

<img src="https://i.imgur.com/Z8ulu5y.png"/>

**Step 2.** Open dataset using new image annotator.

<img src="https://i.imgur.com/kO8f0bL.png"/>
