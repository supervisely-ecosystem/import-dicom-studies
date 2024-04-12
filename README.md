<div align="center" markdown>
<img src="https://user-images.githubusercontent.com/48245050/182844433-c620c1fc-76f4-4480-8461-984b8b713058.jpg"/>

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
[![views](https://app.supervise.ly/img/badges/views/supervisely-ecosystem/import-dicom-studies.png)](https://supervise.ly)
[![runs](https://app.supervise.ly/img/badges/runs/supervisely-ecosystem/import-dicom-studies.png)](https://supervise.ly)

</div>

# Overview

Converts `DICOM` data to `nrrd` format and creates a new project with tagged images in the current `Team` -> `Workspace`.

Application key points:

- Select grouping tag from prepared tags or manually input tag name
- Tag name must match DICOM metadata key name
- Tag value is defined by metadata from `DICOM` file
- Manually inputted tag must match name of the `DICOM` metadata key e.g `AcquisitionDate`
- Add multiple DICOM metadata keys as tags using modal window
- `Images Grouping` option will be turned on by default in the created project
- Images will be grouped by selected tag's value
- Supports `DICOM` files without extention e.g. `1.2.3.4.5.6.10.10.100.110.10000.00000000000000.0000`
- Converts `DICOM` to `nrrd` format
- Result project can be exported only with [Export to Supervisely format](https://ecosystem.supervise.ly/apps/export-to-supervisely-format) app

Learn more how to deal with images groups in [Import images groups](https://ecosystem.supervise.ly/apps/import-images-groups) readme

🏷️ Starting from version `v1.2.0` application support annotations in supervisely format if the corresponding option is selected in modal window during application launch. Learn more about Supervisely project structure [here](https://developer.supervise.ly/api-references/supervisely-annotation-json-format/project-structure).

🏋️ Starting from version `v1.1.0` application supports import from special directory on your local computer. It is made for Enterprise Edition customers who need to upload tens or even hundreds of gigabytes of data without using drag-ang-drop mechanism:

1. Run agent on your computer where data is stored. Watch [how-to video](https://youtu.be/aO7Zc4kTrVg).
2. Copy your data to special folder on your computer that was created by agent. Agent mounts this directory to your Supervisely instance and it becomes accessible in Team Files. Learn more [in documentation](https://docs.supervise.ly/customization/agents/agent-storage). Watch [how-to video](https://youtu.be/63Kc8Xq9H0U).
3. Go to `Team Files` -> `Supervisely Agent` and find your folder there.
4. Right click to open context menu and start app. Now app will upload data directly from your computer to the platform.

# Preparation

**Archive** `zip`, `tar`, `tar.xz`, `tar.gz`

Archive structure:

1. Without annotations (by default)<br>
ℹ️ You can download the archive with data example [here](https://github.com/supervisely-ecosystem/import-dicom-studies/files/12557627/my_dicom_studies_project.zip).

```text
  📦my_project.zip
   ┗ 📂cardio_project
      ┗ 📂research_1
         ┣ 📜IMG-0001-00001.dcm
         ┣ 📜IMG-0001-00002.dcm
         ┣ 📜IMG-0001-00003.dcm
         ┣ 📜IMG-0001-00004.dcm
         ┗ 📜1.2.3.4.5.6.10.10.100.110.10000.00000000000000.0000
```

2. With annotations (supervisely format). [Learn more here.](https://docs.supervise.ly/data-organization/00_ann_format_navi)

```text
  📦my_project.zip
   ┗ 📂cardio_project
      ┣ 📜meta.json
      ┗ 📂research_1
         ┣ 📂ann
         ┃  ┣ 📜IMG-0001-00001.json
         ┃  ┣ 📜IMG-0001-00002.json
         ┃  ┣ 📜IMG-0001-00003.json
         ┃  ┣ 📜IMG-0001-00004.json
         ┃  ┗ 📜1.2.3.4.5.6.10.10.100.110.10000.00000000000000.0000.json
         ┗ 📂img
            ┣ 📜IMG-0001-00001.dcm
            ┣ 📜IMG-0001-00002.dcm
            ┣ 📜IMG-0001-00003.dcm
            ┣ 📜IMG-0001-00004.dcm
            ┗ 📜1.2.3.4.5.6.10.10.100.110.10000.00000000000000.0000
```

**Folder**

Folder structure:

1. Without annotations (by default)

```text
  📂cardio_project
   ┗ 📂research_1
      ┣ 📜IMG-0001-00001.dcm
      ┣ 📜IMG-0001-00002.dcm
      ┣ 📜IMG-0001-00003.dcm
      ┣ 📜IMG-0001-00004.dcm
      ┗ 📜1.2.3.4.5.6.10.10.100.110.10000.00000000000000.0000
```

Structure explained:

1. Archive must contain only 1 project directory. Name of the project directory will be used for created supervisely project.
2. Inside project directory must be dataset directory. Name of the dataset directory will be used for created dataset.
3. Files will be grouped using `DICOM` metadata. If `DICOM` file doesn't contain inputted metadata field, it will be uploaded without tag.

Example of created project using the example below and tag `AcquisitionDate` as user input:

- Project name: cardio_project
- Dataset name: research_1
- Images:

|                        Image name                        |              Tag              |
| :------------------------------------------------------: | :---------------------------: |
|                   IMG-0001-00001.nrrd                    | `AcquisitionDate`: `20200928` |
|                   IMG-0001-00002.nrrd                    | `AcquisitionDate`: `20200928` |
|                   IMG-0001-00003.nrrd                    | `AcquisitionDate`: `20200928` |
|                   IMG-0001-00004.nrrd                    | `AcquisitionDate`: `20200928` |
| 1.2.3.4.5.6.10.10.100.110.10000.00000000000000.0000.nrrd |

2. With annotations (supervisely format). [Learn more here.](https://docs.supervise.ly/data-organization/00_ann_format_navi)

```text
  📂cardio_project
   ┣ 📜meta.json
   ┗ 📂research_1
      ┣ 📂ann
      ┃  ┣ 📜IMG-0001-00001.json
      ┃  ┣ 📜IMG-0001-00002.json
      ┃  ┣ 📜IMG-0001-00003.json
      ┃  ┣ 📜IMG-0001-00004.json
      ┃  ┗ 📜1.2.3.4.5.6.10.10.100.110.10000.00000000000000.0000.json
      ┗ 📂img
         ┣ 📜IMG-0001-00001.dcm
         ┣ 📜IMG-0001-00002.dcm
         ┣ 📜IMG-0001-00003.dcm
         ┣ 📜IMG-0001-00004.dcm
         ┗ 📜1.2.3.4.5.6.10.10.100.110.10000.00000000000000.0000
```

Structure explained:

1. Archive must contain only 1 project directory. Name of the project directory will be used for created supervisely project.
2. Inside project directory must be `meta.json` file and dataset directory. Name of the dataset directory will be used for created dataset. Inside dataset directory must be `ann` and `img` subdirectories with `.json` and `DICOM` files. Learn more about [Supervisely Format](https://docs.supervise.ly/data-organization/00_ann_format_navi).
3. Files will be grouped using `DICOM` metadata. If `DICOM` file doesn't contain inputted metadata field, it will be uploaded without tag.

Example of created project using the example below and tag `AcquisitionDate` as user input:

- Project name: cardio_project
- Dataset name: research_1
- Images:

|                        Image name                        |              Tag              |
| :------------------------------------------------------: | :---------------------------: |
|                   IMG-0001-00001.nrrd                    | `AcquisitionDate`: `20200928` |
|                   IMG-0001-00002.nrrd                    | `AcquisitionDate`: `20200928` |
|                   IMG-0001-00003.nrrd                    | `AcquisitionDate`: `20200928` |
|                   IMG-0001-00004.nrrd                    | `AcquisitionDate`: `20200928` |
| 1.2.3.4.5.6.10.10.100.110.10000.00000000000000.0000.nrrd |

- Annotations:

|                     Annotation name                      |
| :------------------------------------------------------: |
|                   IMG-0001-00001.json                    |
|                   IMG-0001-00002.json                    |
|                   IMG-0001-00003.json                    |
|                   IMG-0001-00004.json                    |
| 1.2.3.4.5.6.10.10.100.110.10000.00000000000000.0000.json |

Prepare project and drag and drop it to `Team Files`.

<img src="https://github.com/supervisely-ecosystem/import-dicom-studies/releases/download/v0.0.1/drag-and-drop-min.gif"/>

# How To Run

**Step 1.** Add [Import DICOM studies](https://ecosystem.supervise.ly/apps/import-dicom-studies) app to your team from Ecosystem

<img data-key="sly-module-link" data-module-slug="supervisely-ecosystem/import-dicom-studies" src="https://i.imgur.com/hEeXmrM.png" width="70%"/>

**Step 2.** Run app from the context menu of your data on Team Files page:
<img src="https://i.imgur.com/OQh3oa3.png"/>

**Step 3.** Define group tag in modal window by selecting one of the predefined DICOM metadata keys, or type metadata key name manually. You can add more metadata keys as tags by adding them to editor in modal window. Specify if you need annotations (supervisely format).

<div align="center" markdown>
  <img src="https://user-images.githubusercontent.com/78355358/231738590-fdfd791a-3a50-47d9-92d6-54d2ad3660ae.png" width="50%"/>
</div>

**Step 4.** Once app is started, new task will appear in workspace tasks. Wait for the app to process your data.

# How To Use

**Step 1.** Open imported project.

<img src="https://i.imgur.com/Z8ulu5y.png"/>

**Step 2.** Open dataset using new image annotator.

<img src="https://i.imgur.com/kO8f0bL.png"/>
