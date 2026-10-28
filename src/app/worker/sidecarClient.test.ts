import { beforeEach, expect, it, vi } from "vitest";
import { SidecarClient } from "./sidecarClient";

const mock = vi.hoisted(() => ({
  stdout: undefined as ((line: string) => void) | undefined,
  close: undefined as (() => void) | undefined,
  error: undefined as (() => void) | undefined,
  write: vi.fn<(...args: string[]) => Promise<void>>(),
  kill: vi.fn<() => Promise<void>>(),
  spawn: vi.fn(),
  sidecar: vi.fn(),
}));

vi.mock("@tauri-apps/plugin-shell", () => ({
  Command: { sidecar: mock.sidecar },
}));

beforeEach(() => {
  vi.resetAllMocks();
  mock.write.mockResolvedValue();
  mock.kill.mockResolvedValue();
  mock.spawn.mockResolvedValue({ write: mock.write, kill: mock.kill });
  mock.sidecar.mockReturnValue({
    stdout: {
      on: (_: string, handler: typeof mock.stdout) => {
        mock.stdout = handler;
      },
    },
    on: (event: string, handler: () => void) => {
      if (event === "close") mock.close = handler;
      if (event === "error") mock.error = handler;
    },
    spawn: mock.spawn,
  });
});

function sent(index = 0) {
  return JSON.parse(mock.write.mock.calls[index][0]);
}

function emit(event: object) {
  mock.stdout?.(JSON.stringify(event));
}

it("spawns only the fixed sidecar and correlates interleaved requests", async () => {
  const client = await SidecarClient.start();
  const progress = vi.fn();
  const discovery = client.request({ operation: "list_formats" });
  const conversion = client.request(
    { operation: "convert", input_path: "/a.txt", output_directory: "/out" },
    progress,
  );
  expect(mock.sidecar).toHaveBeenCalledExactlyOnceWith(
    "binaries/document-worker",
  );
  expect(sent().id).not.toBe(sent(1).id);
  expect(mock.write.mock.calls[0][0]).toMatch(/\n$/);
  expect(sent(1)).toEqual({
    id: expect.any(String),
    operation: "convert",
    input_path: "/a.txt",
    output_directory: "/out",
  });
  emit({ id: sent(1).id, event: "progress", percent: 50 });
  emit({
    id: sent(1).id,
    event: "result",
    status: "success",
    output_path: "/out/a.md",
  });
  emit({
    id: sent().id,
    event: "formats",
    items: [
      { extension: ".txt", label: "Text", requires_optional_component: false },
    ],
  });
  expect(progress).toHaveBeenCalledWith(50);
  expect(await conversion).toMatchObject({ status: "success" });
  expect(await discovery).toMatchObject({ event: "formats" });
  await client.stop();
  expect(mock.kill).toHaveBeenCalledOnce();
});

it("returns structured per-file errors without poisoning later requests", async () => {
  const client = await SidecarClient.start();
  const result = client.request({
    operation: "convert",
    input_path: "/missing.txt",
    output_directory: "/out",
  });
  emit({
    id: sent().id,
    event: "result",
    status: "error",
    error_code: "input_not_found",
    message: "Select an existing file.",
  });
  expect(await result).toMatchObject({ error_code: "input_not_found" });
  const next = client.request({ operation: "list_formats" });
  emit({ id: sent(1).id, event: "formats", items: [] });
  expect(await next).toMatchObject({ items: [] });
});

it.each(["not JSON private", "{}", "null", "[]"])(
  "rejects malformed output safely: %s",
  async (line) => {
    const client = await SidecarClient.start();
    const result = client.request({ operation: "list_formats" });
    const check = expect(result).rejects.toMatchObject({
      code: "invalid_response",
    });
    mock.stdout?.(line);
    await check;
    expect(mock.kill).toHaveBeenCalledOnce();
    await expect(
      client.request({ operation: "list_formats" }),
    ).rejects.toMatchObject({ code: "invalid_response" });
  },
);

it.each([
  { event: "progress", percent: 101 },
  { event: "progress", percent: "50" },
  { event: "result", status: "success" },
  { event: "result", status: "error", message: "private" },
  { event: "formats", items: [{ extension: 42 }] },
  { event: "result", status: "success", output_path: "/out.md" },
])("validates response fields and operation: %j", async (event) => {
  const client = await SidecarClient.start();
  const result = client.request({ operation: "list_formats" });
  const check = expect(result).rejects.toMatchObject({
    code: "invalid_response",
  });
  emit({ id: sent().id, ...event });
  await check;
});

it.each(["close", "error", "stop"])(
  "rejects pending requests on %s",
  async (event) => {
    const client = await SidecarClient.start();
    const pending = client.request({ operation: "list_formats" });
    const check = expect(pending).rejects.toMatchObject({
      code: "worker_stopped",
    });
    if (event === "stop") await client.stop();
    else if (event === "close") mock.close?.();
    else mock.error?.();
    await check;
  },
);

it("sanitizes spawn and write failures", async () => {
  mock.spawn.mockRejectedValueOnce(new Error("private spawn detail"));
  await expect(SidecarClient.start()).rejects.toMatchObject({
    code: "worker_unavailable",
  });
  const client = await SidecarClient.start();
  mock.write.mockRejectedValueOnce(new Error("private path"));
  await expect(
    client.request({ operation: "list_formats" }),
  ).rejects.toMatchObject({ code: "worker_stopped" });
});

it("handles an exit before spawn resolves", async () => {
  mock.spawn.mockImplementationOnce(async () => {
    mock.close?.();
    return { write: mock.write, kill: mock.kill };
  });
  await expect(SidecarClient.start()).rejects.toMatchObject({
    code: "worker_stopped",
  });
});

it("waits for process termination when stopped", async () => {
  let finish!: () => void;
  mock.kill.mockReturnValueOnce(
    new Promise<void>((resolve) => {
      finish = resolve;
    }),
  );
  const client = await SidecarClient.start();
  let stopped = false;
  const stopping = client.stop().then(() => {
    stopped = true;
  });
  await Promise.resolve();
  expect(stopped).toBe(false);
  finish();
  await stopping;
  expect(stopped).toBe(true);
});

it("rejects an uncorrelated event rather than leaving requests pending", async () => {
  const client = await SidecarClient.start();
  const pending = client.request({ operation: "list_formats" });
  const check = expect(pending).rejects.toMatchObject({
    code: "invalid_response",
  });
  emit({ id: crypto.randomUUID(), event: "formats", items: [] });
  await check;
});

it("surfaces a safe stop failure and permits retry", async () => {
  const client = await SidecarClient.start();
  mock.kill.mockRejectedValueOnce(new Error("sensitive process details"));
  await expect(client.stop()).rejects.toMatchObject({
    code: "worker_stop_failed",
    message: "worker_stop_failed",
  });
  await expect(client.stop()).resolves.toBeUndefined();
  expect(mock.kill).toHaveBeenCalledTimes(2);
  await client.stop();
  expect(mock.kill).toHaveBeenCalledTimes(2);
});

it("can stop again after automatic cleanup fails", async () => {
  const client = await SidecarClient.start();
  mock.kill.mockRejectedValueOnce(new Error("sensitive process details"));
  const pending = client.request({ operation: "list_formats" });
  const failed = expect(pending).rejects.toMatchObject({
    code: "invalid_response",
  });
  mock.stdout?.("invalid JSON");
  await failed;
  await expect(client.stop()).resolves.toBeUndefined();
  expect(mock.kill).toHaveBeenCalledTimes(2);
});

it("reports startup cleanup failure without exposing process details", async () => {
  mock.spawn.mockImplementationOnce(async () => {
    mock.close?.();
    return { write: mock.write, kill: mock.kill };
  });
  mock.kill.mockRejectedValueOnce(new Error("sensitive process details"));
  await expect(SidecarClient.start()).rejects.toMatchObject({
    code: "worker_stop_failed",
    message: "worker_stop_failed",
  });
});
