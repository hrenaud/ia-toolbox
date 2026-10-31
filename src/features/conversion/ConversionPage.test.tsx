import { StrictMode } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConversionPage } from "./ConversionPage";
import * as conversionApi from "./conversionApi";
import * as dialogModule from "@tauri-apps/plugin-dialog";

// Mock the conversion API
vi.mock("./conversionApi");

// Mock Tauri dialog and webview
vi.mock("@tauri-apps/plugin-dialog");

/**
 * Stands in for the webview's native drag and drop subscription.
 *
 * It keeps the set of live handlers and honours the unlisten function it hands
 * back, because that is where the interesting behaviour is: registration is
 * asynchronous, so a component that unmounts before its promise settles can
 * leave a handler behind. Resolving to a no-op unlisten, as this mock used to,
 * makes that leak invisible.
 */
const webview = vi.hoisted(() => {
  const handlers = new Set<(event: unknown) => void>();
  return {
    handlers,
    onDragDropEvent: vi.fn((handler: (event: unknown) => void) => {
      handlers.add(handler);
      return Promise.resolve(() => handlers.delete(handler));
    }),
  };
});

vi.mock("@tauri-apps/api/webview", () => ({
  getCurrentWebview: () => webview,
}));

/** Deliver a native drop to every handler currently subscribed. */
function dropFiles(paths: string[]): void {
  act(() => {
    for (const handler of webview.handlers) {
      handler({ payload: { type: "drop", paths } });
    }
  });
}

/**
 * The selected-files list and the job list both show the basename, so job
 * assertions have to be scoped to the job list.
 */
function jobItem(basename: string): HTMLElement {
  const items = Array.from(
    document.querySelectorAll<HTMLElement>("li.job-item"),
  ).filter((item) =>
    item.querySelector(".job-name")?.textContent?.includes(basename),
  );
  if (items.length !== 1) {
    throw new Error(
      `expected exactly one job for ${basename}, found ${items.length}`,
    );
  }
  return items[0];
}

let media: EventTarget & { matches: boolean };
beforeEach(() => {
  vi.clearAllMocks();
  webview.handlers.clear();
  media = Object.assign(new EventTarget(), { matches: false });
  vi.stubGlobal("matchMedia", () => media);
});

describe("ConversionPage", () => {
  it("renders empty state with file selection button and supported formats", async () => {
    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: ".pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
      {
        extension: ".docx",
        label: "Word Document",
        requiresOptionalComponent: false,
      },
    ]);

    render(<ConversionPage locale="en" />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    expect(screen.getByText(/supported formats/i)).toBeInTheDocument();
    expect(screen.getByText(/PDF.*Word Document/)).toBeInTheDocument();
  });

  it("displays a file selection button and drag/drop hint in empty state", async () => {
    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: ".pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

    render(<ConversionPage locale="en" />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    expect(screen.getByText(/drag.*files here/i)).toBeInTheDocument();
    const selectButton = screen.getByRole("button", { name: /select files/i });
    expect(selectButton).toHaveClass("file-select-button");
  });

  // Subscribing is asynchronous and the component used to keep the unlisten
  // function in a variable the cleanup read synchronously. Under StrictMode the
  // first mount is discarded before its promise settles, so the cleanup found
  // nothing to unlisten and that handler stayed subscribed alongside the second
  // one. A dropped file then landed in the list twice, while the file picker
  // next to the drop zone — which goes through no listener — added it once.
  it("adds a dropped file once when mounted under StrictMode", async () => {
    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      { extension: ".pdf", label: "PDF", requiresOptionalComponent: false },
    ]);

    render(
      <StrictMode>
        <ConversionPage locale="en" />
      </StrictMode>,
    );
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    dropFiles(["/tmp/report.pdf"]);

    expect(screen.getAllByText("report.pdf")).toHaveLength(1);
  });

  it("shows status region with aria-live for accessibility", async () => {
    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: ".pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

    render(<ConversionPage locale="en" />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    const statusRegion = screen.getByRole("status");
    expect(statusRegion).toHaveAttribute("aria-live", "polite");
    expect(statusRegion).toHaveAttribute("aria-atomic", "false");
  });

  it("badges selected files distinctly for convertible, OCR-gated, and unknown formats", async () => {
    const dialogOpen = vi.mocked(dialogModule.open);

    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: ".pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
      {
        extension: ".tiff",
        label: "TIFF",
        requiresOptionalComponent: true,
      },
    ]);

    dialogOpen.mockResolvedValue([
      "/path/ok.pdf",
      "/path/scan.tiff",
      "/path/mystery.xyz",
    ]);

    const user = userEvent.setup();
    render(<ConversionPage locale="en" />);

    await waitFor(() => {
      expect(screen.getByText(/PDF, TIFF/)).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /select files/i }));

    const item = async (name: string) =>
      (await screen.findByText(name)).closest("li")!;

    // A convertible format carries no badge at all.
    const convertible = await item("ok.pdf");
    expect(convertible).not.toHaveTextContent(/unsupported|requires ocr/i);

    // The two rejected files are distinguished by their reason, not by colour.
    expect(await item("scan.tiff")).toHaveTextContent(/requires ocr/i);
    expect(await item("mystery.xyz")).toHaveTextContent(/unsupported/i);
  });

  it("handles format loading errors gracefully", async () => {
    vi.mocked(conversionApi.loadSupportedFormats).mockRejectedValue(
      new Error("Failed to load"),
    );

    render(<ConversionPage locale="en" />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    expect(screen.getByRole("alert")).toHaveTextContent(/restart/i);
  });

  it("provides output folder selection with informative help text", async () => {
    const dialogOpen = vi.mocked(dialogModule.open);

    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: ".pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

    // Mock file selection to return paths, then directory selection
    dialogOpen.mockImplementation(async (options) => {
      if (options?.directory) {
        return "/test/output";
      }
      return ["/test/file1.pdf"];
    });

    const user = userEvent.setup();
    render(<ConversionPage locale="en" />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    // Click select files button
    const selectButton = screen.getByRole("button", { name: /select files/i });
    await user.click(selectButton);

    // Files should appear
    await waitFor(() => {
      expect(screen.getByText("file1.pdf")).toBeInTheDocument();
    });

    // Now output button should appear
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select output/i }),
      ).toBeInTheDocument();
    });

    // Help text explains the numbered naming behavior
    expect(
      screen.getByText(/originalname.*md|numbered suffix/i),
    ).toBeInTheDocument();
  });

  it("converts files sequentially and reports per-file progress", async () => {
    const dialogOpen = vi.mocked(dialogModule.open);

    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: ".pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

    dialogOpen.mockImplementation(async (options) => {
      if (options?.directory) {
        return "/test/output";
      }
      return ["/path/file1.pdf", "/path/file2.pdf"];
    });

    // Hold the batch open after the first file so the intermediate running
    // state is observable instead of being overwritten in the same tick.
    let releaseSecondFile: () => void = () => {};
    const secondFileGate = new Promise<void>((resolve) => {
      releaseSecondFile = resolve;
    });
    const convertedOrder: string[] = [];

    vi.mocked(conversionApi.startConversion).mockImplementation(
      async (inputPaths, _outputDir, onUpdate) => {
        expect(inputPaths).toEqual(["/path/file1.pdf", "/path/file2.pdf"]);

        onUpdate({
          id: "job-1",
          inputPath: "/path/file1.pdf",
          status: "running",
          progress: 50,
        });
        await secondFileGate;
        convertedOrder.push("/path/file1.pdf");
        onUpdate({
          id: "job-1",
          inputPath: "/path/file1.pdf",
          outputPath: "/output/file1.md",
          status: "success",
        });
        onUpdate({
          id: "job-2",
          inputPath: "/path/file2.pdf",
          status: "running",
          progress: 75,
        });
        convertedOrder.push("/path/file2.pdf");
        onUpdate({
          id: "job-2",
          inputPath: "/path/file2.pdf",
          outputPath: "/output/file2.md",
          status: "success",
        });
      },
    );

    const user = userEvent.setup();
    render(<ConversionPage locale="en" />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    // Click select files button
    const selectButton = screen.getByRole("button", { name: /select files/i });
    await user.click(selectButton);

    // Files should appear
    await waitFor(() => {
      expect(screen.getByText("file1.pdf")).toBeInTheDocument();
      expect(screen.getByText("file2.pdf")).toBeInTheDocument();
    });

    // Click output button
    const outputButton = screen.getByRole("button", { name: /select output/i });
    await user.click(outputButton);

    // Click convert button
    const convertButton = await screen.findByRole("button", {
      name: /convert/i,
    });
    await user.click(convertButton);

    // Only the first file is under way, and its progress is announced.
    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(
        "Processing file1.pdf: 50%",
      );
    });
    expect(jobItem("file1.pdf")).toHaveTextContent(/running/i);
    expect(screen.queryByText("/output/file1.md")).not.toBeInTheDocument();

    releaseSecondFile();

    // Both files reach a terminal state, in the order they were submitted.
    await waitFor(() => {
      expect(screen.getAllByText("Success")).toHaveLength(2);
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Successfully converted file2.pdf",
    );
    expect(convertedOrder).toEqual(["/path/file1.pdf", "/path/file2.pdf"]);
  });

  it("handles mixed batch with both success and error results in status region", async () => {
    const dialogOpen = vi.mocked(dialogModule.open);

    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: ".pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

    dialogOpen.mockImplementation(async (options) => {
      if (options?.directory) {
        return "/test/output";
      }
      return ["/path/file1.pdf", "/path/file2.pdf"];
    });

    vi.mocked(conversionApi.startConversion).mockImplementation(
      async (_inputPaths, _outputDir, onUpdate) => {
        // First file succeeds
        onUpdate({
          id: "job-1",
          inputPath: "/path/file1.pdf",
          outputPath: "/output/file1.md",
          status: "success",
        });
        // Second file fails
        onUpdate({
          id: "job-2",
          inputPath: "/path/file2.pdf",
          status: "error",
          message: "Conversion failed",
        });
      },
    );

    const user = userEvent.setup();
    render(<ConversionPage locale="en" />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    // Select files
    const selectButton = screen.getByRole("button", { name: /select files/i });
    await user.click(selectButton);

    // Files should appear
    await waitFor(() => {
      expect(screen.getByText("file1.pdf")).toBeInTheDocument();
    });

    // Select output
    const outputButton = screen.getByRole("button", { name: /select output/i });
    await user.click(outputButton);

    // Start conversion
    const convertButton = await screen.findByRole("button", {
      name: /convert/i,
    });
    await user.click(convertButton);

    // The failure is announced, and both outcomes are listed per file.
    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(
        "Error converting file2.pdf: Conversion failed",
      );
    });
    expect(jobItem("file1.pdf")).toHaveTextContent(/success/i);
    const failed = jobItem("file2.pdf");
    expect(failed).toHaveTextContent(/error/i);
    expect(failed).toHaveTextContent("Conversion failed");
  });

  it("respects keyboard-only interaction with file selection button", async () => {
    const dialogOpen = vi.mocked(dialogModule.open);

    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: ".pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

    dialogOpen.mockResolvedValue(["/test/file.pdf"]);

    const user = userEvent.setup();
    render(<ConversionPage locale="en" />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    // Verify button is keyboard accessible
    const selectButton = screen.getByRole("button", { name: /select files/i });
    expect(selectButton).toBeInTheDocument();
    expect(selectButton).toHaveClass("file-select-button");

    // Tab to the button and activate with Enter
    await user.tab();
    expect(selectButton).toHaveFocus();
    await user.keyboard("{Enter}");

    // Verify open was called (file dialog should open)
    expect(dialogOpen).toHaveBeenCalled();
  });

  it("moves focus to the alert for a blocking error raised by a user action", async () => {
    const dialogOpen = vi.mocked(dialogModule.open);

    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: ".pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

    // The native file dialog fails, which blocks the whole workflow.
    dialogOpen.mockRejectedValue(new Error("dialog unavailable"));

    const user = userEvent.setup();
    render(<ConversionPage locale="en" />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /select files/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/failed to select files/i);
    expect(alert).toHaveFocus();
  });

  it("keeps focus in place when the format catalog fails on mount", async () => {
    vi.mocked(conversionApi.loadSupportedFormats).mockRejectedValue(
      new Error("Failed to load"),
    );

    render(<ConversionPage locale="en" />);

    const alert = await screen.findByRole("alert");
    expect(alert).not.toHaveFocus();
    expect(document.body).toHaveFocus();
  });

  it("supports French locale", async () => {
    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: ".pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

    render(<ConversionPage locale="fr" />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /sélectionner les fichiers/i }),
      ).toBeInTheDocument();
    });

    expect(screen.getByText(/formats pris en charge/i)).toBeInTheDocument();
  });

  it("allows adding files to a batch", async () => {
    const dialogOpen = vi.mocked(dialogModule.open);

    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: ".pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

    let callCount = 0;
    dialogOpen.mockImplementation(async () => {
      callCount++;
      if (callCount === 1) {
        return ["/path/file1.pdf", "/path/file2.pdf"];
      }
      return ["/path/file3.pdf"];
    });

    const user = userEvent.setup();
    render(<ConversionPage locale="en" />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    // Click select files button
    const selectButton = screen.getByRole("button", { name: /select files/i });
    await user.click(selectButton);

    // Files should be displayed
    await waitFor(() => {
      expect(screen.getByText("file1.pdf")).toBeInTheDocument();
      expect(screen.getByText("file2.pdf")).toBeInTheDocument();
    });

    // Select files button should still be available to add more
    const selectButtonAgain = screen.getByRole("button", {
      name: /select files/i,
    });
    expect(selectButtonAgain).toBeInTheDocument();

    // Click it again to add more files
    await user.click(selectButtonAgain);

    // All three files should now be displayed
    await waitFor(() => {
      expect(screen.getByText("file3.pdf")).toBeInTheDocument();
    });
  });

  it("marks unsupported files as unsupported", async () => {
    const dialogOpen = vi.mocked(dialogModule.open);

    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: ".pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

    dialogOpen.mockResolvedValue(["/path/file.xyz"]);

    const user = userEvent.setup();
    render(<ConversionPage locale="en" />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    const selectButton = screen.getByRole("button", { name: /select files/i });
    await user.click(selectButton);

    // File should be marked as unsupported
    await waitFor(() => {
      expect(screen.getByText("file.xyz")).toBeInTheDocument();
      // Check the status badge
      expect(screen.getAllByText(/unsupported/i)[0]).toBeInTheDocument();
    });
  });
});
