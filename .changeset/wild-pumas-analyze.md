---
"ia-toolbox": minor
---

feat(anonymization): expose analysis and anonymization over the worker protocol

The anonymization engine is now reachable: `list_anonymization_formats` returns
the formats that can actually be rewritten, `analyze` reports the personal data
a document contains without writing anything, and `anonymize` writes a copy
replacing only the detections the user kept.

Analysis and anonymization are two separate calls because the user decides
between them. The document is read again on the second call, so a document
edited while it was under review is refused rather than producing a copy of
content that no longer exists. The copy is named after the source, never
overwrites an existing file, and the source is never written to.
