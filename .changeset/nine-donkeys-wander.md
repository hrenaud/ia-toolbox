---
"ia-toolbox": patch
---

fix(anonymization): detect French dates, and read code blocks and comments

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
