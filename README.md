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
2. **Find personal information.** Each document is read and what was found is listed, one row per
   value: the value, a few words of the document either side of its first occurrence, where it is,
   and how many times it appears. The language the names were read in is shown above the list and
   can be corrected, which reads the document again. A column of a CSV or TSV file is a single row
   instead, named after its header, showing the first of its values.
3. **Choose what to replace.** Each row proposes a type — person name, organization, place, email
   address, phone number, IBAN, payment card number, French social security number, date — in a
   menu you can change: your answer applies to every occurrence of that value, or to every cell of
   the column. Then tick the rows
   to replace. Nothing is selected at the start, and nothing is written until you confirm. Text the
   format cannot rewrite without breaking the document is shown for information and offers no
   choice.
4. **Confirm.** Choose between a label (`[PERSON 1]`) or masking characters (`●●●●●`), then create
   the copy. Each document succeeds or fails on its own: one failure does not stop the others.

The document is read a second time when the copy is written. A document edited during the review is
reported as changed rather than rewritten at the wrong offsets.

### What is not rewritten

Some content is read, or reported, but deliberately left as it is. The app says so per document:

- Markup itself, in Markdown, HTML, XML and JSON — heading markers, emphasis, list bullets, table
  pipes, raw HTML tags and the fences and delimiters around a code block or a comment are never
  analyzed or replaced. What they wrap is: the body of a fenced code block, of an inline code span
  and of an HTML comment is read and rewritten like any other text, because an address in a snippet
  and a name in a review note are exactly what anonymizing a document is meant to remove. In HTML,
  `<script>` and `<style>` contents are the exception and are reported as not analyzed.
- Values stored inside XML tag attributes.
- Tracked changes in Word: deleted and inserted text stays, so accepting the revisions later can
  bring personal information back.
- Document properties, such as the author name.
- Text shared between cells in Excel: replacing it changes every cell that uses it.

### What to expect from the detector

The review screen exists because the detector is not exact. It errs towards reporting too much: on
a French meeting report, expect a handful of ordinary words picked up as names — a section heading,
the word after a colon — alongside everything that really is personal information. Unchecking a row
costs a click; a value that is never reported is a value that stays in the copy, so the balance is
deliberately set that way. Read the list before confirming.

Three things make that list readable. One value is one row, however many times it appears and
whatever type was guessed for it: every occurrence of a name gets the same pseudonym anyway, so
asking about each one would ask the same question again. The type is a proposal in a menu rather
than a verdict, because the detector does get it wrong and you are the one who knows whether a name
is a person or a firm. And the shape the detector gets wrong most often — a lone capitalised word
opening a line or a heading — is ranked under a **Less likely** heading at the bottom rather than
dropped, because a one-word name in a table cell looks exactly the same. On the sample meeting
report, that turns forty-three spans into thirty-three questions, two of them doubtful and grouped
at the end.

**A column of a table is typed as a whole.** In a CSV or TSV file, when most cells of a column hold
personal information, the column gets one type and every one of its cells is replaced — including
the cells the detector never flagged. That is not a convenience: a model that finds a name in six
cells of a column and misses the seventh left that seventh name in the copy and never offered it for
review, and nobody can untick a row that was never shown. It also makes the list far shorter: on the
sample membership directory, fifty-two spans become twelve questions, nine of them whole columns.
Two conditions are both required before a column is typed this way — its cells have to be mostly
personal information rather than sentences that mention some, and most of them have to hold any at
all. A column of free-text comments stays a list of separate values. If a column is typed wrongly,
the menu on its row retypes every cell at once; the row shows its first values so you can see what
will be replaced. Columns inside an Excel workbook are **not** typed this way yet: its text is
stored in a shared string table with no notion of a grid, so a column cannot be recognized there.

Names are read one line at a time, not over the whole document. A document is not prose: a heading,
a paragraph and a table row carry no full stop between them, and a model given all of it at once
reads one run-on sentence — it loses names in the middle of it and takes the headings for people.

A name the model stopped halfway through is completed. It sometimes tags the first name and leaves
the surname out, and half a name is a leak: the rest stayed in the copy and was never offered for
review. So a detection of a single word takes the capitalised word right after it — one word only,
never onto a name already read as two, and never across punctuation, so a job title or a capital
opening the next sentence stays out.

French dates come from a pattern rather than from the model, which has no date category for French.
The pattern is anchored on the twelve month names, so `2 avril 2026`, `juin 2026` and `18/04/2026`
are reported and a bare `mars` or a figure in a budget table is not. The English model reports its
own dates as before.

Names are read by a model for one language, the one shown above the list; patterns such as IBANs
and email addresses are language-independent. A document read in the wrong language has its names
largely wrong, which is why the guess is shown and can be corrected rather than hidden.

How confident the detector is appears in words, but only where it means something: a pattern with a
verified check digit and a run of digits that merely looks like a phone number are not the same
claim. Names, organizations, places and dates carry no such word — the model gives them all the
same score, so printing it would say nothing.

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
