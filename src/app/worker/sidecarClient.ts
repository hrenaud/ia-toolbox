import { Command, type Child } from "@tauri-apps/plugin-shell";

/** One detection the user chose to keep, as offsets and nothing else.
 *
 * No text and no score: the worker reads the document a second time, and
 * offsets that no longer fit mean the document changed under the review
 * screen. Sending the text back would let a stale copy be written as fresh.
 */
export interface KeptDetection {
  unit_id: string;
  start: number;
  end: number;
  entity_type: string;
}

export type WorkerRequest =
  | { operation: "list_formats" }
  | { operation: "list_anonymization_formats" }
  | { operation: "convert"; input_path: string; output_directory: string }
  | { operation: "analyze"; input_path: string }
  | {
      operation: "anonymize";
      input_path: string;
      output_directory: string;
      operator: string;
      language: string;
      detections: KeptDetection[];
    };

export interface FormatInfo {
  extension: string;
  label: string;
  /** Absent for the anonymization catalog, which has no optional components. */
  requires_optional_component?: boolean;
}

/** A stretch of the document the adapter can read; `location` is a code. */
export interface AnalyzedUnit {
  id: string;
  location: string;
  rewritable: boolean;
}

export interface Detection extends KeptDetection {
  score: number;
  text: string;
  /**
   * False for the shape the model gets wrong most often — a lone capitalised
   * word opening a line. The review screen ranks those last.
   */
  likely: boolean;
}

export type WorkerResult =
  | { id: string; event: "formats"; items: FormatInfo[] }
  | {
      id: string;
      event: "result";
      status: "success";
      units: AnalyzedUnit[];
      detections: Detection[];
      notes: string[];
    }
  | {
      id: string;
      event: "result";
      status: "success";
      output_path: string;
      notes?: string[];
    }
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

export class WorkerStartupError extends WorkerError {
  constructor(public readonly cleanup: () => Promise<void>) {
    super("worker_stop_failed");
    this.name = "WorkerStartupError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isCodeList(value: unknown): boolean {
  return (
    Array.isArray(value) && value.every((code) => typeof code === "string")
  );
}

function isOffset(value: unknown): boolean {
  return Number.isInteger(value) && (value as number) >= 0;
}

function isWrittenFile(value: Record<string, unknown>): boolean {
  return (
    typeof value.output_path === "string" &&
    value.output_path.length > 0 &&
    (value.notes === undefined || isCodeList(value.notes))
  );
}

function isAnalysis(value: Record<string, unknown>): boolean {
  return (
    Array.isArray(value.units) &&
    value.units.every(
      (unit) =>
        isRecord(unit) &&
        typeof unit.id === "string" &&
        typeof unit.location === "string" &&
        typeof unit.rewritable === "boolean",
    ) &&
    Array.isArray(value.detections) &&
    value.detections.every(
      (found) =>
        isRecord(found) &&
        typeof found.unit_id === "string" &&
        isOffset(found.start) &&
        isOffset(found.end) &&
        typeof found.entity_type === "string" &&
        typeof found.score === "number" &&
        typeof found.text === "string" &&
        typeof found.likely === "boolean",
    ) &&
    isCodeList(value.notes)
  );
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
          (item.requires_optional_component === undefined ||
            typeof item.requires_optional_component === "boolean"),
      )
    );
  }
  if (value.event === "result") {
    if (value.status === "error") {
      return (
        typeof value.error_code === "string" &&
        typeof value.message === "string"
      );
    }
    if (value.status !== "success") return false;
    return "output_path" in value ? isWrittenFile(value) : isAnalysis(value);
  }
  return false;
}

/** What each operation is allowed to answer with.
 *
 * A reply shaped for another operation is not a cosmetic mismatch: it would
 * hand a page a result it never asked for, so it is rejected like any other
 * malformed output.
 */
const EXPECTED_REPLY = {
  list_formats: "formats",
  list_anonymization_formats: "formats",
  convert: "file",
  anonymize: "file",
  analyze: "analysis",
} as const;

/** The message each operation sends, field by field.
 *
 * Kept detections are rebuilt rather than forwarded, so a review row carrying
 * its display text cannot send that text back to the worker.
 */
function fieldsOf(request: WorkerRequest): Record<string, unknown> {
  switch (request.operation) {
    case "list_formats":
    case "list_anonymization_formats":
      return { operation: request.operation };
    case "analyze":
      return { operation: request.operation, input_path: request.input_path };
    case "convert":
      return {
        operation: request.operation,
        input_path: request.input_path,
        output_directory: request.output_directory,
      };
    case "anonymize":
      return {
        operation: request.operation,
        input_path: request.input_path,
        output_directory: request.output_directory,
        operator: request.operator,
        language: request.language,
        detections: request.detections.map(
          ({ unit_id, start, end, entity_type }) => ({
            unit_id,
            start,
            end,
            entity_type,
          }),
        ),
      };
  }
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
      try {
        await client.terminate();
      } catch {
        // Keep failed startup cleanup reachable even though start cannot return a client.
        throw new WorkerStartupError(() => client.stop());
      }
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
      const message = { id, ...fieldsOf(request) };
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
    const expected = pending && EXPECTED_REPLY[pending.operation];
    if (
      !pending ||
      (event.event === "formats" && expected !== "formats") ||
      // Only the operations that open a document report progress.
      (event.event === "progress" && expected === "formats") ||
      (event.event === "result" &&
        event.status === "success" &&
        expected !== ("output_path" in event ? "file" : "analysis"))
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
