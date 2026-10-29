/**
 * Unit tests for build-local.mjs exported functions.
 * Run with: npx vitest run scripts/build-local.test.mjs
 */

import { describe, it, expect } from "vitest";
import { commandExists, getSidecarFilename } from "./build-local.mjs";

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
