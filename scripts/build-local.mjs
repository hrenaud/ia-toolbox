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
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");
const pythonDir = path.join(projectRoot, "python");
const tauriDir = path.join(projectRoot, "src-tauri");
const binariesDir = path.join(tauriDir, "binaries");

/**
 * Execute a shell command and return output, or throw with a clear error.
 */
function run(command, description) {
  try {
    return execSync(command, {
      cwd: projectRoot,
      encoding: "utf-8",
      stdio: ["pipe", "pipe", "pipe"],
    }).trim();
  } catch (error) {
    console.error(
      `\n❌ ${description} failed. Ensure the following are installed and on your PATH:`,
    );
    throw error;
  }
}

/**
 * Detect the Rust target triple for the current host.
 * Returns a string like "aarch64-apple-darwin" or "x86_64-pc-windows-msvc".
 */
function getTargetTriple() {
  try {
    return run("rustc --print host-tuple", "Detecting target triple");
  } catch {
    console.error("\n❌ Rust toolchain not found");
    console.error("Please install Rust from https://rustup.rs/");
    process.exit(1);
  }
}

/**
 * Check if a command is available on the system PATH.
 */
function checkCommand(cmd, installUrl) {
  try {
    execSync(`which ${cmd}`, { stdio: "ignore" });
    return true;
  } catch {
    console.error(`\n❌ ${cmd} not found on PATH`);
    console.error(`Please install from: ${installUrl}`);
    process.exit(1);
  }
}

/**
 * Check prerequisites: rustc, node/pnpm, uv.
 */
function checkPrerequisites() {
  console.log("Checking prerequisites...");
  checkCommand("rustc", "https://rustup.rs/");
  checkCommand("pnpm", "https://pnpm.io/installation");
  checkCommand("uv", "https://docs.astral.sh/uv/getting-started/installation/");
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

  // Run PyInstaller via uv
  run(
    `uv run --project ${pythonDir} pyinstaller --clean --distpath dist packaging/worker.spec`,
    "Building Python worker with PyInstaller",
  );

  const builtBinary = path.join(pythonDir, "dist", binaryName);
  console.log(`✓ Worker built at ${builtBinary}`);
  return builtBinary;
}

/**
 * Place the sidecar binary in Tauri's configured location with target-triple suffix.
 */
function placeSidecar(binaryPath, targetTriple) {
  console.log("\nPlacing sidecar binary...");

  // Ensure binaries directory exists
  try {
    execSync(`mkdir -p "${binariesDir}"`, { stdio: "ignore" });
  } catch {
    console.error(`Failed to create ${binariesDir}`);
    process.exit(1);
  }

  // Determine file extension
  const ext = process.platform === "win32" ? ".exe" : "";
  const sidecarName = `document-worker-${targetTriple}${ext}`;
  const sidecarPath = path.join(binariesDir, sidecarName);

  // Copy binary to Tauri sidecar location with target triple suffix
  try {
    execSync(`cp "${binaryPath}" "${sidecarPath}"`, { stdio: "inherit" });
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
  run("pnpm tauri build", "Tauri build");
  console.log("✓ Tauri build complete");
}

/**
 * Main entry point.
 */
async function main() {
  try {
    checkPrerequisites();
    const targetTriple = getTargetTriple();
    console.log(`✓ Target triple: ${targetTriple}`);

    const builtBinary = buildWorker();
    placeSidecar(builtBinary, targetTriple);
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
  } catch {
    console.error("\n❌ Build failed");
    process.exit(1);
  }
}

main();
