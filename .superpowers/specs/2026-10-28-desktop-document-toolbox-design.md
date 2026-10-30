# Desktop document toolbox design

## Purpose

Define the first version of a desktop application for non-technical users who need to convert local documents to Markdown or anonymize Office documents. The application targets macOS and Windows. Linux is not a priority.

The application has two independent workflows. It must work without a command line and must not send document content to remote services.

## Users and goals

Users should be able to:

- select or drop one file or a batch of files into a clear graphical workflow;
- convert supported local files to Markdown;
- review detected personal data and create anonymized copies of supported Office files;
- understand progress, errors, output locations, language, theme, and optional OCR requirements without technical knowledge;
- continue using installed functionality while offline.

## Product scope

### Markdown conversion

- Use Microsoft's MarkItDown for local file conversion.
- Offer the local file formats supported by the enabled MarkItDown converters. The conversion workflow has its own format list, independent from anonymization.
- Do not add converters for formats MarkItDown does not support. OpenDocument formats, including ODT, are out of scope and must be identified as unsupported in the README.
- Do not expose URL, web-search, cloud, or other remote-input integrations. Conversion operates on local files only.
- Include local formats exposed by MarkItDown, such as TXT, Markdown, JSON/JSONL, CSV, HTML, PDF, DOCX, XLS/XLSX, PPTX, and EPUB where the pinned library version and installed optional dependencies support them. Verify the full exact extension list against the selected MarkItDown version before publishing it in the UI or README.
- Unsupported, encrypted, corrupt, or unreadable files receive a clear per-file error. A failure on one batch item must not prevent other files from completing.

### Document anonymization

- Initial input formats are DOCX, XLSX, and PPTX. This list is independent from the conversion list.
- Use Presidio Analyzer and Anonymizer locally, configured for French and English.
- Show detected entities for review before writing output. Users can adjust which detections are anonymized.
- Provide Replace, Mask, Redact, Hash, and Encrypt. Recommend Replace in the UI, but allow users to select another operator. Explain each choice in plain language.
- Create a separate output copy and never overwrite the source. Preserve formatting as much as possible. Clearly report any content that could not be processed or preserved.
- Handle batch jobs per document, with review and status available for each item.
- Do not use cloud-based surrogate generation or remote recognition.

### OCR

- OCR is optional and local. Conversion without OCR remains available.
- Offer a lightweight local OCR model for download during installation. Before download, show the selected model's minimum OS, memory, storage, and other applicable requirements. Determine these values from the actual model and runtime rather than hard-coding estimates in advance.
- Allow users to configure another local OCR engine, or leave OCR disabled.
- OCR, its model, and all document processing must work offline after the required local components are installed.

### Desktop experience

- Use Tauri 2 with React and TypeScript.
- Package the Python processing engine as an internal background component for MarkItDown and Presidio. Users interact only with the graphical app and never need Python or a terminal.
- Keep development and test builds available locally on macOS and Windows, with setup and build instructions in the README. Local builds must not require production signing secrets; release signing and publication happen in CI/CD.
- Keep a shared application shell and separate feature modules for conversion and anonymization. Each module owns its format declarations, workflow state, and processing adapter.
- Support single-file and batch workflows, drag and drop, native file selection, visible progress, understandable error recovery, and output location selection.
- Provide French and English UI translations. Detect the OS language on first launch; allow a persistent manual override.
- Provide System, Light, and Dark appearance. Follow the OS appearance by default and remember a manual override.
- Build and release the application through CI/CD, publishing installers and update artifacts to GitHub Releases. Drive versions with Changesets rather than by hand: a change that users can see carries a changeset, merging one to the main branch opens a version pull request, and merging that pull request bumps the version, writes the changelog, tags the release and triggers the signed build. Keep one file as the version's source of truth so a bundle can never be labelled with a version that was not released. Also support local macOS and Windows builds for development and pre-release checks without production signing secrets. Sign the macOS application in CI/CD. Windows application packages are unsigned initially; explain any OS publisher warning and link to the official GitHub Release. Sign updater artifacts for verification on both platforms. Network access is allowed for update checks/downloads and optional model download only; no document content or personal-data detections are sent.
- Explain offline availability and any connection needed for updates or model downloads without interrupting local jobs.

## Architecture

### Application shell

The Tauri shell owns the desktop window, native file access, application settings, update flow, and the boundary to the processing engine. The React/TypeScript frontend owns navigation, workflow views, progress, review screens, language/theme settings, and user-facing messages.

### Feature modules

- **Conversion module:** declares the enabled local MarkItDown converters and their optional dependencies; accepts local files and produces Markdown outputs.
- **Anonymization module:** accepts DOCX/XLSX/PPTX; coordinates extraction, Presidio analysis, user review, applying selected operators, and writing a new copy.
- **OCR capability:** an optional local service used by conversion when installed and enabled. It must not be a prerequisite for ordinary conversion.

The frontend communicates with a narrow Tauri command/API boundary. The Tauri layer communicates with the packaged Python engine through a documented request/response protocol. Keep the Python process hidden from users and constrain its permissions to the selected input/output files and required local resources.

### Data flow

1. The user selects a workflow and local input files.
2. The UI validates extensions against that workflow's declared capabilities and explains unsupported files.
3. Tauri submits a job to the local Python engine. Progress and per-file results return to the UI.
4. Conversion writes Markdown output. Anonymization returns detections for review, then writes a separate copy after confirmation.
5. Temporary files are removed when no longer needed. Logs contain operational metadata only, never document text, detected personal data, or secrets.

### Failure handling

Show actionable, plain-language messages for unsupported formats, missing optional components, unreadable/password-protected/corrupt files, output permission problems, model download failures, and per-file batch errors. Never show raw tracebacks to users. Preserve original documents on every failure. A batch reports successful, failed, and skipped items separately.

## Accessibility and sustainability

- All core workflows and dialogs must be keyboard-operable and usable with assistive technologies.
- Use clear labels, focus order, visible focus, sufficient contrast, and status messages that do not rely on color alone.
- Keep interface language strings in translation resources.
- Keep OCR optional, install only the dependencies required by enabled formats, and avoid background processing when no job is running.
- Make the download size and minimum system requirements of optional models visible before installation.

## Verification strategy

- Unit-test each workflow's format declarations against the pinned library version and enabled dependencies.
- Test representative supported formats and unsupported ODT behavior.
- Test single-file and batch jobs, per-file failures, progress/result reporting, and preservation of source files.
- For anonymization, test French and English detections, each operator, review/selection behavior, and output formatting for DOCX, XLSX, and PPTX fixtures.
- Keep document processing local by construction rather than by an offline test. Assert that the pinned dependency closure contains no cloud or remote-service client, which is what makes processing local; a passing offline run would only show that no call happened on that run. Network access remains legitimate outside processing, for installation, update checks, and the optional OCR model download.
- Test language detection and manual override, system/light/dark theme selection, updater signature handling, and OCR prerequisite messaging.
- Verify packaged macOS and Windows builds. Confirm the Python engine and optional model can be installed and launched without opening a terminal.
- Manually check keyboard navigation and assistive-technology announcements in the main workflows.

## Decisions taken

- Desktop framework: Tauri 2.
- Frontend: React and TypeScript.
- Processing libraries: Microsoft MarkItDown for conversion and Presidio for anonymization.
- Processing is local. Documents are never sent to external services.
- The app remains usable offline after installation; update and model downloads require connectivity.
- Conversion and anonymization are distinct modular workflows with independent format support.
- ODT/OpenDocument support is excluded for now and documented as unsupported.
- Anonymization starts with DOCX, XLSX, and PPTX and outputs a copy, preserving formatting as much as possible.
- Anonymization supports Replace, Mask, Redact, Hash, and Encrypt; Replace is recommended.
- Users review detections before anonymized output is written.
- OCR is optional, local, downloadable during installation, and replaceable by a user-configured local engine.
- UI languages are French and English. The app detects the system language and supports a persistent override.
- Appearance follows the system by default and can be forced to Light or Dark.
- Developers can build and test locally on macOS and Windows without release-signing secrets. CI/CD builds and publishes installers and update artifacts to GitHub Releases. The macOS application is signed in CI/CD; Windows code signing is deferred initially. Updater artifacts are signed for verification on both platforms, and the GUI explains any Windows publisher warning.

## Open implementation decisions

- Pin MarkItDown and Presidio versions, then derive and test the exact local file format lists from those versions and selected extras.
- Select the lightweight OCR model/runtime and publish verified per-platform minimum requirements and download size.
- Choose the Python packaging/runtime approach and the precise Tauri-to-Python protocol.
- Define the CI/CD workflow, macOS signing/notarization details, GitHub Release assets, and updater feed configuration. Windows code signing is deferred; updater package signatures must still be verified on both platforms.
- Finalize anonymized-copy naming and default output-folder behavior.
