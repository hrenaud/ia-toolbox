import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  WorkerError,
  type WorkerRequest,
} from "../../app/worker/sidecarClient";
import {
  analyzeDocuments,
  anonymizeDocuments,
  loadAnonymizationFormats,
  type AnalyzedDocument,
} from "./anonymizationApi";

/**
 * A batch is documents in sequence, and one document failing is not the batch
 * failing: the user picked ten files and nine of them are fine. The exception
 * is the worker itself going away, where every remaining file would fail the
 * same way and nine more identical errors tell the user nothing.
 */

const request = vi.fn();

vi.mock("../../app/worker/sharedClient", () => ({
  getClient: () => Promise.resolve({ request }),
  stopClient: vi.fn(),
}));

function analysis(id: string) {
  return {
    id,
    event: "result" as const,
    status: "success" as const,
    units: [{ id: "content", location: "document", rewritable: true }],
    detections: [
      {
        unit_id: "content",
        start: 0,
        end: 11,
        entity_type: "PERSON",
        score: 0.85,
        text: "Jean Dupont",
      },
    ],
    notes: ["markup_code_not_analyzed"],
    language: "fr",
  };
}

function failure(code: string) {
  return {
    id: "x",
    event: "result" as const,
    status: "error" as const,
    error_code: code,
    message: "English detail",
  };
}

function collect() {
  const updates: AnalyzedDocument[] = [];
  return { updates, onUpdate: (doc: AnalyzedDocument) => updates.push(doc) };
}

beforeEach(() => {
  request.mockReset();
});

describe("loadAnonymizationFormats", () => {
  it("asks for the anonymization catalog, not the conversion one", async () => {
    request.mockResolvedValue({
      id: "x",
      event: "formats",
      items: [{ extension: ".docx", label: "Word document" }],
    });

    const formats = await loadAnonymizationFormats();

    expect(request).toHaveBeenCalledWith({
      operation: "list_anonymization_formats",
    });
    expect(formats).toEqual([{ extension: ".docx", label: "Word document" }]);
  });
});

describe("analyzeDocuments", () => {
  it("reports each document and carries its analysis back", async () => {
    request.mockResolvedValue(analysis("x"));
    const { updates, onUpdate } = collect();

    await analyzeDocuments(["/a.txt"], onUpdate);

    expect(updates.map((doc) => doc.status)).toEqual(["analyzing", "success"]);
    expect(updates[1].detections[0].text).toBe("Jean Dupont");
    expect(updates[1].notes).toEqual(["markup_code_not_analyzed"]);
  });

  /**
   * A document read by the wrong model is a document whose names are all
   * wrong, and only the user can see that. So the guess travels back to the
   * screen, and the screen can send a correction and have the file read again.
   */
  it("carries the language the worker read the document in", async () => {
    request.mockResolvedValue(analysis("x"));
    const { updates, onUpdate } = collect();

    await analyzeDocuments(["/a.txt"], onUpdate);

    expect(request).toHaveBeenCalledWith({
      operation: "analyze",
      input_path: "/a.txt",
    });
    expect(updates.at(-1)?.language).toBe("fr");
  });

  it("sends the language back when the user corrected the guess", async () => {
    request.mockResolvedValue({ ...analysis("x"), language: "en" });
    const { updates, onUpdate } = collect();

    await analyzeDocuments(["/a.txt"], onUpdate, "en");

    expect(request).toHaveBeenCalledWith({
      operation: "analyze",
      input_path: "/a.txt",
      language: "en",
    } satisfies WorkerRequest);
    expect(updates.at(-1)?.language).toBe("en");
  });

  it("keeps going after a document that cannot be read", async () => {
    request
      .mockResolvedValueOnce(failure("password_protected"))
      .mockResolvedValueOnce(analysis("x"));
    const { updates, onUpdate } = collect();

    await analyzeDocuments(["/locked.docx", "/fine.txt"], onUpdate);

    const last = new Map(updates.map((doc) => [doc.inputPath, doc]));
    expect(last.get("/locked.docx")).toMatchObject({
      status: "error",
      errorCode: "password_protected",
      message: "English detail",
    });
    expect(last.get("/fine.txt")).toMatchObject({ status: "success" });
  });

  it("stops the batch when the worker itself is gone", async () => {
    request.mockRejectedValue(new WorkerError("worker_stopped"));

    await expect(
      analyzeDocuments(["/a.txt", "/b.txt"], () => {}),
    ).rejects.toBeInstanceOf(WorkerError);
    expect(request).toHaveBeenCalledOnce();
  });
});

describe("anonymizeDocuments", () => {
  const kept = [
    { unit_id: "content", start: 0, end: 11, entity_type: "PERSON" },
  ];

  it("sends what the user kept for each document, and nothing else", async () => {
    request.mockResolvedValue({
      id: "x",
      event: "result",
      status: "success",
      output_path: "/out/a-anonymise.txt",
      notes: [],
    });
    const { updates, onUpdate } = collect();

    await anonymizeDocuments(
      [{ inputPath: "/a.txt", detections: kept }],
      { outputDirectory: "/out", operator: "mask", language: "fr" },
      onUpdate,
    );

    expect(request).toHaveBeenCalledWith({
      operation: "anonymize",
      input_path: "/a.txt",
      output_directory: "/out",
      operator: "mask",
      language: "fr",
      detections: kept,
    } satisfies WorkerRequest);
    expect(updates.at(-1)).toMatchObject({
      status: "success",
      outputPath: "/out/a-anonymise.txt",
    });
  });

  it("skips a document the user kept nothing in", async () => {
    await anonymizeDocuments(
      [{ inputPath: "/a.txt", detections: [] }],
      { outputDirectory: "/out", operator: "replace", language: "fr" },
      () => {},
    );

    expect(request).not.toHaveBeenCalled();
  });

  it("isolates a document whose offsets no longer fit", async () => {
    request
      .mockResolvedValueOnce(failure("document_changed"))
      .mockResolvedValueOnce({
        id: "x",
        event: "result",
        status: "success",
        output_path: "/out/b-anonymise.txt",
        notes: [],
      });
    const { updates, onUpdate } = collect();

    await anonymizeDocuments(
      [
        { inputPath: "/a.txt", detections: kept },
        { inputPath: "/b.txt", detections: kept },
      ],
      { outputDirectory: "/out", operator: "replace", language: "fr" },
      onUpdate,
    );

    const last = new Map(updates.map((doc) => [doc.inputPath, doc]));
    expect(last.get("/a.txt")).toMatchObject({
      status: "error",
      errorCode: "document_changed",
    });
    expect(last.get("/b.txt")).toMatchObject({ status: "success" });
  });
});
