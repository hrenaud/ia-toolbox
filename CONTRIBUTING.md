# Contributing to IA Toolbox

IA Toolbox converts documents to Markdown entirely on the user's machine. That constraint shapes
every other rule in this document: if a change would send document contents to a remote service, it
does not belong here, however convenient it is.

- [Development setup](#development-setup)
- [Running the app](#running-the-app)
- [Testing](#testing)
- [Architecture boundaries](#architecture-boundaries)
- [Commits and pull requests](#commits-and-pull-requests)
- [GitHub configuration](#github-configuration)

## Development setup

### Prerequisites

| Tool                      | Version                  | Notes                                             |
| ------------------------- | ------------------------ | ------------------------------------------------- |
| Node.js                   | `^22.21.1` or `>=24.0.0` | Node 23 is excluded; locked deps do not accept it |
| pnpm                      | 12.4.2                   | Pinned via `packageManager` in `package.json`     |
| Rust                      | 1.70+                    | https://rustup.rs/                                |
| uv                        | recent                   | Manages the Python 3.11–3.13 worker environment   |
| Xcode Command Line Tools  | —                        | macOS only: `xcode-select --install`              |
| Visual Studio Build Tools | —                        | Windows only                                      |

macOS and Windows are the supported platforms. Linux is not a target.

### Install

```bash
pnpm install
uv sync --project python
```

`uv sync` installs the default dependency groups, which is everything the tests need. Packaging
additionally needs PyInstaller, which lives in the `build` group:

```bash
uv sync --project python --group build
```

You do not have to run that by hand — `scripts/build-local.mjs` passes `--group build` to `uv run`
itself, so `pnpm app:build` works from a plain checkout. The explicit command is only useful if you
want the tool on your PATH for debugging.

## Running the app

```bash
pnpm app:dev
```

This builds the Python worker, places it where Tauri expects the sidecar, and opens the Tauri
window. Two scripts are worth knowing separately:

| Script            | What it does                                                                 |
| ----------------- | ---------------------------------------------------------------------------- |
| `pnpm dev:worker` | Builds the worker with PyInstaller and installs the sidecar. No Tauri build. |
| `pnpm app:build`  | Same, then runs `pnpm tauri build` to produce a distributable bundle.        |

`pnpm app:build` is the full packaging path despite the name — it is `pnpm build:worker`, which
runs `scripts/build-local.mjs` end to end. Bundles land in:

- macOS: `src-tauri/target/release/bundle/macos/IA Toolbox.app`
- Windows: `src-tauri/target/release/bundle/msi/IA Toolbox*.msi`

Local builds never require release-signing secrets. If you find yourself needing one to build, that
is a bug.

## Testing

### Write the test first

This repository is test-driven. Create or update the test, watch it fail for the reason you expect,
then write the implementation. A test that passes before the fix exists is not evidence of anything
— the project has already shipped two rounds of tests that asserted nothing and masked broken
features.

Specifically, avoid these failure modes, all of which have happened here:

- **Restating the value under test.** A contrast test holding its own copies of the hex colours
  asserts arithmetic, not the stylesheet. `src/app/contrast.test.ts` reads the declared values out
  of the CSS for exactly this reason.
- **Tests that skip themselves.** A conversion test that catches `ImportError` and skips will go
  green on precisely the environment where the dependency is missing. Parametrise from the real
  catalog and fail if a declared format has no fixture.
- **Verifying only the easy case.** Checking `.csv` and stopping hid five formats whose readers were
  not installed at all.
- **Fixtures built from the same assumption as the code.** A hand-built binary fixture and the
  parser that reads it share one mental model, so both can be wrong together and still agree. The
  encryption detection was written against hand-built compound files, then checked against documents
  Word, Excel and PowerPoint actually saved — which is what revealed that "protected" has two
  unrelated meanings.

### Fixtures

Build fixtures programmatically inside the test module, as `test_conversion_e2e.py` does for all 16
declared formats. Keeping them in code makes them reviewable and keeps binaries out of the history.

`python/tests/fixtures/` is the one exception, and it is documented in its own README: no library in
the dependency closure can produce an encrypted Office document, so the only way to test against
what Office writes is to commit three such files. Do not grow this directory for a case a writer
could cover.

### The gate

Everything below must pass before you open a pull request. CI runs the same set on macOS and
Windows.

```bash
pnpm typecheck
pnpm test -- --run
pnpm lint
pnpm format:check
pnpm build
uv run --project python ruff check python/src python/tests
uv run --project python pytest -q
```

Rust is checked separately:

```bash
cd src-tauri
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
```

`cargo` needs the sidecar to exist, because `tauri.conf.json` declares it under `externalBin`. Run
`pnpm dev:worker` first, or create an empty placeholder at
`src-tauri/binaries/document-worker-$(rustc --print host-tuple)` (plus `.exe` on Windows) if you
only want a compile check.

### What the automated suite does not cover

Be honest about these in your pull request rather than implying broader coverage:

- The UI tests run under jsdom. Keyboard-only operation and screen-reader announcements on a real
  build still need a manual pass.
- Launching a packaged bundle and converting a document through the GUI — including confirming that
  no terminal window appears on Windows — is manual.
- One protocol test is Windows-only and skips on macOS.

## Architecture boundaries

### No remote services

Document contents must not leave the machine. This is not a preference; it is the product.

In practice the trap is transitive dependencies. MarkItDown is pinned with an explicit extras list:

```
markitdown[docx,pdf,pptx,xls,xlsx]==0.1.6
```

**Do not change this to `markitdown[all]`.** `[all]` pulls in `azure-ai-contentunderstanding`,
`azure-ai-documentintelligence` and `azure-identity` — remote document-understanding services —
along with audio and YouTube transcription that no supported format needs. If you add a format, add
the one extra it requires and verify the resulting dependency closure contains no cloud SDK.

`python/tests/test_dependency_closure.py` enforces this: it walks the installed distributions and
fails on any Azure, AWS, Google Cloud, model-provider or speech client. That check — not an
"offline" test run — is what makes processing local. A passing offline run would only prove that no
call happened on that run; an empty closure proves none can.

OpenDocument formats, including `.odt`, are deliberately unsupported. OCR and image description are
out of scope, and must not be added by calling out to a service.

### The worker protocol

The frontend talks to the packaged Python worker over JSON lines on stdin/stdout. Requests carry
`input_path` and `output_directory` as **top-level keys** — not nested under a `payload` object.
Nesting them yields an `invalid_path` error, which is an unhelpfully indirect symptom.

Two invariants protect this channel:

- **Output isolation.** `silence_process_output()` redirects file descriptors 1 and 2 to the null
  device (and calls `SetStdHandle` on Windows) _before_ any conversion library is imported.
  MarkItDown's ONNX Runtime dependency writes to native handles and would otherwise interleave
  bytes into the protocol stream. Never import a conversion library above that call.
- **`console=True` in `python/packaging/worker.spec` is correct.** A PyInstaller windowed binary has
  no stdio at all, which would break the protocol outright. Do not "fix" it. The guarantee that no
  console window appears comes from how Tauri spawns the sidecar on Windows, not from the spec.

### Per-file errors must be specific and translated

Every failure the worker reports carries an `error_code`. The UI translates it through
`conversion.failure.<code>` in `src/app/locales/`, and `src/features/conversion/jobErrors.test.ts`
fails if a code listed in `WORKER_ERROR_CODES` has no French and English string. The worker's own
English `message` is only a fallback for a code the frontend does not know yet.

Resist widening `processing_failed`. Collapsing distinct causes into it is how five formats with
missing readers stayed invisible for a whole task cycle, and it is why a password-protected file
once told users to "check file and folder access" — advice that cannot help, since the file is
readable and the permissions are fine.

A password-protected DOCX/XLSX/PPTX is recognised from its bytes before conversion: MS-OFFCRYPTO
stores the package inside an OLE2 compound file holding an `EncryptedPackage` stream, so the file is
not the ZIP archive its extension promises. The suite's fixtures are hand-built, because no
installed library can produce an encrypted document, but the path is also checked against real files
saved by Word, Excel and PowerPoint in `test_conversion_encrypted_real.py`. In those files
the marker sat near the start (offset 1152, and 8320 in a 643 KB deck), so the head window is what
matches in practice; the tail window covers the layout the format permits but Office does not
produce.

Two boundaries matter here:

- **Encryption is not the same as an editing lock.** Excel's "protect workbook structure" and Word's
  "restrict editing" leave an ordinary ZIP whose content is in the clear; `xl/workbook.xml` simply
  gains a `<workbookProtection … lockStructure="1"/>` element whose hash validates a password rather
  than decrypting anything. Such a file converts, and must keep converting — refusing a document we
  can read would block a legitimate conversion. Only a password demanded _to open_ the file produces
  the compound-file wrapper.
- **`.xls` is excluded on purpose.** Excel 97-2003 is legitimately a compound file, so the magic
  proves nothing there and a protected legacy workbook still reports `processing_failed`.

### Never overwrite user files

Output goes to the selected destination folder using the input file's base name with a `.md`
extension. If that path is taken, pick the next free numbered name (`report (2).md`). Never
overwrite an existing file, and never write to the source.

### Accessibility

Keyboard operation, visible focus, assistive-technology status announcements, and sufficient
contrast are requirements, not polish. No state may be communicated by colour alone.

Colour changes are guarded by `src/app/contrast.test.ts`, which parses `theme.css` and
`ConversionPage.css` and asserts WCAG 2.1 AA ratios: 4.5:1 for normal text, 3:1 for UI component
boundaries. Note that `font-weight: 600` does **not** make small text "large" — WCAG's threshold is
24px, or 18.66px when bold.

`ConversionPage.css` currently hardcodes 28 colours outside the theme system and has no dark-theme
override. Each pair sets `background` and `color` together, so nothing becomes illegible, but it is
a known wart. If you touch those rules, consider lifting them into `theme.css`.

## Commits and pull requests

Semantic commit messages, `<type>(<scope>): <subject>`:

`feat` · `fix` · `docs` · `refactor` · `perf` · `test` · `chore`

Pull request descriptions should say what changed and why, and link related issues. **Do not include
test scenarios in the description** — the tests are in the diff.

Keep changes minimal. No speculative abstractions, no configurability nobody asked for, no error
handling for impossible states.

## GitHub configuration

### Workflows

| File                            | Trigger                                   | What it does                                                                |
| ------------------------------- | ----------------------------------------- | --------------------------------------------------------------------------- |
| `.github/workflows/ci.yml`      | push/PR to `main`, manual                 | Runs the quality gate and the Rust checks on macOS and Windows              |
| `.github/workflows/version.yml` | push to `main`                            | Opens the version pull request, or pushes the release tag and calls release |
| `.github/workflows/release.yml` | called by `version.yml`; `v*` tag; manual | Builds the bundles and publishes a **draft** GitHub Release                 |

CI runs two jobs per OS: `gate` (frontend + Python) and `rust` (fmt, clippy, test). Neither needs
secrets, so they run on pull requests from forks.

### Branch protection

On `main`, require the status checks to pass before merging. Their names are:

```
Quality gate (macos-latest)
Quality gate (windows-latest)
Rust compile check (macos-latest)
Rust compile check (windows-latest)
```

Settings → Branches → Add branch ruleset → require status checks to pass. Also enable "Require
branches to be up to date before merging" so a green check reflects the merged state.

### Changesets

Versions are never bumped by hand. Every pull request that changes something a user can see,
install or run carries a changeset:

```bash
pnpm changeset
```

Pick the bump and describe the change for someone who will never read the diff — the text is copied
verbatim into `CHANGELOG.md`. A pull request with no user-visible effect needs no changeset. CI does
not enforce this, deliberately: a mandatory changeset on a test-only change produces an empty file
that says nothing.

The app is `"private": true`, which Changesets skips entirely by default. `.changeset/config.json`
sets `privatePackages` to `{ "version": true, "tag": true }`; without it `changeset version` would
report success and bump nothing — a silent failure, which is why
`scripts/release-config.test.mjs` asserts it.

### Cutting a release

Nothing to do by hand. Merging a changeset to `main` does not release:

1. `version.yml` sees the pending changeset and opens a **`chore(release): version packages`** pull
   request. It accumulates every changeset merged since the last release and shows the resulting
   `CHANGELOG.md`.
2. Merging that pull request bumps `package.json`, writes `CHANGELOG.md`, deletes the consumed
   changesets and pushes the `v<version>` tag.
3. `version.yml` then calls `release.yml`, which builds the bundles and attaches them to a **draft**
   GitHub Release. Review it and publish manually.

The version PR is the release gate: until it is merged, nothing ships.

**The tag alone does not start the build.** A tag pushed with `GITHUB_TOKEN` does not trigger a
workflow run, so `release.yml` is called directly by `version.yml` via `workflow_call`. Its
`push: tags` trigger still covers a tag pushed by a human. If the hand-off ever fails, the tag is
already on the remote — re-run `release.yml` from Actions → Release → Run workflow with that tag.

#### Where the version lives

`package.json` is the only file with a real version. `src-tauri/tauri.conf.json` sets
`"version": "../package.json"`, which Tauri resolves relative to `src-tauri/`, so the bundle always
matches the tag. `src-tauri/Cargo.toml` is pinned at `0.0.0`: Cargo demands a version, Tauri only
falls back to it when `tauri.conf.json` sets none, and `0.0.0` in a bundle is an obvious regression
rather than a plausible-looking wrong number.

`python/pyproject.toml` is **not** part of this. The worker is an internal package that users never
see a version for; keeping it in sync would be ceremony with no reader.

#### Targets

`release.yml` builds `aarch64-apple-darwin` (on `macos-latest`), `x86_64-apple-darwin` (on
`macos-15-intel`) and `x86_64-pc-windows-msvc`.

Each target needs a runner of its own architecture: PyInstaller cannot cross-compile, and
`scripts/build-local.mjs` names the sidecar after the **host** triple while Tauri looks it up by the
**build** target. A mismatch fails the bundle step.

`x86_64-unknown-linux-gnu` is also built, but as **best-effort only**. Linux is not a supported
platform — see the platform note at the top of this guide — and nobody tests it. The job carries
`continue-on-error`, so its bundle is attached when it builds and ignored when it does not; a broken
Linux job never withholds the macOS and Windows installers.

### Action pinning

Third-party actions are pinned to a full commit SHA with the version in a trailing comment. A
mutable tag like `@v2` can be repointed by whoever controls the action's repository, and the release
job holds the Apple certificate and the updater private key — a compromised tag there is a secret
exfiltration. Let Dependabot or Renovate move the pins.

Actions under `actions/` are GitHub-owned and left on major tags.

### Secrets

The release job declares `environment: release`. Create that environment under Settings →
Environments and add required reviewers: the signing secrets are then only handed to a run someone
approved. Scope the secrets to that environment rather than to the repository.

All of these are optional. Without them the workflow still produces unsigned bundles, which is what
forks and local builds get.

| Secret                                        | Purpose                                                    |
| --------------------------------------------- | ---------------------------------------------------------- |
| `APPLE_CERTIFICATE`                           | base64 of the Developer ID Application `.p12`              |
| `APPLE_CERTIFICATE_PASSWORD`                  | password for that `.p12`                                   |
| `APPLE_SIGNING_IDENTITY`                      | e.g. `Developer ID Application: Name (TEAMID)`             |
| `APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID` | notarization; `APPLE_PASSWORD` is an app-specific password |
| `TAURI_SIGNING_PRIVATE_KEY`                   | updater signing key, from `pnpm tauri signer generate`     |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`          | password for that key                                      |

`GITHUB_TOKEN` is provided by Actions; do not create it.

Windows packages are intentionally unsigned for now.

### Updater: not yet wired

The updater secrets above are plumbed through the workflow, but **they currently produce nothing**.
`tauri-plugin-updater` is not a dependency and `tauri.conf.json` has no `plugins.updater` section,
so no `.sig` artifacts are generated and no client checks for updates. Enabling it means adding the
plugin, declaring the endpoint and the public key in `tauri.conf.json`, and generating a keypair.
Until that happens, treat the updater as unimplemented rather than configured.
