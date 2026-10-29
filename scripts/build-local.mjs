#!/usr/bin/env node
/**
 * Build script for local macOS/Windows desktop packaging.
 *
 * Detects the current OS/architecture, builds the Python worker with PyInstaller,
 * places the sidecar in Tauri's configured location with target-triple suffix,
 * and invokes `tauri build`.
 *
 * Usage: node scripts/build-local.mjs
 */

import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");
const pythonDir = path.join(projectRoot, "python");
const tauriDir = path.join(projectRoot, "src-tauri");
const binariesDir = path.join(tauriDir, "binaries");

/**
 * Execute a shell command and return output, or throw with a clear error
 * showing actual stderr output.
 */
function run(command, description) {
  try {
    return execSync(command, {
      cwd: projectRoot,
      encoding: "utf-8",
      stdio: ["pipe", "pipe", "pipe"],
    }).trim();
  } catch (error) {
    console.error(`\n❌ ${description} failed:`);
    if (error.stderr) {
      console.error(error.stderr);
    }
    throw error;
  }
}

/**
 * Execute a command with output visible to the user.
 */
function runVerbose(command, description) {
  try {
    execSync(command, {
      cwd: projectRoot,
      stdio: "inherit",
    });
  } catch (error) {
    console.error(`\n❌ ${description} failed`);
    throw error;
  }
}

/**
 * Check if a command is available (cross-platform).
 * On Windows, uses 'where'; on other systems, uses 'command -v'.
 */
export function commandExists(cmd) {
  const isWindows = process.platform === "win32";
  const checkCmd = isWindows ? `where ${cmd}` : `command -v ${cmd}`;
  try {
    execSync(checkCmd, { stdio: "ignore", shell: true });
    return true;
  } catch {
    return false;
  }
}

/**
 * Compute the sidecar filename for a given target triple and platform.
 * Returns a string like "document-worker-aarch64-apple-darwin" or
 * "document-worker-x86_64-pc-windows-msvc.exe".
 */
export function getSidecarFilename(targetTriple, platform = process.platform) {
  const ext = platform === "win32" ? ".exe" : "";
  return `document-worker-${targetTriple}${ext}`;
}

/**
 * Build the PyInstaller invocation for the packaged worker.
 *
 * `--group build` is required: PyInstaller sits in the `build` dependency group
 * of python/pyproject.toml, and a plain `uv run` syncs only the default groups,
 * which would uninstall it.
 */
export function getPyInstallerCommand(pythonProjectDir) {
  return `uv run --project ${pythonProjectDir} --group build pyinstaller --clean --distpath python/dist python/packaging/worker.spec`;
}

/**
 * Detect the Rust target triple for the current host.
 * Returns a string like "aarch64-apple-darwin" or "x86_64-pc-windows-msvc".
 */
function getTargetTriple() {
  try {
    return run("rustc --print host-tuple", "Detecting target triple");
  } catch {
    console.error("❌ Rust toolchain not found");
    console.error("Please install Rust from https://rustup.rs/");
    process.exit(1);
  }
}

/**
 * Check prerequisites: rustc, node/pnpm, uv.
 */
function checkPrerequisites() {
  console.log("Checking prerequisites...");
  const required = [
    ["rustc", "https://rustup.rs/"],
    ["pnpm", "https://pnpm.io/installation"],
    ["uv", "https://docs.astral.sh/uv/getting-started/installation/"],
  ];
  for (const [cmd, url] of required) {
    if (!commandExists(cmd)) {
      console.error(`\n❌ ${cmd} not found on PATH`);
      console.error(`Please install from: ${url}`);
      process.exit(1);
    }
  }
  console.log("✓ All prerequisites found");
}

/**
 * Build the Python worker with PyInstaller.
 * Returns the path to the generated binary.
 */
function buildWorker() {
  console.log("\nBuilding Python worker...");
  const ext = process.platform === "win32" ? ".exe" : "";
  const binaryName = `document-worker${ext}`;

  runVerbose(
    getPyInstallerCommand(pythonDir),
    "Building Python worker with PyInstaller",
  );

  const builtBinary = path.join(pythonDir, "dist", binaryName);
  if (!fs.existsSync(builtBinary)) {
    throw new Error(
      `PyInstaller did not produce expected binary at ${builtBinary}`,
    );
  }
  console.log(`✓ Worker built at ${builtBinary}`);
  return builtBinary;
}

/**
 * Place the sidecar binary in Tauri's configured location with target-triple suffix.
 * Uses Node.js fs to work cross-platform.
 */
function placeSidecar(binaryPath, targetTriple) {
  console.log("\nPlacing sidecar binary...");

  // Ensure binaries directory exists using Node.js
  fs.mkdirSync(binariesDir, { recursive: true });

  // Determine sidecar filename
  const sidecarName = getSidecarFilename(targetTriple);
  const sidecarPath = path.join(binariesDir, sidecarName);

  // Copy binary using Node.js
  try {
    fs.copyFileSync(binaryPath, sidecarPath);
    // Make executable on Unix-like systems
    if (process.platform !== "win32") {
      fs.chmodSync(sidecarPath, 0o755);
    }
    console.log(`✓ Sidecar placed at ${sidecarPath}`);
  } catch (error) {
    console.error(`Failed to place sidecar binary at ${sidecarPath}`);
    throw error;
  }

  return sidecarPath;
}

/**
 * Invoke Tauri build command.
 */
function buildTauri() {
  console.log("\nBuilding Tauri application...");
  runVerbose("pnpm tauri build", "Tauri build");
  console.log("✓ Tauri build complete");
}

/**
 * Main entry point.
 */
async function main() {
  // Parse command-line arguments
  const args = process.argv.slice(2);
  const devOnly = args.includes("--dev");

  try {
    checkPrerequisites();
    const targetTriple = getTargetTriple();
    console.log(`✓ Target triple: ${targetTriple}`);

    const builtBinary = buildWorker();
    placeSidecar(builtBinary, targetTriple);

    if (!devOnly) {
      buildTauri();

      console.log("\n✅ Build complete!");
      console.log("\nGenerated application:");
      if (process.platform === "darwin") {
        console.log(
          `  macOS: src-tauri/target/release/bundle/macos/IA Toolbox.app`,
        );
      } else if (process.platform === "win32") {
        console.log(
          `  Windows: src-tauri/target/release/bundle/msi/IA Toolbox*.msi`,
        );
      }
    } else {
      console.log("\n✅ Worker sidecar ready for development");
    }
  } catch {
    process.exit(1);
  }
}

// Only run main if this script is invoked directly, not when imported for testing
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
