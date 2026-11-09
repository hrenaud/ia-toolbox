# ia-toolbox

## 0.3.0

### Minor Changes

- a9f7dc6: feat(anonymization): review what was found, then create the anonymized copy

  The anonymization workflow now has its screen. Pick documents and an output
  folder, find the personal information they contain, choose what to replace, and
  create a copy in the original format — the source file is never modified.

  Findings are grouped by what they are, so "every email address" is a decision
  the user can make on a document with two hundred detections. Nothing is
  selected at the start and nothing is written before the explicit confirmation,
  which names the file that will be written. Text the format cannot rewrite
  without breaking the document is shown and left as it is, rather than hidden.
  Each document reports its own result: one failure neither stops the batch nor
  hides the copies that were written.

  Confidence is said in words and every state is announced in the page's status
  region, so nothing on the screen is carried by colour alone. Selecting a PDF
  now explains that it has to be converted to Markdown first instead of being
  refused as an unknown format.

- e85b198: feat(anonymization): type a column of a CSV file as a whole

  A column of a table is not prose: every cell in it holds the same kind of
  value, which is a stronger claim than anything a detector can make about one
  cell on its own. So a column whose cells are mostly personal data now gets one
  type, and every one of its cells is replaced.

  That closes a leak. The model found names in six cells of a column and missed
  the seventh; the seventh name stayed in the anonymized copy and was never
  offered for review, and nobody can untick a row that was never shown. And it
  makes the review usable on a table: the column is a single row, named after its
  header and showing its first values, whose menu retypes every cell at once. On
  the sample membership directory, 52 spans become 12 questions instead of ~40.

  Two measurements decide a column and both are required. Fill is how much of a
  cell its detections cover, averaged only over the cells where something was
  found — so it never measures recall, which is the case that has to be accepted.
  Reach is how many non-empty cells hold anything at all. Fill alone accepts a
  column of reference codes with one name in it; reach alone accepts a column of
  free-text comments that each mention somebody. Both thresholds were measured on
  a real file and sit in the middle of the gap.

  CSV and TSV only. Columns inside an Excel workbook are not typed this way: its
  text lives in a shared string table with no notion of a grid, so recognizing a
  column there is a separate piece of work.

- 9eef595: feat(anonymization): ask once per value, with a type the user can correct

  The review screen listed one row per occurrence, grouped under its type. A
  ten-line document produced fifty rows, the same name was asked about eight
  times, and a value two models typed differently was asked about twice, under
  two headings, both claiming high confidence.

  It is now one row per value, whatever the type: the value, a few words of the
  document either side of its first occurrence, where it is, and how many times
  it appears. The type is a proposal in a menu rather than a verdict, and the
  answer applies to every occurrence of that value — it decides the label the
  copy will carry. Values the detector is least sure of stay in the list, under a
  heading at the bottom.

  The language the names were read in is shown above each document's list and can
  be corrected, which reads the document again: names are read by a model for one
  language, so the wrong one gets most of them wrong. The confidence word is no
  longer printed for the types the model guesses at, which all score the same —
  it is kept for the ones a pattern decides, where it still varies.

- a9f7dc6: feat(anonymization): expose analysis and anonymization over the worker protocol

  The anonymization engine is now reachable: `list_anonymization_formats` returns
  the formats that can actually be rewritten, `analyze` reports the personal data
  a document contains without writing anything, and `anonymize` writes a copy
  replacing only the detections the user kept.

  Analysis and anonymization are two separate calls because the user decides
  between them. The document is read again on the second call, so a document
  edited while it was under review is refused rather than producing a copy of
  content that no longer exists. The copy is named after the source, never
  overwrites an existing file, and the source is never written to.

### Patch Changes

- cf5347f: fix(anonymization): read names one line at a time

  A name in the middle of a document went unreported, so it stayed in the
  anonymized copy. `Sophie Marchand`, named in a paragraph between two headings,
  was never offered for replacement, and `Thomas Nguyen` was offered for the line
  that listed him but not for the table cell that named him again.

  The cause was the text handed to the model. A unit's text is not prose: an
  adapter joins a heading, a paragraph and a table row with newlines, and none of
  them ends in a full stop, so the whole unit reads as one run-on sentence. A
  small model given that loses names inside it and takes the headings for people.

  The model now reads one line at a time; the patterns keep the whole unit, since
  a NIR is accepted on the strength of the words introducing it and those can sit
  a line away. On the sample meeting report both missing names are now found and
  the false positives `Lieu`, `Participants`, `Décisions` and `Points` are gone —
  32 spans over 24 rows, 2 of them doubtful, against 34 over 27 with 6 doubtful.

  The README now also states that dates are not detected in French: the French
  model has no date category, so a date is left in the copy even though the type
  menu offers one.

- 6f85241: fix(anonymization): complete a name the model stopped halfway through

  The French model sometimes tags the first name and leaves the surname out. In
  `relire avec Sophie Marchand` it returned `Sophie` alone, so the review screen
  offered half a name and the anonymized copy kept `Marchand`.

  A detection of a single word now takes the capitalised word right after it.
  Three limits keep it from swallowing ordinary words: a span the model already
  read as two words is left alone, only one word is taken so a job title after a
  full name stays out, and the word has to follow a single space and not be a
  stop word, so a capital opening the next sentence is out too.

  On the sample report that is 43 spans over 33 rows, 2 of them doubtful.

- 66dc312: fix(anonymization): ask once per value and rank the doubtful ones last

  A ten-line document produced fifty questions, which made the review screen
  unusable. Three changes, none of which hides anything that was found.

  One value is now one row. Every occurrence of a name already receives the same
  pseudonym, so asking about each occurrence asked the same question again; two
  spellings of one value are one row too, since the labels are assigned ignoring
  case. The row says how many times the value appears, and the count the page
  announces is counted in rows as well.

  A person name or an organization is narrowed to the part of it that carries a
  capital, so `la mairie de Rennes` is reported as `Rennes` and a span with no
  capital at all is dropped. Places are left alone: an address is lowercase and
  still personal data.

  A lone capitalised word opening a line or a heading is the shape the detector
  gets wrong most often. It is still reported — a one-word name in a table cell
  looks the same — but it now sits under a **Less likely** heading at the bottom
  of its type, with a note explaining what to check before ticking it.

  On the sample meeting report this turns fifty questions into twenty-six, with
  nine doubtful ones grouped at the end.

- f643f22: fix(worker): stop the discarded dev mount from claiming the formats failed

  Launching the app in development showed a red "restart the application" banner
  on the conversion page, above the list of formats it had just loaded fine, and
  it disappeared as soon as the workflow was switched.

  StrictMode discards the first mount in development, and the shell's cleanup
  stops the shared worker while that mount's `list_formats` request is still in
  flight. The request rejected, and the page it no longer belonged to set its
  error anyway. Both pages now drop a result that arrives after their mount was
  discarded, the same way the drag-and-drop subscription next to them already
  did.

- dce0ef8: fix(anonymization): leave Markdown syntax out of what is analyzed

  A Markdown file was handed to the detector exactly as written, which cost twice.
  An email address inside a fenced code block was offered for replacement although
  the documentation says code is not analyzed, and the syntax broke the sentences
  around it: `**Lieu :** Nantes, salle Loire` reported `salle` as a person, and a
  table cell came back with its closing pipe inside the value.

  Code blocks, code spans, HTML comments and raw tags are now copied without being
  read, and reported as not analyzed. Heading markers, list bullets, emphasis and
  table pipes are no longer part of what the detector sees or what a replacement
  can touch. A document with nothing selected is copied byte for byte.

  A detection can also no longer run across a line break. One that did wrote the
  replacement into the first block and emptied the second, which deleted a
  heading; such a span is now cut at the break and each half kept.

- 86fdfac: fix(anonymization): detect French dates, and read code blocks and comments

  Three kinds of personal data stayed in the anonymized copy of a French meeting
  report, and the app reported the document as covered.

  Dates were never offered: the French model has no date category, so `2 avril
2026`, `31 mars` and `juin 2026` were left untouched. A pattern anchored on the
  twelve month names now reports them — a day or a year is required, so a bare
  `mars` and the figures in a budget table are still not dates. Which pass keeps
  a result is now decided by the recognizer it came from rather than by its type,
  since the model reports dates too and its results are made in a separate pass.

  Code blocks, inline code spans and comments were copied without being read, so
  two addresses and a name in an export snippet, and a name in an internal review
  note, survived anonymization. Their content is now analyzed and rewritable
  while their delimiters stay untouched: a fence, its info string, backticks and
  `<!--`/`-->` are never part of a span. HTML and XML comments changed the same
  way, and `markup_code_not_analyzed` is now only about `<script>` and `<style>`,
  whose content is a program rather than prose.

  On the sample report that is 43 spans over 34 rows, 2 of them doubtful.

- ade3716: fix(worker): keep the one worker alive when switching between workflows

  Switching from conversion to anonymization opened the page on "could not load
  the formats that can be anonymized". Each page stopped the worker when it was
  left, but the two workflows talk to the **same** process, so leaving one killed
  the process the other was about to use. The app now owns the worker's lifetime
  and no page stops it.

  Two related races are closed on the way: asking for the worker twice before the
  first one has finished starting started two processes, and asking for it while
  it was being stopped handed back a worker already told to fail.

- dce0ef8: fix(anonymization): package the detection models so the installed app can analyze

  In a release build, finding personal information failed with no message at all.
  PyInstaller does not follow `spacy.load("fr_core_news_sm")`, and presidio builds
  its recognizer registry by walking modules, so neither the models nor the
  libraries were in the bundle. The worker started, listed the formats it can
  anonymize, and then died on the first document — silently, because it redirects
  its own output to protect the protocol.

  spaCy, presidio and both language models are now collected by name, and a test
  checks that list against the models the detector actually loads.

- 9eef595: fix(anonymization): read the document in one language, and report whole addresses

  The detector reported the French word `Le` as an organization, split
  `12 rue des Lilas, 44000 Nantes` into three rows, and gave no clue about where
  a value like `Loire` came from. It also ran both language models over every
  document, which is how one name came back as a person and as an organization at
  once.

  A document is now read in one language: it is guessed from the text by counting
  the function words each model knows, can be overridden by the `analyze` request
  and is reported in the result. Only that language's model proposes names;
  patterns such as IBANs and email addresses still run regardless. A lone
  capitalised word that is a function word in the document's language is refused,
  adjacent address components are merged into one detection, postcode included,
  and every detection carries a short excerpt of the text around it so the review
  screen can show the value in context.

## 0.2.2

### Patch Changes

- fa0784d: A file dropped onto the conversion page is added to the list once, not twice.
  The page subscribed to native drag and drop inside the effect that loads the
  format catalog, and read the unsubscribe function synchronously in the cleanup
  even though subscribing is asynchronous — so a cleanup that ran before the
  subscription settled left a second handler attached, and every drop was
  counted by both.
- af37d6e: The macOS app can load its list of supported formats again, and convert files.
  The signed bundle was refusing to start its document worker: notarization
  requires the hardened runtime, under which macOS declined to load the Python
  libraries the worker unpacks at startup because they do not carry this team's
  signature. The worker died silently and every conversion was unavailable. The
  bundle now ships the entitlement that exempts those libraries.
- bafa7c4: Dropping files onto the drop zone of the Markdown conversion page works again.
  The window's capability granted no core permissions, so the page's request to
  listen for native drag and drop events was rejected at the IPC boundary. The
  rejection went to the console and the zone stayed inert, while the file picker
  beside it kept working.

## 0.2.1

### Patch Changes

- dc52d36: The Windows installer is built again. Its build step had been silently doing
  nothing: the script that packages the Python worker decided whether it was being
  run or merely imported by comparing paths in a way that is only ever true on
  macOS and Linux, so on Windows it exited immediately and reported success. The
  bundle then failed on a worker that was never produced, and no Windows installer
  was attached to the release.

## 0.2.0

### Minor Changes

- 3118874: A document that needs a password to open is now reported as password-protected,
  in French and English, instead of as a generic processing failure telling you to
  check file and folder access — advice that could not help, since the file is
  readable and no permission is missing. The original file is left untouched and
  the rest of the batch continues.

  A document that is only locked against editing is not encrypted and still
  converts normally. Legacy `.xls` workbooks are the exception: a protected one is
  reported as unreadable.
