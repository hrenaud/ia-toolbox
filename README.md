# IA Toolbox

A locally-running desktop application for converting supported documents to Markdown. All document processing happens locally without sending content to remote services.

## Supported Formats

The following formats are supported for conversion to Markdown:

- `.txt`, `.text` — Text
- `.md`, `.markdown` — Markdown
- `.csv` — CSV
- `.html` — HTML
- `.json` — JSON
- `.jsonl` — JSON Lines
- `.epub` — EPUB
- `.docx` — Word Document
- `.xlsx` — Excel Spreadsheet
- `.xls` — Excel 97-2003
- `.pptx` — PowerPoint
- `.pdf` — PDF
- `.ipynb` — Jupyter Notebook
- `.zip` — ZIP Archive

**OpenDocument formats, including `.odt` (ODT), are not supported.**

## Prerequisites

- **macOS or Windows** (Intel or Apple Silicon on macOS)
- **Node.js 22.21.1 or later** (or 24.0.0+)
- **pnpm 12.4.2** — install with `npm install -g pnpm`
- **Rust 1.70 or later** — install from https://rustup.rs/
- **Python 3.11–3.13** via `uv` — install `uv` from https://docs.astral.sh/uv/getting-started/installation/
- **Xcode Command Line Tools** on macOS — install with `xcode-select --install`
- **Visual Studio Build Tools** on Windows (for native module compilation)

## Getting Started

### Install Dependencies

```bash
pnpm install
uv sync --project python
```

### Develop Locally

Start the app with the embedded Python worker:

```bash
pnpm app:dev
```

The Tauri window opens without a terminal. Quit with Cmd+Q (macOS) or Alt+F4 (Windows).

### Run Tests

```bash
pnpm typecheck
pnpm test -- --run
pnpm lint
pnpm format:check
uv run --project python ruff check python/src python/tests
uv run --project python pytest -q
```

### Build for Distribution

Package the application for your platform:

```bash
pnpm app:build
```

The generated installer is located at:

- **macOS:** `src-tauri/target/release/bundle/macos/IA Toolbox.app`
- **Windows:** `src-tauri/target/release/bundle/msi/IA Toolbox*.msi`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, the full test gate, the
architecture boundaries to respect, and how CI and releases are configured.

## Architecture

The application uses:

- **Frontend:** React + TypeScript + Vite, with Tauri 2 for native window management and OS integration.
- **Worker:** Python with MarkItDown for document conversion, packaged as a one-file PyInstaller executable and bundled as a Tauri sidecar.
- **Communication:** JSON-lines protocol over stdin/stdout; the worker receives requests and emits progress/results.
- **Isolation:** All output from third-party libraries is redirected to `/dev/null` before conversion imports run, protecting the JSON-lines protocol from native library output.
