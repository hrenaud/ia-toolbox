---
"ia-toolbox": minor
---

feat(anonymization): review what was found, then create the anonymized copy

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
