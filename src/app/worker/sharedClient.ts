import { SidecarClient } from "./sidecarClient";

/**
 * The one worker process, shared by every feature that needs it.
 *
 * Conversion and anonymization are two surfaces over the same sidecar: a
 * second process would double the memory the language models take and spawn a
 * second binary for no gain, since requests are already correlated by id.
 *
 * What is held here is the *starting* worker, not the started one. Two callers
 * arriving before the first spawn finishes would otherwise each get their own
 * process, which is the very thing sharing is for.
 */
let starting: Promise<SidecarClient> | null = null;

export function getClient(): Promise<SidecarClient> {
  if (!starting) {
    const attempt = SidecarClient.start().catch((error: unknown) => {
      // A worker that failed to start must not be remembered, or every later
      // call replays that failure. Only clear our own attempt: a stop may have
      // already replaced it.
      if (starting === attempt) starting = null;
      throw error;
    });
    starting = attempt;
  }
  return starting;
}

/**
 * Stop the worker, on app shutdown.
 *
 * The reference is dropped before the kill is awaited, not after. Stopping is a
 * round trip to the OS, and a caller arriving during that window must get a new
 * worker rather than the one we have already told to fail — including when the
 * kill itself fails, since that worker rejects every request from then on.
 */
export async function stopClient(): Promise<void> {
  const running = starting;
  starting = null;
  if (running) await (await running).stop();
}
