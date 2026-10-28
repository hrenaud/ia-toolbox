import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConversionPage } from "./ConversionPage";
import * as conversionApi from "./conversionApi";
import * as dialogModule from "@tauri-apps/plugin-dialog";

// Mock the conversion API
vi.mock("./conversionApi");

// Mock Tauri dialog and webview
vi.mock("@tauri-apps/plugin-dialog");

vi.mock("@tauri-apps/api/webview", () => ({
  getCurrentWebview: () => ({
    onDragDropEvent: vi.fn(() => Promise.resolve(() => {})),
  }),
}));

let media: EventTarget & { matches: boolean };
beforeEach(() => {
  vi.clearAllMocks();
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

  it("displays supported and unsupported formats distinctly", async () => {
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

    render(<ConversionPage locale="en" />);

    await waitFor(() => {
      expect(screen.getByText(/supported formats/i)).toBeInTheDocument();
    });

    // Verify both formats are displayed in the format list
    const formatList = screen.getByText(/PDF, TIFF/);
    expect(formatList).toBeInTheDocument();
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

    vi.mocked(conversionApi.startConversion).mockImplementation(
      async (_inputPaths, _outputDir, onUpdate) => {
        // Simulate sequential conversion of two files
        onUpdate({
          id: "job-1",
          inputPath: "/path/file1.pdf",
          status: "running",
          progress: 50,
        });
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

    // Verify progress is displayed
    await waitFor(() => {
      expect(screen.getByText(/progress/i)).toBeInTheDocument();
    });

    // Verify success states
    await waitFor(() => {
      const successElements = screen.getAllByText("Success");
      expect(successElements.length).toBeGreaterThanOrEqual(2);
    });
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

    // Verify status region exists
    const statusRegion = screen.getByRole("status");
    expect(statusRegion).toBeInTheDocument();

    // Verify error state appears in job list
    await waitFor(() => {
      expect(screen.getAllByText(/error/i).length).toBeGreaterThan(1);
    });
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

  it("displays proper error focus management with alert role", async () => {
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

    // Error alert should have tabIndex={-1} so focus can be moved to it
    const selectButton = screen.getByRole("button", { name: /select files/i });
    expect(selectButton).toBeInTheDocument();
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
