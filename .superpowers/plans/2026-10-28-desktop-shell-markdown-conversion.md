# Desktop shell and Markdown conversion implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a locally buildable macOS/Windows desktop application with a modular Tauri/React shell and a complete first workflow that converts supported local files to Markdown.

**Architecture:** Tauri 2 hosts a React/TypeScript interface and exposes a narrow set of application commands. A packaged Python worker uses MarkItDown and communicates through a fixed JSON-lines protocol. The conversion feature owns its format catalog, job state, and output handling. The shell owns settings, native dialogs, and module navigation.

**Tech Stack:** Tauri 2, React, TypeScript, Vite, pnpm, Rust, Python, uv, MarkItDown, pytest, Vitest, React Testing Library.

## Global constraints

- Target macOS and Windows; Linux is not a priority.
- Users need no terminal, Python installation, or command-line knowledge.
- Keep document processing local. Do not send document contents to remote services.
- Keep MarkItDown conversion and future Presidio anonymization as independent modules with independent format lists.
- Exclude OpenDocument formats, including ODT, and state this in the README.
- Support French and English UI, detect the system language on first launch, and persist a manual language override.
- Follow the system appearance by default; support persistent System, Light, and Dark choices.
- Support single-file and batch conversion, with per-file status and errors.
- Local output uses the selected destination folder and the input file's base name with a `.md` extension. If that output already exists, choose the next free numbered name; never overwrite an existing file or source.
- OCR is not part of this implementation slice. Conversion without OCR must remain usable; do not add a remote OCR or image-description service.
- Keep local builds free of production signing secrets. Release signing and GitHub publication belong to a later CI/CD plan.
- Preserve keyboard operation, visible focus, assistive-technology status announcements, and sufficient contrast. Never communicate state by color alone.
- Execute implementation on a feature branch, not `main`. Commit each completed task after its tests pass, using a concise English Conventional Commit message.

## Scope split

This is the first implementation slice: application shell plus MarkItDown conversion. It should build and run locally before release automation is added.

Create separate plans for the independent follow-on slices:

1. Presidio anonymization for DOCX, XLSX, and PPTX, including review and format-preserving output copies.
2. Optional local OCR model/runtime, custom local engine configuration, and system-requirement messaging.
3. macOS signing, Windows unsigned-package messaging, signed Tauri updater artifacts, and GitHub Actions/GitHub Releases.

Do not implement those follow-on slices as hidden scope in this plan.

## Proposed file structure

- `package.json`, `pnpm-lock.yaml`, `tsconfig.json`, `vite.config.ts`, `index.html`: frontend scripts and build configuration.
- `src/main.tsx`, `src/App.tsx`: application entry and shell composition.
- `src/app/`: settings, module navigation, locale dictionaries, theme handling, and shared UI state.
- `src/features/conversion/`: conversion view, format catalog display, file/job state, and output handling.
- `src-tauri/Cargo.toml`, `src-tauri/tauri.conf.json`, `src-tauri/capabilities/default.json`, `src-tauri/src/`: Tauri setup, narrow commands, file dialogs, and worker lifecycle.
- `python/pyproject.toml`, `python/uv.lock`, `python/src/document_worker/`: Python worker, MarkItDown adapter, format catalog, and JSON-lines protocol.
- `python/tests/`: worker protocol, format catalog, and conversion tests.
- `src/**/*.test.tsx`: frontend behavior and accessibility-facing state tests.
- `README.md`: developer prerequisites, local run/build commands, supported formats, and explicit ODT exclusion.

## Tasks

### Task 1: Scaffold the desktop shell and local frontend checks

**Files:**
- Create: `package.json`, `pnpm-lock.yaml`, `tsconfig.json`, `vite.config.ts`, `index.html`
- Create: `src/main.tsx`, `src/App.tsx`, `src/app/AppShell.tsx`
- Create: `src/app/i18n.ts`, `src/app/locales/en.ts`, `src/app/locales/fr.ts`
- Create: `src/app/theme.ts`, `src/app/theme.css`, `src/app/settings.ts`
- Create: `src/app/AppShell.test.tsx`, `src/app/settings.test.ts`
- Create: `src-tauri/Cargo.toml`, `src-tauri/build.rs`, `src-tauri/tauri.conf.json`, `src-tauri/capabilities/default.json`, `src-tauri/src/lib.rs`, `src-tauri/src/main.rs`

**Interfaces:**
- `type Locale = "en" | "fr"`
- `type ThemePreference = "system" | "light" | "dark"`
- `getInitialLocale(systemLocale: string, savedLocale: Locale | null): Locale`
- `getTheme(preference: ThemePreference, systemIsDark: boolean): "light" | "dark"`
- `AppShell` renders the app header, workflow navigation, settings entry, and selected workflow content.

- [ ] Scaffold a Vite React TypeScript application and initialize a Tauri 2 desktop target. Use pnpm and commit the generated lockfile.
- [ ] Add Vitest, jsdom, and React Testing Library. Configure `pnpm test` and `pnpm typecheck`.
- [ ] Write tests for French/English system-locale selection, saved locale override, and System/Light/Dark theme resolution. Run `pnpm test -- --run`; confirm the tests fail before implementation.
- [ ] Implement the two locale dictionaries and settings helpers. Persist explicit language/theme choices locally; leave system-following choices unset rather than duplicating OS preferences.
- [ ] Build a polished semantic shell with a compact design-token set for color, spacing, and typography. Use system fonts and local assets. Include visible keyboard focus, named buttons, a settings dialog that closes with Escape and returns focus, and status text that is not color-only. Do not add placeholder anonymization or OCR controls.
- [ ] Run `pnpm typecheck`, `pnpm test -- --run`, and `pnpm tauri dev` on the host OS. Confirm the native app opens without a terminal window and uses the OS locale on launch when no manual language override is saved. Change the OS appearance while the app is running and confirm the theme follows when set to System.
- [ ] Commit the verified shell as `feat(app): scaffold desktop shell`.

### Task 2: Define and test the local worker protocol

**Files:**
- Create: `python/pyproject.toml`, `python/uv.lock`
- Create: `python/src/document_worker/__init__.py`, `python/src/document_worker/protocol.py`, `python/src/document_worker/main.py`
- Create: `python/tests/test_protocol.py`
- Create: `src/app/worker/sidecarClient.ts`, `src/app/worker/sidecarClient.test.ts`
- Modify: `src-tauri/src/lib.rs`, `src-tauri/capabilities/default.json`, `package.json`, `pnpm-lock.yaml`

**Interfaces:**
- Format request JSON line: `{"id":"<uuid>","operation":"list_formats"}`
- Conversion request JSON line: `{"id":"<uuid>","operation":"convert","input_path":"<absolute path>","output_directory":"<absolute path>"}`
- Format response: `{"id":"<uuid>","event":"formats","items":[{"extension":".txt","label":"Text","requires_optional_component":false}]}`
- Progress/result JSON line: `{"id":"<uuid>","event":"progress","percent":0..100}` or `{"id":"<uuid>","event":"result","status":"success|error","output_path":"...","error_code":"...","message":"..."}`
- The worker accepts one request per line on stdin and writes protocol messages only to stdout. Diagnostics go to stderr and never contain document text or detected personal data.

- [ ] Create a Python package using `uv`, pytest, and Ruff. Pin MarkItDown to a reviewed version in `pyproject.toml`; do not install the `[all]` extra by default.
- [ ] Add protocol tests for both operations, malformed JSON, unknown operation, missing input, and structured per-file errors. Run `uv run --project python pytest python/tests/test_protocol.py -q`; confirm the tests fail before implementing parsing.
- [ ] Implement JSON-lines parsing and response serialization. Validate paths and operation names; never accept arbitrary shell commands or executable names from a request.
- [ ] Register Tauri's shell plugin and configure the capability to spawn, write to, and stop only the fixed worker sidecar. The frontend must not be allowed to execute arbitrary programs.
- [ ] Add the matching JavaScript shell plugin dependency and use only its fixed `sidecar()` API. Never construct a process name or command from file names or UI input.
- [ ] Add a TypeScript worker adapter that starts the fixed sidecar, writes JSON lines, correlates events by request ID, and converts malformed/early-exit responses into user-safe errors.
- [ ] Add an integration test using a temporary text file. Verify format discovery and one conversion request produce correlated protocol results and stdout contains no logs or tracebacks.
- [ ] Run `uv run --project python pytest python/tests -q`, `pnpm typecheck`, and `pnpm test -- --run src/app/worker/sidecarClient.test.ts`. Commit the verified worker boundary as `feat(worker): add local processing protocol`.

### Task 3: Implement the MarkItDown adapter and format catalog

**Files:**
- Create: `python/src/document_worker/conversion.py`, `python/src/document_worker/formats.py`
- Create: `python/tests/test_formats.py`, `python/tests/test_conversion.py`, `python/tests/fixtures/`
- Modify: `python/pyproject.toml`, `python/uv.lock`, `python/src/document_worker/main.py`

**Interfaces:**
- `supported_input_formats() -> list[FormatInfo]`, where `FormatInfo` contains `extension`, `label`, and `requires_optional_component`.
- `convert_file(input_path: Path, output_directory: Path) -> ConversionResult`.
- `ConversionResult` contains `output_path`, `status`, and an optional user-safe `error_code` and `message`.

- [ ] Inventory the pinned MarkItDown version's local-file converters and optional extras. Include every enabled local converter that can run without a remote service. Exclude URL/web integrations and any converter whose only path requires a cloud endpoint. Keep OCR-dependent formats marked unavailable until a local OCR plan enables them.
- [ ] Write tests that compare the app's format catalog with the selected converters and assert ODT is absent. Add fixtures for TXT, Markdown, JSON, JSONL, CSV, HTML, and representative enabled Office/PDF formats.
- [ ] Run the new format/conversion tests before implementation and confirm they fail because the catalog and adapter are not implemented yet.
- [ ] Add only the MarkItDown optional extras required by that inventory. Run `uv lock` and `uv run pytest -q`; confirm unsupported formats fail with a stable error code.
- [ ] Implement conversion using MarkItDown's Python API. Write Markdown to the selected output directory using `<input stem>.md`; when occupied, choose the next free name such as `<input stem> (2).md`. Preserve the source and return actionable errors without returning raw exceptions.
- [ ] Test one valid conversion for every declared format using small fixtures. Test unsupported, unreadable, and corrupt files, source preservation, and output write failure.
- [ ] Run `uv run --project python ruff check python/src python/tests` and `uv run --project python pytest python/tests -q`.
- [ ] Commit the verified conversion adapter as `feat(conversion): add MarkItDown adapter`.

### Task 4: Build the conversion workflow UI

**Files:**
- Create: `src/features/conversion/ConversionPage.tsx`, `src/features/conversion/ConversionPage.test.tsx`
- Create: `src/features/conversion/conversionApi.ts`, `src/features/conversion/useConversionJobs.ts`, `src/features/conversion/formatLabels.ts`
- Modify: `src/App.tsx`, `src/app/AppShell.tsx`, `src/app/locales/en.ts`, `src/app/locales/fr.ts`
- Modify: `src-tauri/Cargo.toml`, `src-tauri/capabilities/default.json`, `src-tauri/src/lib.rs`
- Modify: `package.json`

**Interfaces:**
- `ConversionJob`: `{ id: string; inputPath: string; outputPath?: string; status: "queued" | "running" | "success" | "error"; progress?: number; message?: string }`.
- `FormatInfo`: `{ extension: string; label: string; requiresOptionalComponent: boolean }`; map the worker's `requires_optional_component` field at the API boundary.
- `loadSupportedFormats(): Promise<FormatInfo[]>` reads the backend format catalog.
- `startConversion(inputPaths: string[], outputDirectory: string, onUpdate: (job: ConversionJob) => void): Promise<void>` streams per-file progress and completion.
- `ConversionPage` supports native file selection, drag/drop, batch selection, output-folder selection, job progress, and per-file results.

- [ ] Add UI tests for empty state, selected files, unsupported extension, job progress, mixed batch success/failure, output-folder selection, and translated labels. Run `pnpm test -- --run`; confirm new tests fail.
- [ ] Add and register Tauri's dialog plugin for native file/folder selection. Grant only the open-dialog permission needed by the workflow.
- [ ] Implement the conversion page with keyboard-operable file selection and drag/drop as an enhancement, not the only input method. Display the supported formats from the backend catalog instead of duplicating a separate list.
- [ ] Add a native output-folder chooser and show the chosen destination before starting. Explain the numbered-name behavior for output collisions; never overwrite source or output files.
- [ ] Connect the page to the fixed Tauri sidecar API. Announce progress and completion to assistive technologies using a polite status region; move focus only when needed to report a blocking error.
- [ ] Add French and English copy for instructions, format list, progress, success, unsupported files, and recovery steps. Ensure no status depends only on color.
- [ ] Run `pnpm typecheck` and `pnpm test -- --run`. Manually verify keyboard-only operation and screen-reader announcements for a mixed batch.
- [ ] Check the interactive controls against RGAA themes 3 (contrast), 7 (keyboard/script behavior and status announcements), and 11 (control labels).
- [ ] Commit the verified conversion UI as `feat(conversion): add desktop conversion workflow`.

### Task 5: Package local macOS and Windows builds

**Files:**
- Create: `python/packaging/worker.spec`
- Create: `scripts/build-local.mjs`
- Modify: `package.json`, `src-tauri/tauri.conf.json`, `README.md`

**Interfaces:**
- `pnpm app:build` builds the Python worker for the current host, places the correctly target-suffixed binary in Tauri's configured sidecar location, then runs `tauri build`.
- `pnpm app:dev` packages the worker for the current host, then starts the Tauri frontend; the developer runs the command, while the app itself opens without a terminal window.

- [ ] Package the worker for the current host as a PyInstaller one-file executable so Tauri can bundle one fixed sidecar binary. Do not include signing credentials or OCR models.
- [ ] Configure Tauri to bundle only the fixed worker sidecar and the app assets. Restrict worker execution to that exact binary; keep file access limited to user-selected inputs and outputs.
- [ ] Implement `scripts/build-local.mjs` to detect the current OS/architecture, build the worker, place the Tauri target-triple-named sidecar, and invoke `tauri build`. Fail with a clear prerequisite message if Rust, Node/pnpm, or uv is missing.
- [ ] Run `pnpm app:build` on macOS and verify the generated app/installer launches and converts a fixture while offline. Verify no terminal window appears.
- [ ] Run `pnpm app:build` on Windows and verify the generated installer launches and converts a fixture while offline. A native Windows host is required for this verification.
- [ ] Document prerequisites, `pnpm install`, `uv sync --project python`, `pnpm app:dev`, `pnpm app:build`, local artifact locations, supported formats, and ODT exclusion in `README.md`.
- [ ] Run `pnpm typecheck`, `pnpm test -- --run`, `pnpm build`, `uv run --project python ruff check python/src python/tests`, `uv run --project python pytest -q`, and the native Tauri build. Report platform checks that could not run on the current host.
- [ ] Commit local build and packaging support as `build: add local desktop packaging`.

## Plan self-review

- Scope is limited to the shell and Markdown conversion. Presidio anonymization, OCR model selection, updater implementation, CI/CD signing, and GitHub Releases require separate plans.
- Every format claim is generated from and tested against the pinned, locally enabled MarkItDown converters. Remote-only integrations and ODT remain excluded.
- Local builds produce testable artifacts without release-signing secrets. Each OS build must be verified on its native host.
- Accessibility, local-only processing, French/English UI, theme preferences, and per-file batch handling have explicit implementation and verification steps.
