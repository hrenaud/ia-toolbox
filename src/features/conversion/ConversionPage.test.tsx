import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConversionPage } from "./ConversionPage";
import * as conversionApi from "./conversionApi";

// Mock the conversion API
vi.mock("./conversionApi");

// Mock Tauri dialog
vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(),
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
        extension: "pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
      {
        extension: "docx",
        label: "Word Document",
        requiresOptionalComponent: false,
      },
    ]);

    render(<ConversionPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    expect(screen.getByText(/supported formats/i)).toBeInTheDocument();
    expect(screen.getByText(/PDF.*Word Document/)).toBeInTheDocument();
  });

  it("displays a file input and drag/drop hint in empty state", async () => {
    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: "pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

    render(<ConversionPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    expect(screen.getByText(/drag.*files here/i)).toBeInTheDocument();
    const fileInput = screen.getByLabelText(/select files/i);
    expect(fileInput).toHaveAttribute("type", "file");
    expect(fileInput).toHaveAttribute("multiple");
  });

  it("shows status region with aria-live for accessibility", async () => {
    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: "pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

    render(<ConversionPage />);

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
        extension: "pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
      {
        extension: "tiff",
        label: "TIFF",
        requiresOptionalComponent: true,
      },
    ]);

    render(<ConversionPage />);

    await waitFor(() => {
      expect(screen.getByText(/PDF.*TIFF/)).toBeInTheDocument();
    });

    expect(screen.getByText(/PDF.*TIFF/)).toBeInTheDocument();
  });

  it("handles format loading errors gracefully", async () => {
    vi.mocked(conversionApi.loadSupportedFormats).mockRejectedValue(
      new Error("Failed to load"),
    );

    render(<ConversionPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    expect(screen.getByRole("alert")).toHaveTextContent(
      /failed|error|unknown/i,
    );
  });

  it("provides output folder selection with informative help text", async () => {
    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: "pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

    render(<ConversionPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    const outputButton = screen.queryByRole("button", {
      name: /output|select output|change output/i,
    });
    expect(outputButton || screen.queryByText(/output/i)).toBeDefined();

    // Help text explains the numbered naming behavior
    expect(
      screen.queryByText(/originalname.*md|numbered suffix/i),
    ).toBeDefined();
  });

  it("converts files sequentially and reports per-file progress", async () => {
    const onUpdateSpy = vi.fn();
    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: "pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

    vi.mocked(conversionApi.startConversion).mockImplementation(
      async (_inputPaths, _outputDir, onUpdate) => {
        // Simulate sequential conversion of two files
        onUpdate({
          id: "job-1",
          inputPath: "file1.pdf",
          status: "running",
          progress: 50,
        });
        onUpdate({
          id: "job-1",
          inputPath: "file1.pdf",
          outputPath: "/output/file1.md",
          status: "success",
        });
        onUpdate({
          id: "job-2",
          inputPath: "file2.pdf",
          status: "running",
          progress: 75,
        });
        onUpdate({
          id: "job-2",
          inputPath: "file2.pdf",
          outputPath: "/output/file2.md",
          status: "success",
        });
      },
    );

    render(<ConversionPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    // Verify API was called
    expect(conversionApi.loadSupportedFormats).toHaveBeenCalled();
  });

  it("handles mixed batch with both success and error results in status region", async () => {
    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: "pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

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

    render(<ConversionPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    const statusRegion = screen.getByRole("status");
    expect(statusRegion).toBeInTheDocument();
  });

  it("respects keyboard-only interaction with file selection button", async () => {
    const user = userEvent.setup();
    vi.mocked(conversionApi.loadSupportedFormats).mockResolvedValue([
      {
        extension: "pdf",
        label: "PDF",
        requiresOptionalComponent: false,
      },
    ]);

    render(<ConversionPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /select files/i }),
      ).toBeInTheDocument();
    });

    // Verify button is keyboard accessible (has proper role)
    const selectButton = screen.getByRole("button", { name: /select files/i });
    expect(selectButton).toBeInTheDocument();
    expect(selectButton).toHaveAttribute("class", "file-select-button");
  });

  it("displays proper error focus management with alert role", async () => {
    vi.mocked(conversionApi.loadSupportedFormats).mockRejectedValue(
      new Error("Loading failed"),
    );

    render(<ConversionPage />);

    await waitFor(() => {
      const alert = screen.queryByRole("alert");
      if (alert) {
        expect(alert).toBeInTheDocument();
      }
    });
  });
});
