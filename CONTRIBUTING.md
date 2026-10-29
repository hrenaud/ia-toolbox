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

| File                            | Trigger                   | What it does                                                              |
| ------------------------------- | ------------------------- | ------------------------------------------------------------------------- |
| `.github/workflows/ci.yml`      | push/PR to `main`, manual | Runs the quality gate and the Rust checks on macOS and Windows            |
| `.github/workflows/release.yml` | tag matching `v*`, manual | Builds bundles for three targets and publishes a **draft** GitHub Release |

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

### Cutting a release

The version appears in four files and they must agree, because Tauri reads its own:

- `package.json`
- `src-tauri/tauri.conf.json` ← the one Tauri uses for the bundle
- `src-tauri/Cargo.toml`
- `python/pyproject.toml`

Bump all four, commit, then tag:

```bash
git tag v0.2.0
git push origin v0.2.0
```

The release workflow builds `aarch64-apple-darwin` (on `macos-latest`), `x86_64-apple-darwin` (on
`macos-15-intel`) and `x86_64-pc-windows-msvc`, then attaches the bundles to a draft release.
Review it and publish manually.

Each target needs a runner of its own architecture: PyInstaller cannot cross-compile, and
`scripts/build-local.mjs` names the sidecar after the **host** triple while Tauri looks it up by the
**build** target. A mismatch fails the bundle step.

### Secrets

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
