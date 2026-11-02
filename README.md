# IA Toolbox

A locally-running desktop application for converting supported documents to Markdown and for
anonymizing the personal information they contain. All document processing happens locally without
sending content to remote services.

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

**Documents that need a password to open cannot be converted.** A PDF, Word, Excel or PowerPoint
file encrypted with an open-password is reported as protected, so you can remove the protection in
the original application and save a copy.

A document that is merely locked against editing — Excel's "protect workbook structure", Word's
"restrict editing" — is not encrypted and converts normally. Legacy `.xls` workbooks are an
exception: a protected one is reported only as unreadable.

In every case the original file is left untouched and the rest of the batch continues.

## Anonymization

The anonymizer finds personal information in a document and writes an anonymized **copy** in the
same format. The original file is never modified.

### Formats that can be anonymized

Rewriting a document in place is a different capability from converting it to Markdown, so this
catalog is shorter:

- `.txt`, `.text` — Text
- `.md`, `.markdown` — Markdown
- `.csv`, `.tsv` — CSV, TSV
- `.json`, `.jsonl` — JSON, JSON Lines
- `.xml` — XML
- `.html`, `.htm` — HTML
- `.docx` — Word Document
- `.xlsx` — Excel Spreadsheet
- `.pptx` — PowerPoint

**OpenDocument formats, including `.odt` (ODT), are not supported.**

**A PDF cannot be anonymized.** Rewriting its text means rebuilding the file, which loses the
layout. Convert the PDF to Markdown first, then anonymize the Markdown file.

Scanned pages and images are not read: text inside an image needs OCR, which this version does not
include.

### How the review works

1. **Select the documents and an output folder.** Files in an unsupported format are listed and
   skipped, never silently dropped.
2. **Find personal information.** Each document is read and what was found is listed by type —
   person names, organizations, places, email addresses, phone numbers, IBANs, payment card
   numbers, French social security numbers, dates. Each item shows how confident the detector is,
   in words, and where in the document it is.
3. **Choose what to replace.** Nothing is selected at the start, and nothing is written until you
   confirm. Each type can be selected as a whole. Text the format cannot rewrite without breaking
   the document is shown for information and offers no choice.
4. **Confirm.** Choose between a label (`[PERSON 1]`) or masking characters (`●●●●●`), then create
   the copy. Each document succeeds or fails on its own: one failure does not stop the others.

The document is read a second time when the copy is written. A document edited during the review is
reported as changed rather than rewritten at the wrong offsets.

### What is not rewritten

Some content is read, or reported, but deliberately left as it is. The app says so per document:

- Code and markup, in Markdown, HTML, XML and JSON — only the text a reader sees is analyzed.
- Values stored inside XML tag attributes.
- Tracked changes in Word: deleted and inserted text stays, so accepting the revisions later can
  bring personal information back.
- Document properties, such as the author name.
- Text shared between cells in Excel: replacing it changes every cell that uses it.

### Naming of the copy

The copy is `originalname-anonymized` in English, `originalname-anonymise` in French, keeping the
original extension. An existing file is never overwritten: a numbered suffix (`-2`, `-3`) is added
instead.

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
