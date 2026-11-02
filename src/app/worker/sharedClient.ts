import { SidecarClient } from "./sidecarClient";

/**
 * The one worker process, shared by every feature that needs it.
 *
 * Conversion and anonymization are two surfaces over the same sidecar: a
 * second process would double the memory the language models take and spawn a
 * second binary for no gain, since requests are already correlated by id.
 */
let client: SidecarClient | null = null;

export async function getClient(): Promise<SidecarClient> {
  if (!client) {
    client = await SidecarClient.start();
  }
  return client;
}

/**
 * Stop the worker, on app shutdown.
 *
 * The reference is dropped only once the process is gone, so a kill that
 * failed is retried by the next call instead of leaving a process behind.
 */
export async function stopClient(): Promise<void> {
  if (client) {
    await client.stop();
    client = null;
  }
}
