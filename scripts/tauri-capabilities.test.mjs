/**
 * The window capability, checked against what the frontend actually calls.
 *
 * A command the capability does not grant is rejected at the IPC boundary, at
 * runtime, in the packaged app only — there is no build error and no warning.
 * Whatever the call site does with the rejection is all the user sees, and a
 * listener registration that fails silently leaves a feature that simply never
 * reacts.
 *
 * Only commands with no visible error path are asserted here. The dialog and
 * shell permissions surface their own failures loudly enough.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const repoRoot = process.cwd();

function readJson(relativePath) {
  return JSON.parse(readFileSync(join(repoRoot, relativePath), "utf8"));
}

describe("main window capability", () => {
  const capability = readJson("src-tauri/capabilities/default.json");
  const granted = capability.permissions.map((permission) =>
    typeof permission === "string" ? permission : permission.identifier,
  );

  // The drop zone of the conversion page gets its paths from
  // getCurrentWebview().onDragDropEvent, which is a wrapper over four
  // core:event listen calls. Without these the registration is rejected, the
  // page logs to a console nobody has open, and dropping a file onto the zone
  // does nothing at all while the file picker next to it keeps working.
  it("lets the webview listen for native drag and drop", () => {
    expect(granted).toSatisfy((identifiers) =>
      ["core:default", "core:event:default", "core:event:allow-listen"].some(
        (identifier) => identifiers.includes(identifier),
      ),
    );
    expect(granted).toSatisfy((identifiers) =>
      ["core:default", "core:event:default", "core:event:allow-unlisten"].some(
        (identifier) => identifiers.includes(identifier),
      ),
    );
  });
});
