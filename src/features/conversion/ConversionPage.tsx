import { useEffect, useRef, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { dictionaries, getInitialLocale } from "../../app/i18n";
import {
  loadSupportedFormats,
  startConversion,
  stopClient,
  type ConversionJob,
  type FormatInfo,
} from "./conversionApi";
import {
  isSupportedFormat,
  requiresOptionalComponent,
  formatListForDisplay,
} from "./formatLabels";
import { useConversionJobs } from "./useConversionJobs";
import "./ConversionPage.css";

export function ConversionPage() {
  const [formats, setFormats] = useState<FormatInfo[]>([]);
  const [formatsLoaded, setFormatsLoaded] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [outputDirectory, setOutputDirectory] = useState<string | null>(null);
  const [isConverting, setIsConverting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const statusRegionRef = useRef<HTMLDivElement>(null);
  const { jobs, addJob, updateJob } = useConversionJobs();

  // Get locale from system (respects saved preference at AppShell level)
  const systemLocale = navigator.language;
  const locale = getInitialLocale(systemLocale, null);
  const t = dictionaries[locale];

  // Load supported formats on mount
  useEffect(() => {
    loadSupportedFormats()
      .then((loaded) => {
        setFormats(loaded);
        setFormatsLoaded(true);
      })
      .catch((err) => {
        console.error("Failed to load formats:", err);
        setError(t["conversion.formatLoadError"]);
        setFormatsLoaded(true);
      });

    return () => {
      void stopClient();
    };
  }, [t]);

  const handleFileSelect = (files: FileList | null) => {
    if (!files) return;
    const newFiles = Array.from(files);
    setSelectedFiles((prev) => [...prev, ...newFiles]);
    setError(null);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.currentTarget.classList.add("drag-active");
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.currentTarget.classList.remove("drag-active");
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.currentTarget.classList.remove("drag-active");
    handleFileSelect(e.dataTransfer.files);
  };

  const handleSelectOutput = async () => {
    try {
      const selected = await open({
        directory: true,
        title: t["conversion.selectOutput"],
      });
      if (selected) {
        setOutputDirectory(selected as string);
      }
    } catch (err) {
      console.error("Failed to select output directory:", err);
      setError(t["conversion.outputSelectError"]);
    }
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleConvert = async () => {
    if (!outputDirectory) {
      setError(t["conversion.outputRequired"]);
      return;
    }

    const supportedFiles = selectedFiles.filter((file) =>
      isSupportedFormat(file.name, formats),
    );

    if (supportedFiles.length === 0) {
      setError(t["conversion.noSupportedFiles"]);
      return;
    }

    setIsConverting(true);
    setError(null);
    setStatusMessage("");

    try {
      // Queue initial jobs
      supportedFiles.forEach((file) => {
        addJob({
          id: crypto.randomUUID(),
          inputPath: file.webkitRelativePath || file.name,
          status: "queued",
        });
      });

      await startConversion(
        supportedFiles.map((f) => f.name),
        outputDirectory,
        (job) => {
          updateJob(job.id, job);
          updateStatusMessage(job);
        },
      );
    } catch (err) {
      const message =
        err instanceof Error ? err.message : t["conversion.unknownError"];
      setError(message);
      setStatusMessage(`Error: ${message}`);
    } finally {
      setIsConverting(false);
    }
  };

  const updateStatusMessage = (job: ConversionJob) => {
    if (job.status === "running" && job.progress !== undefined) {
      setStatusMessage(`Processing ${job.inputPath}: ${job.progress}%`);
    } else if (job.status === "success") {
      setStatusMessage(`Successfully converted ${job.inputPath}`);
    } else if (job.status === "error") {
      setStatusMessage(
        `Error converting ${job.inputPath}: ${job.message || "unknown error"}`,
      );
    }
  };

  const unsupportedFiles = selectedFiles.filter((file) => {
    const supported = isSupportedFormat(file.name, formats);
    const optional = requiresOptionalComponent(file.name, formats);
    return !supported && !optional;
  });

  const optionalComponentFiles = selectedFiles.filter((file) =>
    requiresOptionalComponent(file.name, formats),
  );

  return (
    <div className="conversion-page">
      <div
        role="status"
        aria-live="polite"
        aria-atomic="false"
        ref={statusRegionRef}
        className="sr-only"
      >
        {statusMessage}
      </div>

      {/* Format list */}
      {formatsLoaded && formats.length > 0 && (
        <div className="format-section">
          <h2>{t["conversion.supportedFormats"]}</h2>
          <p className="format-list">{formatListForDisplay(formats)}</p>
        </div>
      )}

      {/* File selection area */}
      {!isConverting && selectedFiles.length === 0 && (
        <div
          className="file-input-area"
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <button
            className="file-select-button"
            onClick={() => fileInputRef.current?.click()}
          >
            {t["conversion.selectFiles"]}
          </button>
          <p className="drag-hint">{t["conversion.dragHint"]}</p>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={(e) => handleFileSelect(e.currentTarget.files)}
            style={{ display: "none" }}
            aria-label={t["conversion.selectFiles"]}
          />
        </div>
      )}

      {/* Selected files list */}
      {selectedFiles.length > 0 && !isConverting && (
        <div className="files-section">
          <h2>{t["conversion.selectedFiles"]}</h2>
          <ul className="file-list">
            {selectedFiles.map((file, index) => {
              const supported = isSupportedFormat(file.name, formats);
              const optional = requiresOptionalComponent(file.name, formats);
              return (
                <li
                  key={index}
                  className={`file-item ${supported ? "supported" : optional ? "optional" : "unsupported"}`}
                >
                  <span>{file.name}</span>
                  {!supported && !optional && (
                    <span className="status-badge unsupported">
                      {t["conversion.unsupported"]}
                    </span>
                  )}
                  {optional && (
                    <span className="status-badge optional">
                      {t["conversion.requiresOcr"]}
                    </span>
                  )}
                  <button
                    onClick={() => handleRemoveFile(index)}
                    aria-label={`Remove ${file.name}`}
                    className="remove-button"
                  >
                    ✕
                  </button>
                </li>
              );
            })}
          </ul>

          {unsupportedFiles.length > 0 && (
            <p className="warning">
              {unsupportedFiles.length} {t["conversion.unsupportedWarning"]}
            </p>
          )}

          {optionalComponentFiles.length > 0 && (
            <p className="info">
              {optionalComponentFiles.length} {t["conversion.ocmInfo"]}
            </p>
          )}

          {/* Output folder selector */}
          <div className="output-section">
            <button onClick={handleSelectOutput} className="secondary-button">
              {outputDirectory
                ? t["conversion.changeOutput"]
                : t["conversion.selectOutput"]}
            </button>
            {outputDirectory && (
              <p className="output-path">
                {t["conversion.outputPath"]} <code>{outputDirectory}</code>
              </p>
            )}
            <p className="output-help">{t["conversion.outputHelp"]}</p>
          </div>

          {/* Convert button */}
          <button
            onClick={handleConvert}
            disabled={
              isConverting ||
              selectedFiles.length === 0 ||
              !outputDirectory ||
              selectedFiles.every((f) => !isSupportedFormat(f.name, formats))
            }
            className="primary"
          >
            {isConverting
              ? t["conversion.converting"]
              : t["conversion.convert"]}
          </button>

          <button
            onClick={() => {
              setSelectedFiles([]);
              setOutputDirectory(null);
              setError(null);
            }}
            className="secondary-button"
            disabled={isConverting}
          >
            {t["conversion.clearSelection"]}
          </button>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="error-message" role="alert">
          <p>{error}</p>
          <button onClick={() => setError(null)} aria-label="Close error">
            ✕
          </button>
        </div>
      )}

      {/* Progress and results */}
      {jobs.length > 0 && (
        <div className="jobs-section">
          <h2>{t["conversion.progress"]}</h2>
          <ul className="job-list">
            {jobs.map((job) => (
              <li key={job.id} className={`job-item job-${job.status}`}>
                <div className="job-header">
                  <span className="job-name">{job.inputPath}</span>
                  <span className={`job-status status-${job.status}`}>
                    {t[`conversion.${job.status}`]}
                  </span>
                </div>
                {job.progress !== undefined && job.status === "running" && (
                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{ width: `${job.progress}%` }}
                    />
                  </div>
                )}
                {job.message && <p className="job-message">{job.message}</p>}
                {job.outputPath && (
                  <p className="output-file">
                    Output: <code>{job.outputPath}</code>
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
