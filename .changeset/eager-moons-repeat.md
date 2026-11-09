---
"ia-toolbox": patch
---

fix(anonymization): complete a name the model stopped halfway through

The French model sometimes tags the first name and leaves the surname out. In
`relire avec Sophie Marchand` it returned `Sophie` alone, so the review screen
offered half a name and the anonymized copy kept `Marchand`.

A detection of a single word now takes the capitalised word right after it.
Three limits keep it from swallowing ordinary words: a span the model already
read as two words is left alone, only one word is taken so a job title after a
full name stays out, and the word has to follow a single space and not be a
stop word, so a capital opening the next sentence is out too.

On the sample report that is 43 spans over 33 rows, 2 of them doubtful.
