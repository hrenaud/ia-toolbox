# Project guidance

## Product scope

Build a graphical desktop application for non-technical users on macOS and Windows. Linux is not a priority. The app must not require users to open a terminal or use a command line.

The app currently has two independent workflows:

1. Convert supported files to Markdown with Microsoft's MarkItDown.
2. Anonymize supported Office files with Presidio.

Keep these workflows modular so future features can be added without coupling their formats, UI flow, or processing logic. Show each workflow only the formats it actually supports. Use MarkItDown's available converters rather than adding unrelated formats. OpenDocument files, including ODT, are not supported for now; state this clearly in the README.

## Product decisions

- Use Tauri 2 with React and TypeScript for the desktop application.
- Package the Python processing engine as an internal component. It runs in the background and is never exposed as a terminal to users.
- Support single-file and batch processing.
- Process documents locally. Never send document contents to a remote service.
- The app must remain usable offline after installation. Internet access may be used to download the optional OCR model or application updates.
- Provide French and English UI translations. Detect the system language on first launch, and let users choose and keep a language override.
- Provide System, Light, and Dark appearance settings. Follow the OS appearance by default and remember a manual override.
- Build and publish macOS and Windows releases from CI/CD to GitHub Releases. Sign the macOS application in CI/CD; Windows application packages remain unsigned initially. Sign updater artifacts for verification on both platforms and keep signing keys in CI/CD secrets.
- Keep the app buildable locally for development and pre-release testing on macOS and Windows. Document local build and packaging checks; local builds must not require release-signing secrets.
- Provide in-app updates from GitHub Releases. Make update checks and downloads understandable and user-controlled.

## Conversion workflow

- Use MarkItDown's supported converters and optional dependencies. Keep its actual format list distinct from the anonymization format list.
- Do not claim support for a format unless the installed converter can process it.
- OCR is optional. Offer a lightweight local model for download during installation, show the model's minimum system requirements before download, and allow users to configure another local OCR engine or leave OCR disabled.
- OCR must not introduce a remote document-processing dependency.

## Anonymization workflow

- Initial document formats: DOCX, XLSX, and PPTX.
- Use Presidio for detection and anonymization, with French and English support configured and tested.
- Create an anonymized copy; never overwrite the source document. Preserve formatting as much as possible and report limitations or failures clearly.
- Let users review detected entities before producing output, including in batch workflows.
- Offer Presidio's Replace, Mask, Redact, Hash, and Encrypt operators. Recommend Replace in the UI without forcing it. Explain operator choices in plain language.
- Use only local recognizers, models, and processing. Do not depend on cloud-based surrogate generation.

## Interface and accessibility

- Design for non-technical users: clear workflow entry points, plain-language labels, visible progress, useful recovery steps, and clear success or error states.
- Support keyboard operation and assistive technologies. Do not communicate status or meaning through color alone.
- Keep French and English strings in translation resources, not embedded in UI components.
- Make offline status, optional model installation, and update connectivity clear without interrupting local processing.

## Engineering practices

- Keep UI, Tauri/Rust integration, and Python document processing behind explicit interfaces. Validate inputs at each boundary and return actionable errors rather than raw tracebacks.
- Treat documents as sensitive data. Avoid logging document contents, detected personal data, or secrets. Clean temporary files when processing ends.
- Verify current upstream documentation before relying on MarkItDown, Presidio, Tauri, or updater APIs.
- Keep dependencies and bundled models limited to what the enabled workflows need. Make optional, large models opt-in and explain their disk and system requirements.
- Add tests for supported-format declarations, single and batch processing, anonymization operators, original-file preservation, language selection, theme selection, and failure handling as those areas are implemented.
- Before completion, run the repository's relevant format, lint, type-check, test, and build commands. Report any checks that could not run.
