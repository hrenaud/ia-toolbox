---
"ia-toolbox": minor
---

feat(anonymization): ask once per value, with a type the user can correct

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
