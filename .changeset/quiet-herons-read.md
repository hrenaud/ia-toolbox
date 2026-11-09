---
"ia-toolbox": patch
---

fix(anonymization): read the document in one language, and report whole addresses

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
