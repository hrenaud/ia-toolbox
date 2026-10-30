# Binary test fixtures

Fixtures in this project are normally built programmatically, in the test module that uses them —
see the docstring of `test_conversion_e2e.py`. These three files are the documented exception.

## Why they are committed

No library in the worker's dependency closure can produce an encrypted Office document, and adding
one for a fixture would widen the closure the project deliberately keeps narrow. The alternative was
a hand-built compound file, which proves only that the detection agrees with the author's mental
model of MS-OFFCRYPTO — not that it recognises what Word, Excel and PowerPoint actually write. These
files close that gap, and they caught a real mistake: the first `.xlsx` dropped in for testing was
protected against structural editing rather than encrypted, which is a different format and must
keep converting.

| File                      | Saved by   | Protection                |
| ------------------------- | ---------- | ------------------------- |
| `password-protected.docx` | Word       | Password required to open |
| `password-protected.xlsx` | Excel      | Password required to open |
| `password-protected.pptx` | PowerPoint | Password required to open |

The password is `ia-tools`. Nothing reads it: detection recognises the compound-file wrapper without
ever attempting to decrypt. It is recorded only so a future contributor can confirm that a fixture
really is protected rather than merely damaged.

## Provenance

These documents are unfilled Office templates: they carry no content beyond the template itself,
and the project owner confirmed they are shareable. They are committed encrypted, so nothing is
extractable from the repository in any case. A replacement only needs to be a real encrypted
package — that is all the tests require.

`password-protected.pptx` is 628 KB and accounts for most of this directory. A smaller deck would
serve the tests equally well if repository size becomes a concern.
