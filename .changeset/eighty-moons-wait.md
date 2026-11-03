---
"ia-toolbox": patch
---

fix(anonymization): ask once per value and rank the doubtful ones last

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
