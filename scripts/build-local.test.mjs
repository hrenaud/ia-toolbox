/**
 * Unit tests for build-local.mjs exported functions.
 * Run with: npx vitest run scripts/build-local.test.mjs
 */

import { fileURLToPath } from "node:url";

import { describe, it, expect } from "vitest";
import {
  commandExists,
  getPyInstallerCommand,
  getSidecarFilename,
  isDirectInvocation,
} from "./build-local.mjs";

// This guard decides whether the script does anything at all. When it is wrong
// the script exits 0 having built nothing, and the failure only surfaces much
// later, as a Tauri bundle complaining about a missing sidecar — which is
// exactly how it was found, on a release build.
//
// Both cases are derived from this module's own path rather than written as
// literals. No path literal can be portable here: pathToFileURL is the thing
// under test and it is platform-dependent: it resolves its argument first, so
// "/Users/dev/x.mjs" yields "file:///Users/dev/x.mjs" on macOS but picks up the
// runner's current drive letter on Windows.
// Deriving the paths sidesteps that, and on the Windows runner the first case
// is what catches a guard that concatenates onto "file://" instead of
// converting.
describe("isDirectInvocation", () => {
  const thisScript = fileURLToPath(import.meta.url);

  it("recognises this module's own invocation", () => {
    expect(isDirectInvocation(import.meta.url, thisScript)).toBe(true);
  });

  it("rejects a different module", () => {
    expect(
      isDirectInvocation(
        import.meta.url,
        thisScript.replace("build-local.test.mjs", "other.mjs"),
      ),
    ).toBe(false);
  });
});

describe("getPyInstallerCommand", () => {
  // PyInstaller lives in the `build` dependency group, which `uv` does not
  // install by default. Without `--group build` a fresh checkout — or a CI
  // runner — resolves no `pyinstaller` and the worker build fails.
  it("requests the build dependency group", () => {
    expect(getPyInstallerCommand("/repo/python")).toContain("--group build");
  });

  it("runs the packaging spec through uv in the python project", () => {
    const command = getPyInstallerCommand("/repo/python");
    expect(command).toContain("uv run --project /repo/python");
    expect(command).toContain("python/packaging/worker.spec");
  });

  it("keeps PyInstaller output out of the Vite dist directory", () => {
    expect(getPyInstallerCommand("/repo/python")).toContain(
      "--distpath python/dist",
    );
  });
});

describe("getSidecarFilename", () => {
  it("should produce macOS filename without .exe extension", () => {
    const filename = getSidecarFilename("aarch64-apple-darwin", "darwin");
    expect(filename).toBe("document-worker-aarch64-apple-darwin");
  });

  it("should produce x86_64 macOS filename", () => {
    const filename = getSidecarFilename("x86_64-apple-darwin", "darwin");
    expect(filename).toBe("document-worker-x86_64-apple-darwin");
  });

  it("should produce Windows filename with .exe extension", () => {
    const filename = getSidecarFilename("x86_64-pc-windows-msvc", "win32");
    expect(filename).toBe("document-worker-x86_64-pc-windows-msvc.exe");
  });

  it("should produce Windows filename for aarch64", () => {
    const filename = getSidecarFilename("aarch64-pc-windows-msvc", "win32");
    expect(filename).toBe("document-worker-aarch64-pc-windows-msvc.exe");
  });

  it("should handle Linux target triple", () => {
    const filename = getSidecarFilename("x86_64-unknown-linux-gnu", "linux");
    expect(filename).toBe("document-worker-x86_64-unknown-linux-gnu");
  });

  it("should use current platform when not specified", () => {
    // This should use process.platform
    const filename = getSidecarFilename("aarch64-apple-darwin");
    // Just verify it doesn't throw and has expected prefix
    expect(filename).toContain("document-worker-aarch64-apple-darwin");
  });
});

describe("commandExists", () => {
  it("should find common system commands", () => {
    // Node itself should always exist in this environment
    expect(commandExists("node")).toBe(true);
  });

  it("should return false for non-existent commands", () => {
    expect(commandExists("definitely-not-a-real-command-xyz123")).toBe(false);
  });
});
