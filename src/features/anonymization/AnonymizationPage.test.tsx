import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { fr } from "../../app/locales/fr";
import { AnonymizationPage } from "./AnonymizationPage";
import * as api from "./anonymizationApi";
import type { AnalyzedDocument } from "./anonymizationApi";
import * as dialogModule from "@tauri-apps/plugin-dialog";

vi.mock("./anonymizationApi");
vi.mock("@tauri-apps/plugin-dialog");

vi.mock("@tauri-apps/api/webview", () => ({
  getCurrentWebview: () => ({
    onDragDropEvent: () => Promise.resolve(() => {}),
  }),
}));

/**
 * The screen the whole feature exists for: read, show, let the user decide,
 * and only then write. Nothing is written before the confirmation, one failed
 * document never hides the others, and the count of what will be replaced is
 * announced rather than left for the user to count.
 */

function analyzed(fields: Partial<AnalyzedDocument> = {}): AnalyzedDocument {
  return {
    inputPath: "/docs/rapport.docx",
    status: "success",
    units: [{ id: "content", location: "document_body", rewritable: true }],
    detections: [
      {
        unit_id: "content",
        start: 0,
        end: 11,
        entity_type: "PERSON",
        score: 0.9,
        text: "Jean Dupont",
        likely: true,
      },
    ],
    notes: [],
    ...fields,
  };
}

/** Make `analyzeDocuments` report these documents, in order. */
function analysisReturns(documents: AnalyzedDocument[]) {
  vi.mocked(api.analyzeDocuments).mockImplementation(
    async (_paths, onUpdate) => {
      for (const document of documents) onUpdate(document);
    },
  );
}

async function pickFiles(paths: string[]) {
  vi.mocked(dialogModule.open).mockResolvedValueOnce(paths);
  await userEvent.click(
    screen.getByRole("button", { name: fr["anonymization.selectFiles"] }),
  );
}

async function pickOutput(directory = "/out") {
  vi.mocked(dialogModule.open).mockResolvedValueOnce(directory);
  await userEvent.click(
    screen.getByRole("button", { name: fr["anonymization.selectOutput"] }),
  );
}

/** Go from an empty page to the review screen for one analyzed document. */
async function reachReview(documents = [analyzed()]) {
  analysisReturns(documents);
  render(<AnonymizationPage locale="fr" />);
  await waitFor(() => expect(api.loadAnonymizationFormats).toHaveBeenCalled());
  await pickFiles(documents.map((document) => document.inputPath));
  await pickOutput();
  await userEvent.click(
    screen.getByRole("button", { name: fr["anonymization.analyze"] }),
  );
  await screen.findByText(fr["anonymization.review"]);
}

function status(): HTMLElement {
  return screen.getByRole("status");
}

beforeEach(() => {
  vi.mocked(api.loadAnonymizationFormats).mockResolvedValue([
    { extension: ".docx", label: "Document Word" },
    { extension: ".md", label: "Markdown" },
  ]);
  vi.mocked(api.anonymizeDocuments).mockResolvedValue(undefined);
});

describe("choosing the documents", () => {
  it("lists the formats that can be anonymized", async () => {
    render(<AnonymizationPage locale="fr" />);

    expect(
      await screen.findByText(/Document Word/, { ignore: "option" }),
    ).toBeVisible();
  });

  it("marks a file whose format cannot be anonymized", async () => {
    render(<AnonymizationPage locale="fr" />);
    await waitFor(() =>
      expect(api.loadAnonymizationFormats).toHaveBeenCalled(),
    );

    await pickFiles(["/docs/scan.pdf"]);

    expect(screen.getByText(fr["anonymization.unsupported"])).toBeVisible();
  });

  it("explains why a PDF has to be converted first", async () => {
    render(<AnonymizationPage locale="fr" />);
    await waitFor(() =>
      expect(api.loadAnonymizationFormats).toHaveBeenCalled(),
    );

    await pickFiles(["/docs/scan.pdf"]);

    expect(screen.getByText(fr["anonymization.pdfNotice"])).toBeVisible();
  });

  it("refuses to analyze when nothing selected can be anonymized", async () => {
    render(<AnonymizationPage locale="fr" />);
    await waitFor(() =>
      expect(api.loadAnonymizationFormats).toHaveBeenCalled(),
    );
    await pickFiles(["/docs/scan.pdf"]);
    await pickOutput();

    await userEvent.click(
      screen.getByRole("button", { name: fr["anonymization.analyze"] }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      fr["anonymization.noSupportedFiles"],
    );
    expect(api.analyzeDocuments).not.toHaveBeenCalled();
  });

  it("asks for an output folder before reading anything", async () => {
    render(<AnonymizationPage locale="fr" />);
    await waitFor(() =>
      expect(api.loadAnonymizationFormats).toHaveBeenCalled(),
    );
    await pickFiles(["/docs/rapport.docx"]);

    await userEvent.click(
      screen.getByRole("button", { name: fr["anonymization.analyze"] }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      fr["anonymization.outputRequired"],
    );
    expect(api.analyzeDocuments).not.toHaveBeenCalled();
  });

  it("moves focus to a blocking error so it is announced", async () => {
    render(<AnonymizationPage locale="fr" />);
    await waitFor(() =>
      expect(api.loadAnonymizationFormats).toHaveBeenCalled(),
    );
    await pickFiles(["/docs/rapport.docx"]);

    await userEvent.click(
      screen.getByRole("button", { name: fr["anonymization.analyze"] }),
    );

    await waitFor(() => expect(screen.getByRole("alert")).toHaveFocus());
  });
});

describe("reviewing what was found", () => {
  it("writes nothing until the user confirms", async () => {
    await reachReview();

    expect(api.anonymizeDocuments).not.toHaveBeenCalled();
  });

  it("starts with nothing selected, so a slip replaces nothing", async () => {
    await reachReview();

    expect(status()).toHaveTextContent("0 élément(s) sélectionné(s) sur 1");
  });

  it("announces the count as the user chooses", async () => {
    await reachReview();

    await userEvent.click(
      screen.getByRole("checkbox", { name: /Jean Dupont/ }),
    );

    expect(status()).toHaveTextContent("1 élément(s) sélectionné(s) sur 1");
  });

  /**
   * The list asks once per value, so the count has to say the same thing. A
   * name found twice that announced "2 sur 2" after one tick would be counting
   * something the user cannot see.
   */
  it("counts the values it asks about, not their occurrences", async () => {
    await reachReview([
      analyzed({
        detections: [
          {
            unit_id: "content",
            start: 0,
            end: 11,
            entity_type: "PERSON",
            score: 0.9,
            text: "Jean Dupont",
            likely: true,
          },
          {
            unit_id: "content",
            start: 20,
            end: 31,
            entity_type: "PERSON",
            score: 0.9,
            text: "Jean Dupont",
            likely: true,
          },
        ],
      }),
    ]);

    expect(status()).toHaveTextContent("0 élément(s) sélectionné(s) sur 1");

    await userEvent.click(
      screen.getByRole("checkbox", { name: /Jean Dupont/ }),
    );

    expect(status()).toHaveTextContent("1 élément(s) sélectionné(s) sur 1");
  });

  it("selects everything in every document at once", async () => {
    await reachReview([
      analyzed(),
      analyzed({
        inputPath: "/docs/notes.md",
        detections: [
          {
            unit_id: "content",
            start: 4,
            end: 14,
            entity_type: "EMAIL_ADDRESS",
            score: 1,
            text: "a@b.fr",
            likely: true,
          },
        ],
      }),
    ]);

    await userEvent.click(
      screen.getByRole("button", { name: fr["anonymization.selectAll"] }),
    );

    expect(status()).toHaveTextContent("2 élément(s) sélectionné(s) sur 2");
  });

  it("gives back the empty selection in one action", async () => {
    await reachReview();
    await userEvent.click(
      screen.getByRole("button", { name: fr["anonymization.selectAll"] }),
    );

    await userEvent.click(
      screen.getByRole("button", { name: fr["anonymization.clearAll"] }),
    );

    expect(status()).toHaveTextContent("0 élément(s) sélectionné(s) sur 1");
  });

  it("names the file that will be written, before writing it", async () => {
    await reachReview();

    expect(screen.getByText(/rapport-anonymise\.docx/)).toBeVisible();
  });

  it("tells the user what will not be rewritten", async () => {
    await reachReview([analyzed({ notes: ["tracked_changes_not_rewritten"] })]);

    expect(
      screen.getByText(fr["anonymization.note.tracked_changes_not_rewritten"]),
    ).toBeVisible();
  });

  it("warns that one replacement can change several cells", async () => {
    await reachReview([analyzed({ notes: ["xlsx_shared_strings_reused"] })]);

    expect(screen.getByText(fr["anonymization.sharedValue"])).toBeVisible();
  });

  it("says so when a document held nothing personal", async () => {
    await reachReview([analyzed({ detections: [] })]);

    expect(screen.getByText(fr["anonymization.nothingFound"])).toBeVisible();
  });

  it("shows a document that could not be read next to the others", async () => {
    await reachReview([
      analyzed(),
      analyzed({
        inputPath: "/docs/verrouille.docx",
        status: "error",
        detections: [],
        errorCode: "password_protected",
      }),
    ]);

    expect(
      screen.getByText(fr["anonymization.failure.password_protected"]),
    ).toBeVisible();
    expect(screen.getByRole("checkbox", { name: /Jean Dupont/ })).toBeVisible();
  });

  it("comes back to the file selection without writing", async () => {
    await reachReview();

    await userEvent.click(
      screen.getByRole("button", { name: fr["anonymization.back"] }),
    );

    expect(
      screen.getByRole("button", { name: fr["anonymization.analyze"] }),
    ).toBeVisible();
    expect(api.anonymizeDocuments).not.toHaveBeenCalled();
  });
});

describe("writing the copies", () => {
  it("sends only what the user kept, with the chosen operator", async () => {
    await reachReview();
    await userEvent.click(
      screen.getByRole("checkbox", { name: /Jean Dupont/ }),
    );
    await userEvent.click(
      screen.getByRole("radio", { name: fr["anonymization.operator.mask"] }),
    );

    await userEvent.click(
      screen.getByRole("button", { name: fr["anonymization.confirm"] }),
    );

    await waitFor(() => expect(api.anonymizeDocuments).toHaveBeenCalled());
    expect(vi.mocked(api.anonymizeDocuments).mock.calls[0][0]).toEqual([
      {
        inputPath: "/docs/rapport.docx",
        detections: [
          { unit_id: "content", start: 0, end: 11, entity_type: "PERSON" },
        ],
      },
    ]);
    expect(vi.mocked(api.anonymizeDocuments).mock.calls[0][1]).toEqual({
      outputDirectory: "/out",
      operator: "mask",
      language: "fr",
    });
  });

  it("will not write when the user kept nothing", async () => {
    await reachReview();

    expect(
      screen.getByRole("button", { name: fr["anonymization.confirm"] }),
    ).toBeDisabled();
  });

  it("shows where each copy went", async () => {
    vi.mocked(api.anonymizeDocuments).mockImplementation(
      async (documents, _choices, onUpdate) => {
        for (const document of documents) {
          onUpdate({
            inputPath: document.inputPath,
            status: "success",
            units: [],
            detections: [],
            notes: [],
            outputPath: "/out/rapport-anonymise.docx",
          });
        }
      },
    );
    await reachReview();
    await userEvent.click(
      screen.getByRole("checkbox", { name: /Jean Dupont/ }),
    );

    await userEvent.click(
      screen.getByRole("button", { name: fr["anonymization.confirm"] }),
    );

    expect(
      await screen.findByText("/out/rapport-anonymise.docx"),
    ).toBeVisible();
    expect(screen.getByText(fr["anonymization.written"])).toBeVisible();
  });

  it("reports a copy that could not be written, in words", async () => {
    vi.mocked(api.anonymizeDocuments).mockImplementation(
      async (documents, _choices, onUpdate) => {
        for (const document of documents) {
          onUpdate({
            inputPath: document.inputPath,
            status: "error",
            units: [],
            detections: [],
            notes: [],
            errorCode: "write_failed",
          });
        }
      },
    );
    await reachReview();
    await userEvent.click(
      screen.getByRole("checkbox", { name: /Jean Dupont/ }),
    );

    await userEvent.click(
      screen.getByRole("button", { name: fr["anonymization.confirm"] }),
    );

    expect(
      await screen.findByText(fr["anonymization.failure.write_failed"]),
    ).toBeVisible();
  });

  it("surfaces the worker going away as a blocking error", async () => {
    vi.mocked(api.anonymizeDocuments).mockRejectedValue(
      new Error("worker_stopped"),
    );
    await reachReview();
    await userEvent.click(
      screen.getByRole("checkbox", { name: /Jean Dupont/ }),
    );

    await userEvent.click(
      screen.getByRole("button", { name: fr["anonymization.confirm"] }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "worker_stopped",
    );
  });

  it("keeps the English detail of a failure this build does not know", async () => {
    vi.mocked(api.anonymizeDocuments).mockImplementation(
      async (documents, _choices, onUpdate) => {
        for (const document of documents) {
          onUpdate({
            inputPath: document.inputPath,
            status: "error",
            units: [],
            detections: [],
            notes: [],
            errorCode: "future_code",
            message: "Raw English detail",
          });
        }
      },
    );
    await reachReview();
    await userEvent.click(
      screen.getByRole("checkbox", { name: /Jean Dupont/ }),
    );

    await userEvent.click(
      screen.getByRole("button", { name: fr["anonymization.confirm"] }),
    );

    expect(await screen.findByText("Raw English detail")).toBeVisible();
  });
});

describe("the English locale", () => {
  it("says everything in English too", async () => {
    analysisReturns([analyzed()]);
    render(<AnonymizationPage locale="en" />);
    await waitFor(() =>
      expect(api.loadAnonymizationFormats).toHaveBeenCalled(),
    );

    expect(screen.getByRole("button", { name: "Select files" })).toBeVisible();
  });

  it("names the copy with the English suffix", async () => {
    analysisReturns([analyzed()]);
    render(<AnonymizationPage locale="en" />);
    await waitFor(() =>
      expect(api.loadAnonymizationFormats).toHaveBeenCalled(),
    );
    vi.mocked(dialogModule.open).mockResolvedValueOnce(["/docs/rapport.docx"]);
    await userEvent.click(screen.getByRole("button", { name: "Select files" }));
    vi.mocked(dialogModule.open).mockResolvedValueOnce("/out");
    await userEvent.click(
      screen.getByRole("button", { name: "Select output folder" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Find personal information" }),
    );

    expect(await screen.findByText(/rapport-anonymized\.docx/)).toBeVisible();
  });
});

describe("the document list", () => {
  it("shows each document under its own name", async () => {
    await reachReview([
      analyzed(),
      analyzed({ inputPath: "/docs/notes.md", detections: [] }),
    ]);

    const headings = screen.getAllByRole("heading", { level: 3 });

    expect(headings.map((heading) => heading.textContent)).toEqual([
      "rapport.docx",
      "notes.md",
    ]);
    expect(
      within(headings[0].closest("section") as HTMLElement).getByRole(
        "checkbox",
        { name: /Jean Dupont/ },
      ),
    ).toBeVisible();
  });
});
