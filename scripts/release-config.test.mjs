/**
 * Invariants of the Changesets-driven release, checked on the files themselves.
 *
 * Two of the three ways this pipeline can break are silent. A version that
 * drifts still builds, and still produces an installer — one labelled with the
 * wrong version. A private package that Changesets is not told to version is
 * skipped without an error, so `changeset version` reports success and bumps
 * nothing. Neither shows up in a green build, which is why they are asserted
 * here rather than left to a release that nobody is watching closely.
 *
 * The workflow YAML is not covered: no parser is installed, and adding one for
 * a test would widen the dependency closure this project keeps deliberately
 * narrow. It is verified by an actual run on GitHub Actions.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// Vitest rewrites `import.meta.url`, so the repository root comes from the
// project root it already runs in rather than from this file's own location.
const repoRoot = process.cwd();

function read(relativePath) {
  return readFileSync(join(repoRoot, relativePath), "utf8");
}

function readJson(relativePath) {
  return JSON.parse(read(relativePath));
}

describe("application version", () => {
  // Changesets only ever writes package.json. Before this pipeline existed the
  // repository carried three independent "0.1.0" strings, so a bump would have
  // left the bundled app reporting the previous version indefinitely.
  it("is single-sourced from package.json", () => {
    const tauriConfig = readJson("src-tauri/tauri.conf.json");

    expect(tauriConfig.version).toBe("../package.json");
  });

  it("is a concrete version in package.json", () => {
    const manifest = readJson("package.json");

    expect(manifest.version).toMatch(/^\d+\.\d+\.\d+/);
  });

  // Tauri falls back to Cargo.toml only when tauri.conf.json sets no version.
  // A literal version left in the manifest is therefore dead but misleading:
  // the next reader has no way to tell which of the two the bundle used.
  it("is not duplicated as a literal in the Tauri crate manifest", () => {
    const declared = read("src-tauri/Cargo.toml").match(
      /^version\s*=\s*"([^"]+)"/m,
    );

    expect(declared?.[1]).toBe("0.0.0");
  });
});

describe("changesets configuration", () => {
  // The app is `"private": true`, and by default Changesets neither versions
  // nor tags private packages. Left at the default the release PR would bump
  // nothing and no tag would ever be pushed, with no error anywhere.
  it("opts the private package in to versioning and tagging", () => {
    const config = readJson(".changeset/config.json");

    expect(config.privatePackages).toMatchObject({ version: true, tag: true });
  });

  // The release workflow triggers on `v*`. Changesets uses `v<version>` only
  // for a single-package repository; introducing a workspace would switch the
  // format to `<name>@<version>` and the trigger would stop matching.
  it("keeps the repository single-package so tags stay v-prefixed", () => {
    const manifest = readJson("package.json");

    expect(manifest.workspaces).toBeUndefined();
  });
});

describe("macOS signing entitlements", () => {
  // The worker is a PyInstaller onefile binary: it unpacks its own libraries
  // into a temporary directory and dlopens them at startup. Tauri signs it with
  // the hardened runtime, which notarization requires, and those unpacked
  // libraries carry the signature PyInstaller gave them rather than this team's.
  // Library validation then refuses to map them and the worker dies before it
  // reads a single request.
  //
  // Nothing catches this short of launching a signed bundle: an unsigned local
  // build has no hardened runtime, and CI only checks that the bundle was
  // produced. It shipped in v0.2.1, where every format the app offers failed to
  // load.
  it("grants the worker the library validation exemption it needs", () => {
    const tauriConfig = readJson("src-tauri/tauri.conf.json");
    const entitlementsPath = tauriConfig.bundle?.macOS?.entitlements;

    expect(entitlementsPath).toBeDefined();
    expect(read(join("src-tauri", entitlementsPath))).toContain(
      "com.apple.security.cs.disable-library-validation",
    );
  });
});
