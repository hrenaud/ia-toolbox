import { beforeEach, expect, it, vi } from "vitest";

const start = vi.fn();
vi.mock("./sidecarClient", () => ({
  SidecarClient: {
    start: () => start(),
  },
}));

/** A client that reports whether it was stopped, and when. */
function fakeClient(stop: () => Promise<void> = () => Promise.resolve()) {
  return { stop: vi.fn(stop) };
}

/**
 * A fresh copy of the module under test.
 *
 * The shared client is module state on purpose — one worker for the whole app
 * — so each test needs its own copy or it inherits the previous one's worker.
 */
async function freshModule() {
  vi.resetModules();
  return import("./sharedClient");
}

beforeEach(() => {
  vi.clearAllMocks();
});

it("hands the same worker to every caller", async () => {
  const client = fakeClient();
  start.mockResolvedValue(client);
  const { getClient } = await freshModule();

  const [first, second] = await Promise.all([getClient(), getClient()]);

  expect(first).toBe(client);
  expect(second).toBe(client);
  // Two processes would load the detection models twice for nothing.
  expect(start).toHaveBeenCalledTimes(1);
});

it("never hands out a worker that is being stopped", async () => {
  // Stopping is not instantaneous: the kill is a round trip to the OS. A page
  // asking for the worker during that window must not be given the dying one,
  // or its first request fails with a transport error it cannot explain.
  let finishStop = () => {};
  const stopping = fakeClient(
    () =>
      new Promise<void>((resolve) => {
        finishStop = resolve;
      }),
  );
  const replacement = fakeClient();
  start.mockResolvedValueOnce(stopping).mockResolvedValueOnce(replacement);
  const { getClient, stopClient } = await freshModule();

  await getClient();
  const stopped = stopClient();
  const next = await getClient();
  finishStop();
  await stopped;

  expect(next).toBe(replacement);
});

it("starts a new worker after a stop that failed", async () => {
  const failing = fakeClient(() => Promise.reject(new Error("kill failed")));
  const replacement = fakeClient();
  start.mockResolvedValueOnce(failing).mockResolvedValueOnce(replacement);
  const { getClient, stopClient } = await freshModule();

  await getClient();
  await expect(stopClient()).rejects.toThrow();

  // A worker we could not kill is still a worker we told to fail: handing it
  // back would answer every later request with the same transport error.
  expect(await getClient()).toBe(replacement);
});

it("stops nothing when no worker was ever started", async () => {
  const { stopClient } = await freshModule();

  await expect(stopClient()).resolves.toBeUndefined();
  expect(start).not.toHaveBeenCalled();
});
