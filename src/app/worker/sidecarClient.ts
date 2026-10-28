import { Command, type Child } from "@tauri-apps/plugin-shell";

export type WorkerRequest =
  | { operation: "list_formats" }
  | { operation: "convert"; input_path: string; output_directory: string };

export interface FormatInfo {
  extension: string;
  label: string;
  requires_optional_component: boolean;
}

export type WorkerResult =
  | { id: string; event: "formats"; items: FormatInfo[] }
  | { id: string; event: "result"; status: "success"; output_path: string }
  | {
      id: string;
      event: "result";
      status: "error";
      error_code: string;
      message: string;
    };
type WorkerEvent =
  WorkerResult | { id: string; event: "progress"; percent: number };

// The UI translates codes. Raw process diagnostics never cross this boundary.
export class WorkerError extends Error {
  constructor(
    public readonly code:
      | "invalid_response"
      | "worker_stopped"
      | "worker_unavailable"
      | "worker_stop_failed",
  ) {
    super(code);
    this.name = "WorkerError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isEvent(value: unknown): value is WorkerEvent {
  if (!isRecord(value) || typeof value.id !== "string") return false;
  if (value.event === "progress") {
    return (
      typeof value.percent === "number" &&
      Number.isFinite(value.percent) &&
      value.percent >= 0 &&
      value.percent <= 100
    );
  }
  if (value.event === "formats") {
    return (
      Array.isArray(value.items) &&
      value.items.every(
        (item) =>
          isRecord(item) &&
          typeof item.extension === "string" &&
          typeof item.label === "string" &&
          typeof item.requires_optional_component === "boolean",
      )
    );
  }
  if (value.event === "result") {
    return value.status === "success"
      ? typeof value.output_path === "string" && value.output_path.length > 0
      : value.status === "error" &&
          typeof value.error_code === "string" &&
          typeof value.message === "string";
  }
  return false;
}

interface Pending {
  operation: WorkerRequest["operation"];
  resolve: (result: WorkerResult) => void;
  reject: (error: WorkerError) => void;
  progress?: (percent: number) => void;
}

export class SidecarClient {
  private child?: Child;
  private failure?: WorkerError;
  private termination?: Promise<void>;
  private pending = new Map<string, Pending>();

  private constructor() {}

  static async start(): Promise<SidecarClient> {
    const client = new SidecarClient();
    try {
      const command = Command.sidecar("binaries/document-worker");
      // Shell's default text mode delivers one complete line per data event.
      command.stdout.on("data", (line) => client.receive(line));
      command.on("close", () => client.fail("worker_stopped"));
      command.on("error", () => client.fail("worker_stopped"));
      client.child = await command.spawn();
    } catch {
      client.fail("worker_unavailable");
    }
    if (client.failure) {
      await client.terminate();
      throw client.failure;
    }
    return client;
  }

  request(
    request: WorkerRequest,
    progress?: (percent: number) => void,
  ): Promise<WorkerResult> {
    if (this.failure) return Promise.reject(this.failure);
    const id = crypto.randomUUID();
    return new Promise((resolve, reject) => {
      this.pending.set(id, {
        operation: request.operation,
        resolve,
        reject,
        progress,
      });
      // Select fields explicitly so extra UI properties cannot become protocol commands.
      const message =
        request.operation === "list_formats"
          ? { id, operation: request.operation }
          : {
              id,
              operation: request.operation,
              input_path: request.input_path,
              output_directory: request.output_directory,
            };
      void this.child!.write(JSON.stringify(message) + "\n").catch(() =>
        this.fail("worker_stopped"),
      );
    });
  }

  async stop(): Promise<void> {
    this.fail("worker_stopped");
    await this.terminate();
  }

  private terminate(): Promise<void> {
    if (this.termination) return this.termination;
    if (!this.child) return Promise.resolve();
    this.termination = this.child.kill().then(
      () => {
        this.child = undefined;
      },
      () => {
        this.termination = undefined;
        throw new WorkerError("worker_stop_failed");
      },
    );
    return this.termination;
  }

  private receive(line: string): void {
    if (this.failure) return;
    let event: unknown;
    try {
      event = JSON.parse(line);
    } catch {
      this.fail("invalid_response");
      return;
    }
    if (!isEvent(event)) {
      this.fail("invalid_response");
      return;
    }
    const pending = this.pending.get(event.id);
    if (
      !pending ||
      (event.event === "formats" && pending.operation !== "list_formats") ||
      (event.event === "progress" && pending.operation !== "convert") ||
      (event.event === "result" &&
        event.status === "success" &&
        pending.operation !== "convert")
    ) {
      this.fail("invalid_response");
      return;
    }
    if (event.event === "progress") {
      pending.progress?.(event.percent);
    } else {
      this.pending.delete(event.id);
      pending.resolve(event);
    }
  }

  private fail(code: WorkerError["code"]): void {
    if (this.failure) return;
    this.failure = new WorkerError(code);
    for (const pending of this.pending.values()) pending.reject(this.failure);
    this.pending.clear();
    // Event handlers cannot await cleanup. Keep its rejection observable to stop(),
    // while preventing an unhandled rejection when failure arrived asynchronously.
    void this.terminate().catch(() => undefined);
  }
}
