---
"ia-toolbox": patch
---

fix(anonymization): package the detection models so the installed app can analyze

In a release build, finding personal information failed with no message at all.
PyInstaller does not follow `spacy.load("fr_core_news_sm")`, and presidio builds
its recognizer registry by walking modules, so neither the models nor the
libraries were in the bundle. The worker started, listed the formats it can
anonymize, and then died on the first document — silently, because it redirects
its own output to protect the protocol.

spaCy, presidio and both language models are now collected by name, and a test
checks that list against the models the detector actually loads.
