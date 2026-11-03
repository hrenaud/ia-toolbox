# Document anonymization

Specification for the second workflow of the toolbox. It refines the
anonymization section of
[the toolbox design](2026-10-28-desktop-document-toolbox-design.md) into
something implementable, and records the decisions taken since that document
was written.

## Purpose

A user drops a document on the app, sees the personal data it contains listed
for review, chooses what to anonymize and how, and gets a new copy with those
passages replaced. The original is never modified. Nothing leaves the machine.

## What Presidio actually covers

Worth stating plainly, because it sets the boundary between what we configure
and what we build:

| Presidio package                                       | Input it handles                                    | State  |
| ------------------------------------------------------ | --------------------------------------------------- | ------ |
| `presidio-analyzer` / `presidio-anonymizer`            | **a string**, with character offsets                | stable |
| `presidio-structured`                                  | pandas DataFrame, JSON — column/key-level detection | alpha  |
| `presidio-image-redactor`                              | PIL raster images, via an OCR engine                | stable |
| `presidio-image-redactor` (`DicomImageRedactorEngine`) | DICOM medical imaging                               | stable |

There is **no Office document support and no PDF support anywhere in
Presidio**. Every format below that is not a raster image is therefore our own
adapter around the text engine. That is the whole engineering content of this
workflow.

## Format coverage

The input list is independent of the conversion workflow's. It is organised in
tiers by what the adapter has to do, not by how common the format is.

### Tier A — the file is its text

`TXT`, `MD`, `CSV`, `TSV`, `JSON`, `JSONL`, `XML`, `HTML`

Read, analyze, replace by offset, write. The adapter is a decode and an encode;
there is no formatting to preserve beyond the bytes around the edits. These are
near-free once the pipeline exists, which is why they come first — they prove
the pipeline end to end before any OOXML complexity.

Specifics:

- Encoding is detected and round-tripped, and the output keeps the input's
  line endings. A tool that silently converts CRLF to LF has modified the
  document.
- `CSV`/`TSV`: detection is run per column, and the header name is fed to the
  analyzer as context — a column called `courriel` or `nom` lifts recall far
  above what the cell values alone give. The field structure is preserved:
  replacements go inside fields, quoting rules are respected, and a replacement
  containing a delimiter is quoted rather than breaking the row.
- `JSON`/`JSONL`: keys are context, values are analyzed. Keys themselves are
  never rewritten, document structure is preserved, and output stays valid
  JSON. JSONL is processed line by line so one malformed line does not lose the
  file.
- `XML`/`HTML`: text nodes and attribute values that hold visible text are
  analyzed. Tags, attribute names and structure are never rewritten. Scripts,
  styles and comments are reported as not analyzed rather than silently
  skipped.

`presidio-structured` is the obvious candidate for the CSV and JSON cases, but
it is alpha, it decides per _column_ rather than per value, and it would pull
pandas into the worker. Per-value replacement with the header as context gives
finer results with less weight. Decided against it, revisit if the column-level
approach proves better in practice.

**What the implementation round-trips, and what it does not.** Encoding, BOM and
line endings round-trip. Three things are normalised rather than preserved
byte for byte, and the choice is deliberate in each case:

- **CSV/TSV quoting** is re-emitted as `QUOTE_MINIMAL`. A field that was quoted
  for no reason loses its quotes. Preserving the original quoting would mean
  writing our own CSV writer; `csv` already guarantees the property that
  matters, which is that a replacement containing a delimiter, a quote or a
  newline comes back as the same field.
- **JSONL blank lines** are dropped, because a blank line is not a JSON
  document and there is nothing to re-emit.
- **XML/HTML serialisation** is lxml's: attribute quoting and empty-element
  syntax may differ from the input even in parts no edit touched. The output is
  equivalent markup, not the same bytes.

A user who needs the bytes untouched outside the edits is better served by a
tier B format, where the untouched parts genuinely are copied verbatim.

### Tier B — OOXML, format-preserving

`DOCX`, `XLSX`, `PPTX`

A new copy of the package with the detected spans replaced and everything else
byte-identical. This is where the work is, and all three need the same two
operations — extract the text with a map back to its location, then write edits
through that map.

**DOCX.** Text lives in more than one part, and all of these are scanned:
the body (`word/document.xml`), headers and footers — where client names and
reference numbers usually sit — footnotes and endnotes, comments, text boxes
and shape text, and hyperlink display text plus `mailto:` targets in
`document.xml.rels`.

**PPTX.** Slides (`<a:t>` runs in DrawingML), **speaker notes**, placeholder
text inherited from layouts and masters, comments, and the **alt text** on
shapes and pictures, which is a reliable place for forgotten names.

**XLSX.** The shared strings table (`xl/sharedStrings.xml`), inline strings,
cell comments and notes, and header/footer text are rewritten. A string in the
shared table is referenced by many cells, so replacing it affects all of them —
the review screen says how many.

Two things are read and reported but **never rewritten**, because in a workbook
they are code rather than content:

- **Formula literals** (`<f>`). A string inside a formula is both content and
  code, and rewriting it can change what the spreadsheet computes.
- **Sheet names and defined names** (`xl/workbook.xml`). The spec originally
  listed these as rewritable; the implementation does not, and this is the
  correction. A sheet name is a reference target: renaming `Dupont` to
  `[PERSONNE 1]` turns every `=Dupont!A1` and every defined name pointing at
  that sheet into a `#REF!`. Renaming it _and_ every reference to it is a
  refactoring tool, not an anonymizer, and getting it half right is worse than
  not doing it — so the detections are shown and the user renames the sheet in
  Excel, which does fix the references.

### Tier C — raster images

`PNG`, `JPEG`, `TIFF`, `BMP`

Redaction, not replacement: you cannot put a plausible name back into a
photograph. `presidio-image-redactor` finds text with an OCR engine and paints
over the boxes it matched.

This tier depends on a decision the project has not taken yet. The library's
default OCR engine is Tesseract, reached through `pytesseract` — a **system
binary, not a Python package**, which a frozen worker cannot simply import, and
which the design document's optional-OCR section already has to resolve for
conversion. Tier C is specified here but gated on that answer, and must use
whatever local OCR the app settles on rather than adding a second one.

Images **embedded** in tier B documents are a different problem and stay out:
scanning them means OCR plus re-encoding inside the package. Until then, a
document containing images is reported as partly unprocessed.

### Formats named and excluded

- **PDF.** Users will try it — the conversion workflow accepts it — so the
  refusal has to be explicit and explained rather than a format quietly absent
  from the list. Presidio offers nothing for PDF, and format-preserving text
  replacement in a PDF is not a tractable problem at this scale: text has no
  reliable logical structure, replacements break glyph positioning, and
  embedded font subsets often lack the glyphs a replacement needs. The two
  honest options are rasterise-and-redact, which destroys the text layer and
  every bit of accessibility with it, or convert to another format first. The
  app will say which, not pretend.
- **DICOM.** Presidio supports it and it would work. It is medical imaging for
  a radiology audience; this product has a different one, and it adds
  `pydicom` for nobody here. Available if the audience ever changes.
- **ODT and OpenDocument generally**, excluded project-wide and documented as
  unsupported in the README. Nothing here changes that.
- **Legacy `DOC`, `XLS`, `PPT`.** Binary formats with no format-preserving
  write path worth building. Users are told to save as the modern format first.

### Why only tiers A and B are in the build

Tiers A and B are implemented. Nothing below them is, and the reasons are not
"later" in every case — some are refusals.

**Tier C is blocked, not deprioritised.** `presidio-image-redactor` needs an OCR
engine, and its default is Tesseract through `pytesseract`: a **system binary**,
not a wheel. A PyInstaller onefile worker cannot import a binary that is not on
the machine, so shipping tier C means shipping and code-signing a second native
executable per platform, on both macOS and Windows, inside the signed build the
release pipeline produces. That is a packaging and notarisation decision the
project has not taken, and it is the **same** decision the conversion workflow's
optional-OCR section is waiting on. Taking it twice, differently, would leave
the app with two OCR engines. So tier C waits for that one answer, and whatever
it is, tier C uses it. The alternative — an OCR Python wheel chosen just for
this feature — is how a 40 MB worker becomes a 400 MB one.

**PDF is a refusal.** It is the format users will try first, which is exactly
why it gets an explicit message instead of silence. Presidio has nothing for
PDF, and format-preserving replacement in a PDF is not a smaller version of the
OOXML problem — it is a different one. There is no logical text structure to map
offsets onto, replacing a string invalidates the glyph positioning around it,
and the embedded font is usually a subset lacking the glyphs a placeholder
needs. The only two workable paths are rasterise-and-redact, which throws away
the text layer and with it every accessibility property the project commits to
preserving, or convert first. Neither belongs behind a format that silently
"works".

**Embedded images stay out even inside tier B.** Scanning the picture in a DOCX
means OCR (see above) plus re-encoding an image inside a package we otherwise
copy byte for byte. Instead, a document carrying images is reported as partly
unprocessed — the report is the feature, not a workaround for a missing one.

**DICOM is a scope decision.** Presidio supports it and it would work. It is
radiology tooling for a radiology audience, and this product has a different
one; adding `pydicom` to every user's worker for nobody here is weight without
a reader. Reopen it if the audience changes.

**ODT and OpenDocument are excluded project-wide**, in conversion and here
alike, and the README says so. An anonymizer covering a format the converter
refuses would be the one place the app contradicts itself.

**Legacy `DOC`, `XLS`, `PPT` have no write path.** They are binary formats whose
format-preserving rewrite would be a from-scratch implementation per format, for
documents a user can convert once in Office and then anonymize as tier B. The
app says to do that.

What this leaves is a line the UI must hold: a format we cannot anonymize is
**absent from `list_anonymization_formats`** — the catalog in
`python/src/document_worker/anonymization/formats.py` is deliberately not the
conversion catalog, and the dispatcher returns `None` for `.pdf` rather than an
adapter that fails late. The user finding out after handing over a file they
believed was handled is the worst failure available here.

## Codes the UI has to translate

Adapters do not write user-facing sentences; they emit codes, and the French and
English strings live in the interface. Two sets:

**Notes** — things read, reported, and left alone. They appear in the
not-processed report:

| Code                                | Meaning                                                                                                                    |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `markup_code_not_analyzed`          | HTML/XML comments, `<script>` and `<style>` content, Markdown code blocks and code spans were not analyzed.                |
| `xml_attributes_not_analyzed`       | An XML document has attribute values; unlike HTML there is no way to tell visible text from metadata, so they are skipped. |
| `tracked_changes_not_rewritten`     | The document has revisions (`w:delText`, `w:ins`); accepting them later can bring the personal data back.                  |
| `document_properties_not_rewritten` | `docProps/core.xml` or `app.xml` holds text — author, company, title.                                                      |
| `xlsx_shared_strings_reused`        | One shared string serves many cells, so one replacement changes all of them.                                               |

**Adapter errors** — the file cannot be processed at all, and nothing is
written:

| Code                  | Meaning                                                            |
| --------------------- | ------------------------------------------------------------------ |
| `unreadable_text`     | Not decodable as text in any encoding tried.                       |
| `malformed_json`      | Invalid JSON.                                                      |
| `malformed_markup`    | Unparseable XML or HTML.                                           |
| `unsupported_package` | Not a readable Office package, or a part inside it will not parse. |

**Pipeline errors** — the request itself cannot be honoured. Same shape, raised
by `anonymization/pipeline.py` rather than by an adapter:

| Code                       | Meaning                                                                            |
| -------------------------- | ---------------------------------------------------------------------------------- |
| `input_not_found`          | The file is not there or not readable.                                             |
| `unsupported_format`       | The anonymizer has no adapter for this extension.                                  |
| `password_protected`       | The package is encrypted; it is recognised from its own bytes, not from a failure. |
| `invalid_output_directory` | The output folder does not exist.                                                  |
| `document_changed`         | The kept detections no longer fit the document. Analyze it again.                  |
| `not_rewritable`           | The request keeps a span in text this format never writes back.                    |
| `invalid_request`          | The request asks for something the worker does not offer, such as an operator.     |
| `write_failed`             | The copy could not be written. Any partial file is removed.                        |

**Why `document_changed` and not `invalid_request`.** The spec first treated
every mismatched offset as a malformed request. It is not one: a request whose
shape is right and whose offsets were right an hour ago describes a document the
user has since edited or replaced. `invalid_request` would tell them to fix
something they did nothing wrong with, while `document_changed` names the one
action that works — analyze again. Shape errors are still `invalid_request`, and
they are caught at parse time in `protocol.py`, before the document is opened.

**Why `not_rewritable` is an error and not a silent drop.** Detections inside a
formula literal or a sheet name are reported, because a user has to know a name
is still in there. The review screen does not offer them, so a request that
keeps one is a bug on the UI side of the protocol. Dropping it quietly would
write a copy the user believes is clean.

## The adapter boundary

Covering this many formats is only affordable with one pipeline and one small
interface per format. The pipeline — detection, review, operators, output
naming, batch, error reporting — is written once. An adapter provides two
things:

```
extract(path)        -> list of text units: (unit id, text, human-readable location)
apply(path, edits, output_path)
```

A unit is an independently-analyzed string with its own offset space: a CSV
column, a DOCX part, a PPTX slide, an XLSX sheet. Nothing is ever concatenated
across units, because an offset that crosses a unit boundary cannot be mapped
back. `edits` are `(unit id, start, end, replacement)`, and the adapter owns
the mapping from offsets to wherever the text physically lives.

This is the one abstraction the design admits, and only because it has six real
implementations. It is not there for a hypothetical seventh.

## The run problem, which tier B adapters all share

Within an OOXML part, text is split across runs at arbitrary boundaries —
formatting, spell-check state and editing history all split runs, so a single
name is commonly `Jean` + ` Dup` + `ont`. Presidio needs one continuous string;
the writer needs to put a replacement back into runs.

One structure per unit, built once: the concatenation of every text node in
document order, plus the mapping from each character index to its node and the
offset inside it. Replacement resolves a span to the nodes it covers; a span
inside one node is a substring edit, a span across several writes the whole
replacement into the first node it touches and empties the covered text from
the others — the replacement inherits the formatting of the run where the
entity starts, the only choice that does not invent formatting.

Three rules that are not optional:

- edits within a unit are applied from the highest offset down, so earlier
  offsets stay valid while lengths change;
- `xml:space="preserve"` is set on any text node whose new value begins or ends
  with whitespace, or the whitespace is silently dropped on the next open;
- extraction inserts no separator between runs — an inserted character shifts
  every offset after it — but does insert one at paragraph, cell and slide
  boundaries, without which the last word of one and the first of the next
  concatenate into phantom detections.

## Syntax is not content

A tier A format carries its structure in the same characters as its text, and
the first Markdown adapter handed the raw file to the model. That costs twice.
An email inside a fenced code block is offered for replacement although this
spec says code is not analyzed; and the syntax wrecks the sentences around it,
so `**Lieu :** Nantes, salle Loire` yields `salle` as a person and a table cell
comes back with its closing pipe inside the span.

So the Markdown adapter splits the file into content and structure, and builds
the `TextMap` over the content only. Excluded are fenced code blocks, inline
code spans, HTML comments, raw HTML tags, heading markers, list bullets,
blockquote markers, emphasis runs, table pipes and the table rule row. Code and
comments raise `markup_code_not_analyzed`; emphasis and bullets are not worth a
note. The adapter still does not parse Markdown into a tree and re-render it —
every excluded piece is copied back byte for byte, and the first test of the
class is that a document with no edits round-trips identically.

Any format added later excludes its own syntax the same way, rather than hoping
the model ignores it.

**No detection may cross a line break.** An adapter inserts a break between two
blocks so their words cannot fuse, and the small French model then runs a name
across it. One replacement over such a span writes the pseudonym into the first
block and empties the second: a heading disappears. `detection.line_spans()`
cuts every span at its newlines and narrows each piece. Splitting rather than
truncating is what keeps both halves — `"l'Université \n Claire Dubois"` holds
one real name, and dropping either end would lose it.

## Reported, not rewritten

Two things that are personal data but whose rewriting changes document
semantics. Both are surfaced to the user, in every tier B format:

- **Document properties** (`docProps/core.xml`: author, last modified by,
  title, company). Personal data by definition. Reported, with clearing them
  offered as an explicit separate choice.
- **Tracked changes and revision metadata**, which carry an author name per
  edit. A document with unaccepted revisions cannot be anonymized reliably; the
  honest answer is to say so and ask the user to accept or reject them first.

## Protocol

Anonymization is two round trips, because the user decides in the middle. The
worker holds no state between them: the second request carries everything it
needs.

`analyze` — given an absolute input path, return the detections.

`anonymize` — given the same input path, an output directory, an operator, and
the subset of detections the user kept, write the copy.

Consequences for `python/src/document_worker/protocol.py`, whose `Request` is
today a frozen dataclass of `id, operation, input_path, output_directory` with
a gate accepting only `list_formats` and `convert`:

- the gate grows `analyze`, `anonymize`, and a format list for this workflow
  (`list_anonymization_formats`), since the two workflows' lists are
  independent and the UI must not hard-code either;
- path validation becomes per-operation — `analyze` has no output directory;
- `anonymize` carries a structured payload, validated as strictly as the paths
  are today: each kept detection is a unit id, a start offset, an end offset
  and an entity type, with offsets inside that unit's extracted text. Anything
  else is `invalid_request`, not a traceback.

The existing discipline holds: errors never carry request data or exception
text, and the worker's stdout stays a clean JSON-lines stream because
`silence_process_output()` redirects the real file descriptors before any
processing library is imported. Presidio and its model loader write to stderr on
import and on first inference; that redirection is what keeps them from
corrupting the protocol.

## Detection

- ~~One analyzer, both languages. A document is analyzed for French and English
  and the detections merged — mixed-language documents are the norm here.~~
  **Revised during implementation: one document, one language.** Running both
  models over the same text is what returned `Claire Dubois` as a person and as
  an organization at once, each with the same score, and a French model reading
  English prose tags ordinary words as names. The language is guessed from the
  text by counting the function words each model knows, reported in the result
  and overridable in the `analyze` request — the user is the one who can see
  the guess was wrong. Only that language's model proposes names and dates; the
  patterns (email, IBAN, card, phone, NIR) are language-independent and still
  run regardless. A genuinely bilingual document is read in one language and the
  other language's names are missed: a deliberate trade for a list the user can
  actually read.
- Entity types: person, organization, location, email address, phone number,
  IBAN, credit card, French social security number (NIR), and date of birth.
  The NIR needs its check-key validation; a bare 15-digit pattern puts too many
  false positives in front of a user.
- A confidence score is kept per detection and shown. Overlapping detections
  resolve to the longer span; equal spans with different types keep the higher
  score.
- Detections never appear in logs.

**What the implementation added to this list.** Three decisions the spec left
implicit, each visible in `detection.py`.

- **No country-specific recognizers.** Presidio's registry is loaded with
  `countries=[]`, which keeps the locale-agnostic recognizers — email, IBAN,
  credit card, phone, date — and drops the national identifier recognizers it
  ships for a dozen other countries. A US social security pattern loose on a
  French document is a false-positive factory, and a review screen full of noise
  is one a user stops reading. France is not among those dozen countries, so the
  NIR recognizer is ours, and the check key is what validates it rather than the
  pattern: the regex is deliberately loose, and `validate_result` decides.
- **Spans are narrowed before they are reported.** The small French model
  routinely tags the word that introduces a name — `de Marie Lefebvre`, not
  `Marie Lefebvre`. Replacing that span would delete a word the sentence needs
  and redact one that is not personal data, so surrounding punctuation and a
  leading particle are cut off. The cost is a name whose particle is part of it,
  `de Gaulle` tagged without a first name, keeping its particle in the clear;
  the name itself is still replaced.
- **The entity list filters results, it does not constrain the request.** Not
  every type has a recognizer in every language — Presidio ships no French
  credit card recognizer, and the English pass covers it — and asking Presidio
  for a type it cannot serve in a language is a deprecation warning now and an
  error in a later version.

No score threshold is applied. The review screen is the filter, and a threshold
here would hide detections from the person whose job is to judge them.

## Operators

First version: **Replace** and **Mask**.

**Replace** (recommended, default) substitutes a labelled placeholder:
`[PERSONNE 1]`, `[PERSONNE 2]`, `[EMAIL 1]`. The number is stable per distinct
source value within a document, so the same person is the same label everywhere
and the copy stays readable — a report where everyone is `[PERSONNE]` is
anonymous and useless. The mapping lives in memory for the job and is never
written anywhere.

**Mask** keeps the shape and hides the content: the last four characters of an
IBAN or phone number remain, the rest becomes `•`. Fixed per entity type, not
user-configurable.

**Redact** and **Hash** follow once the replacement machinery exists — they are
different strings through the same path. **Encrypt** is deferred until the
provenance and storage of the key are decided: an operator producing ciphertext
nobody can decrypt is a data-loss feature, not a privacy one.

For tier C, the only operator is a painted box.

## Output

- Written to the folder the user chose; source folder by default.
- Name: the source stem with a locale-appropriate suffix —
  `rapport-anonymise.docx` in French, `report-anonymized.docx` in English — and
  the source extension unchanged.
- A collision appends a counter (`rapport-anonymise-2.docx`). An existing file
  is never overwritten and the source is never written to. No in-place mode,
  not even behind a flag.
- The result reports per document: detections applied, units scanned, and what
  was **not** processed — embedded images, formula literals, tracked changes,
  script and style blocks. This report is a feature, not a footnote: it is what
  stops a user believing a copy is clean when it is partly not.

## Review screen

It stands between detection and writing, so it must be usable without a mouse.

- ~~Detections grouped by entity type~~, each row showing the detected text,
  its type, its confidence, and its location in terms the user recognises —
  "page header", "slide 4 notes", "sheet Ventes, cell B12", "column courriel" —
  with a checkbox. **Revised during implementation: one flat list, one row per
  value.** See below.
- ~~Bulk selection per type and per unit, so a user can drop all organizations,
  or everything on one slide, in one action.~~ **Dropped with the grouping**:
  "select everything" and "select nothing" remain.
- Where one replacement affects several places — an XLSX shared string — the
  row says how many.
- Keyboard-operable with visible focus; the count of kept detections announced
  through the existing status region when it changes; state never conveyed by
  colour alone, so confidence is a word, not a shade.
- Nothing is written until the user confirms, and the confirm action names the
  output file.

### What was built, and where it departs from the above

Implemented as `ReviewList.tsx` and `AnonymizationPage.tsx`. The deliberate
deviations:

- **The selection starts empty, not all-kept.** A confirmation reached by a slip
  then replaces nothing instead of rewriting a whole document, and the announced
  "kept of total" count makes the empty start visible. "Select everything" is
  one action away.
- **One row per value, and the type is a menu, not a label.** The grouped
  design was built first and tried on a ten-line meeting report: fifty rows,
  the same name asked about eight times, and one name asked about twice under
  two headings because the two models typed it differently — both claiming high
  confidence. So the row is the value, case-folded, type excluded from the key:
  one value is one question. The type the worker proposed is shown in a
  `<select>` the user can change, and the answer is applied to every occurrence
  of that value when the payload is built, because the type decides the label
  the copy carries. The row shows the first occurrence with a few words of the
  document either side — "Loire" alone is a question nobody can answer.
- **Bulk selection is per entity type only, not per unit.** ~~A unit is an
  internal part id; grouping the screen by both type and unit would mean two
  competing hierarchies over the same rows.~~ **Superseded**: with the grouping
  gone, the only bulk actions are "select everything" and "select nothing".
- **The confidence word is shown only where it varies.** Every type the model
  guesses at — person, organization, location, date — scores exactly 0.85, so
  "high confidence" was printed on precisely the rows the user has to check one
  by one. A word that never changes is not information, and here it contradicted
  what the user was reading. It is kept for the types a pattern decides, where
  a verified check digit (1.0) and a bare run of digits (0.4) are different
  claims.
- **The document's language is part of the review.** It is shown per document
  with a menu to correct it; correcting it re-runs `analyze` for that document
  and clears its selection and type overrides, because the offsets come from a
  different pass.
- **The shared-string note carries no count.** `xlsx_shared_strings_reused` is
  a document-level note and the worker reports no reference count per shared
  value, so a number cannot be stated without inventing it. The row says the
  value is shared and that replacing it changes every cell using it. Stating
  the count would require the adapter to report the fan-out per shared string;
  that is a worker change, not a UI one.

## Batch and failure handling

Per document, in sequence. A failure on one does not stop the others. The
per-file error vocabulary follows conversion's — unsupported format,
password-protected, corrupt, output not writable — each a plain-language
message with no traceback, and `processing_failed` as the generic fallback. A
format outside the list is rejected at selection time by the workflow's own
format list, with PDF getting its own explanatory message rather than a bare
refusal.

## Models

**Built: the two small models are frozen into the worker.** They cost about
30 MB, which this project can ship, and freezing them removes a first-run
network step, a download UI, a corrupt-download path and a "model missing"
state from the product. Anonymization therefore works the moment the app is
installed, like conversion. See _Detector choice_ for how PyInstaller is made
to find them.

The rules below bind only if a later, larger model is downloaded instead:

- Downloaded once after installation, into the application data directory, with
  the download size shown before it starts.
- Loaded by absolute path with the library's offline flag set, so a missing
  file is an error rather than a silent network fetch.
- **Models are data; code is never downloaded.** The worker is a frozen
  PyInstaller onefile binary with no writable `site-packages` and no `pip`, so
  Python packages are fixed at build time. Fetching executable code at runtime
  into a process whose library validation we had to disable is a posture this
  app will not take.
- A corrupt or partial download is detected and re-fetchable, not an obscure
  failure at first inference.

## Detector choice

Presidio stays the frame; its value is exactly what the review screen needs —
offsets, a score per detection, checksum-validated recognizers, context
strengthening, the operator layer. The NER model behind it is interchangeable,
and the candidates were the spaCy pipeline Presidio defaults to, and GLiNER
through Presidio's built-in `GLiNERRecognizer` with a multilingual PII
checkpoint. GLiNER should recall French person names better.

**Decided: spaCy.** Not on recall — on weight, and the measurement is not close
enough to need numbers. `gliner` 0.2.29 declares `torch>=2.0.0` as a **base**
dependency; its `onnx` extra adds `onnxruntime` without removing torch. A
frozen onefile worker would carry PyTorch, and nothing about an optional
post-install download changes that, because the import happens at build time
when PyInstaller walks the closure. spaCy's models are a separate download of
tens of megabytes, which is the shape this project can ship.

**Which models the suite runs on.** `fr_core_news_sm` and `en_core_web_sm`,
pinned by URL in the `dev` dependency group and hash-locked, so CI and a local
`uv run pytest` install the same bytes. `python/tests/test_detection_models.py`
fails rather than skips when one is absent: a model-dependent test that skips is
a green build over a code path nobody ran, which is the specific failure this
decision exists to prevent. `spacy download` is rejected for the same reason —
an unpinned fetch at test time means two runs of one commit can test two
different models.

The small models bound what the suite may assert: entity types, offsets, and
overlap resolution, which are our code. **Recall is recorded, never asserted.** A
threshold would make a model upgrade a red build, and the number it would guard
is the model's property, not ours. Baseline recall figures on French fixtures
are still to be measured, so a later switch has something to beat.

**The two small models are frozen into the worker.** PyInstaller does not
follow `spacy.load("fr_core_news_sm")`, and presidio builds its recognizer
registry by walking modules, so neither is found by import analysis. A worker
frozen without them starts, answers `list_anonymization_formats`, and dies on
the first `analyze` with no message at all, because output isolation has
already taken its stderr away. `python/packaging/worker.spec` therefore
`collect_all`s spaCy, presidio and both model packages by name, and
`python/tests/test_packaging_spec.py` asserts that list against
`detection._MODELS` rather than against a second copy of it. The cost is about
30 MB of binary. Shipping a larger model than the suite tests stays possible —
the suite would then test the plumbing while the recorded figures describe the
shipped model — but it is no longer a post-install download.

**Precision measured, and left as it is.** On the French meeting-report fixture
the detector reports 32 spans, which the review screen collapses into 24 rows,
2 of them ranked doubtful: `Annexe` and `Prochaine` — section headings, both
below the fold. Before these rules the same document produced about fifty rows
with the noise mixed into them. A POS filter was prototyped —
`AnalyzerEngine.analyze` takes pre-computed `nlp_artifacts`, so reading
`.pos_` off the tokens costs no extra model time — and dropping single-token
non-`PROPN` spans removed 10 false positives and also `Nantes`, a real location
the model tagged `NOUN`. For a privacy tool a miss is worse than a noise row
and the review screen starts empty, so the filter is rejected. The README says
plainly what to expect instead.

**Dates are not detected in French, and the type is kept anyway.**
`fr_core_news_sm` labels only `LOC`, `MISC`, `ORG` and `PER` — it has no date
category, so no French document ever yields a `DATE_TIME` detection, while
`en_core_web_sm` does report them. The type stays in the menu because an English
document uses it and because the user can retype a value onto it by hand. A
French date pattern was not written: a date is a wide, ambiguous shape in free
text, and a regex loose enough to catch `juin 2026` also catches every figure in
a budget table. The README states the gap instead.

**A larger model is not the answer either.** `fr_core_news_md` was measured on
the same fixture: 33 rows against the small model's 35, the same `La carte de
service` and `Université`, and `rue des Lilas` cut down to `Lilas` — a worse
address on the one value a reader would most want gone. Forty-four megabytes for
two rows and a recall loss is not a trade worth shipping, so the two small
models stay.

**What the noise cost is paid with instead.** Six rules, only the first of
which drops anything:

- The model reads one line at a time; the patterns keep the whole unit. A unit's
  text is not prose — an adapter joins a heading, a paragraph and a table row
  with newlines and none of them ends in a full stop — so handed all of it the
  small model reads one run-on sentence. It lost `Sophie Marchand`, named in a
  paragraph between two headings, and the second `Thomas Nguyen`, in a table
  cell, while reporting `Lieu`, `Participants`, `Décisions` and `Points` as
  people. Per line it finds both names and reports none of those four. The
  patterns are the opposite case: a NIR is accepted on the strength of the words
  introducing it, which can sit a line away, so they still see everything.

- A `PERSON` or an `ORGANIZATION` is narrowed to the part of it that starts with
  a capital, because both are named with one in French and English. `la mairie
de Rennes` becomes `Rennes`, and a span holding no capital at all — `porte le
numéro de sécurité` — held no name to begin with and is dropped. `LOCATION` is
  excluded from this: an address is lowercase and still personal data, and
  cutting `rue des Lilas` to `Lilas` would leave the street in the copy. This
  rule subsumes the older list of leading particles, which is deleted.
- `Detection.likely` is false for the shape the model gets wrong most often: a
  lone capitalised word opening a line. It is reported all the same — a one-word
  name in a table cell has that exact shape — but the review screen ranks it
  under its own heading at the bottom of the list. `score` is the detector's
  confidence and answers a different question; this one is ours.
- A lone capitalised word that is a function word in the document's language is
  refused outright. `Le`, opening a line, is not a brand — it is a French
  article the model tagged because of the capital. The stop-word list is
  spaCy's own, per language, so there is no hand-written list of pronouns to
  keep in step with anything.
- Adjacent address components are merged into one detection, postcode included:
  `12 rue des Lilas`, `44000` and `Nantes` were three rows asking one question,
  and a user who unticked one of them left the address half in the copy.
- The review screen collapses every occurrence of a value into one row, case
  ignored and type ignored, because `operators.py` already assigns one pseudonym
  per `(type, value.casefold())`. Showing eight occurrences apart would promise
  a distinction the output does not make, and it is what turned a ten-line
  document into fifty questions. The count the page announces is counted in rows
  for the same reason.

Measured on the fixture, and on the packaged binary: 47 spans become 35 rows, 9
of them ranked low, and all 9 are ordinary words — `Participants`, `Décisions`,
`Rédigé`. Twenty-six questions remain where there were fifty.

## Verification strategy

Tests first, per the project's rule that a test passing before the fix exists
is not evidence of anything.

- **Dependency closure.** Extend `python/tests/test_dependency_closure.py` over
  the pinned anonymization dependencies and assert no cloud or remote-service
  client enters the closure. This is what makes processing local; an offline
  run would only show that no call happened that run.
- **Per-format extraction**, on fixtures built to be hostile: a name split
  across three runs; a run with `xml:space="preserve"`; an entity spanning a
  hyperlink boundary; text in a DOCX header, footnote, comment and text box; in
  PPTX notes, a master placeholder and shape alt text; in an XLSX shared
  string, cell comment and sheet name; a CSV field containing the delimiter and
  a quote; CRLF line endings; a non-UTF-8 encoding. Assert the extracted string
  and assert every offset resolves to the right location.
- **Per-format writing**: the copy opens without a repair prompt, the
  replacement is present, formatting around the edit is unchanged, line endings
  and encoding round-trip, and the source file's bytes are unchanged.
- **The absence assertion is the important one.** The source text must be
  absent from the _whole_ output — every part of an unzipped package, not just
  the main document part.
- **Detection**, on short French and English fixtures per entity type,
  asserting type and span. Recall figures recorded rather than asserted, giving
  step 1's comparison a baseline. The models this runs on are installed by the
  `dev` dependency group and asserted present — these tests never skip.
- **Operators**: label stability for repeated values, distinctness for
  different values, mask shape per entity type.
- **Protocol**: malformed, out-of-range and unknown-unit payloads produce
  `invalid_request` with no document text in the error.
- **The not-processed report** is asserted per format: a document with an
  embedded image, a formula literal, or tracked changes says so.
- **UI**: review list rendering, per-detection, per-type and per-unit
  selection, the kept-count announcement, and that nothing is written without
  confirmation.
- **Batch**: a failing document does not prevent the others and reports
  separately.
- Manual pass: keyboard navigation and screen-reader announcements on the
  review screen, and one real document per tier end to end in a packaged build.

## Implementation steps

Each ends in something checkable. Tier A first, because it makes the pipeline
real at a fraction of the cost and every later step inherits it.

1. **Pin the dependencies and choose the detector.** Extend the closure test;
   measure both candidates on French fixtures for recall, installed size and
   cold-start time. Verify by numbers, written into this document. — **Done for
   the dependency half**: Presidio is pinned without extras and the detector is
   spaCy, because `gliner` declares `torch` as a base dependency and no extra
   removes it. Recall numbers still to measure.
2. **Detection on plain text** behind `analyze`, French and English, no
   document involved. Verify by the detection tests. — **Done** for the
   detection half (`detection.py`, `tests/test_detection.py`). `analyze` itself
   is step 10.
3. **The pipeline and the tier A adapters** — TXT, MD, XML, HTML — including
   operators, output naming and the not-processed report. Verify by the tier A
   extraction and writing tests. — **Adapters and operators done**
   (`textmap.py`, `adapter.py`, `formats.py`, `text_adapters.py`,
   `operators.py`). Output naming and the report belong to the pipeline, which
   step 10 wires.
4. **CSV/TSV and JSON/JSONL**, with header and key context and structure
   preservation. Verify by the field- and structure-integrity tests. — **Done.**
5. **DOCX**: extraction across every part listed above, then writing. Verify by
   the DOCX tests, especially the whole-package absence assertion. This step
   carries the risk. — **Done** (`ooxml_adapters.py`).
6. **PPTX**, which reuses the DOCX run machinery over a different part layout. —
   **Done**, by rules over the same machine rather than a second implementation.
7. **XLSX**, including shared-string fan-out and formulas reported but not
   rewritten. — **Done**, with sheet names also not rewritten.
8. **The review screen**, keyboard and announcements included. Verify by the UI
   tests plus the manual pass. — **Done** (`ReviewList.tsx`,
   `AnonymizationPage.tsx`, `AnonymizationPage.css`, `review.ts`, and their
   tests), with the three deviations recorded above. The manual keyboard and
   screen-reader pass is still owed.
9. **Batch and failure isolation.** Verify by the batch tests. — **Done**: the
   worker handles a document per request and the page reports each result and
   each failure on its own, so one bad document neither stops the batch nor
   hides the copies that were written. A transport failure aborts the batch
   instead of repeating one error per document.
10. **Wire the protocol**: `analyze`, `anonymize` and
    `list_anonymization_formats`, per-operation path validation, strict payload
    validation, output naming and the not-processed report. — **Done**
    (`protocol.py`, `anonymization/pipeline.py`, the dispatch in `main.py`,
    `tests/test_anonymization_pipeline.py`). The report's French and English
    strings land with the screen that renders them, in step 8.
11. **Tier C images**, gated on the project's OCR decision and using whatever
    local engine it picks. Not startable before that decision exists.

## Open decisions

- Whether clearing document properties is on by default. It is the safer
  default and the more surprising one.
- The exact mask length per entity type.
- ~~Where the model download is triggered~~ — **moot**: the two small models are
  frozen into the worker, so there is no download to trigger, and
  `fr_core_news_md` was measured and rejected (see "A larger model is not the
  answer either"). The question returns only if a larger model is reconsidered,
  and it should then get the same answer as the optional OCR model.
- Which local OCR engine tier C uses, inherited from the conversion workflow's
  OCR decision.
- ~~What the app tells a user who selects a PDF~~ — **decided**: convert it
  first. Selecting a PDF shows why it cannot be rewritten in place and points at
  the conversion workflow (`anonymization.pdfNotice`), rather than listing it as
  one more unsupported extension.
