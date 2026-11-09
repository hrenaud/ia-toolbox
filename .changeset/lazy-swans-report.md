---
"ia-toolbox": patch
---

fix(anonymization): leave Markdown syntax out of what is analyzed

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
