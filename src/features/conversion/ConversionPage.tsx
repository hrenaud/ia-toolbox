import { useEffect, useRef, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import { dictionaries, type Locale } from "../../app/i18n";
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
import "./ConversionPage.css";

interface ConversionPageProps {
  locale: Locale;
}

export function ConversionPage({ locale }: ConversionPageProps) {
  const [formats, setFormats] = useState<FormatInfo[]>([]);
  const [formatsLoaded, setFormatsLoaded] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [outputDirectory, setOutputDirectory] = useState<string | null>(null);
  const [isConverting, setIsConverting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [jobs, setJobs] = useState<ConversionJob[]>([]);
  const statusRegionRef = useRef<HTMLDivElement>(null);
  const errorAlertRef = useRef<HTMLDivElement>(null);
  const shouldFocusError = useRef(false);
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

    // Set up drag/drop listener (only in actual Tauri app, not in tests)
    let unlistenDragDrop: (() => void) | null = null;
    try {
      const webview = getCurrentWebview();
      if (webview) {
        void webview
          .onDragDropEvent((event) => {
            if (event.payload.type === "drop") {
              const paths = event.payload.paths;
              if (paths && paths.length > 0) {
                setSelectedFiles((prev) => [...prev, ...paths]);
                setError(null);
              }
            }
          })
          .then((unlisten) => {
            unlistenDragDrop = unlisten;
          })
          .catch((err) => console.error("Failed to set up drag/drop:", err));
      }
    } catch (err) {
      // Drag/drop is not available in test environment
      console.debug("Drag/drop not available:", err);
    }

    return () => {
      void stopClient();
      // Unlisten is async and fires in the background
      if (unlistenDragDrop) {
        unlistenDragDrop();
      }
    };
  }, [t]);

  const handleSelectFiles = async () => {
    try {
      const selected = await open({
        multiple: true,
        title: t["conversion.selectFiles"],
        filters: formats.map((f) => ({
          name: f.label,
          extensions: [f.extension.slice(1)], // Remove the dot
        })),
      });
      if (selected) {
        const paths = Array.isArray(selected) ? selected : [selected];
        setSelectedFiles((prev) => [...prev, ...paths]);
        setError(null);
      }
    } catch (err) {
      console.error("Failed to select files:", err);
      reportBlockingError(t["conversion.fileSelectError"]);
    }
  };

  const handleRemoveFile = (path: string) => {
    setSelectedFiles((prev) => prev.filter((f) => f !== path));
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
      reportBlockingError(t["conversion.outputSelectError"]);
    }
  };

  const getFileBasename = (filePath: string): string => {
    return filePath.split(/[\\/]/).pop() || filePath;
  };

  const upsertJob = (job: ConversionJob) => {
    setJobs((prev) => {
      const existing = prev.find((j) => j.id === job.id);
      if (existing) {
        return prev.map((j) => (j.id === job.id ? { ...j, ...job } : j));
      }
      return [...prev, job];
    });
  };

  const updateStatusMessage = (job: ConversionJob) => {
    const basename = getFileBasename(job.inputPath);
    if (job.status === "running" && job.progress !== undefined) {
      setStatusMessage(
        `${t["conversion.processing"]} ${basename}: ${job.progress}%`,
      );
    } else if (job.status === "success") {
      setStatusMessage(`${t["conversion.successfullyConverted"]} ${basename}`);
    } else if (job.status === "error") {
      setStatusMessage(
        `${t["conversion.errorConverting"]} ${basename}: ${job.message || t["conversion.unknownError"]}`,
      );
    }
  };

  // Report a blocking error raised by a user action: move focus to the alert so
  // it is announced. The alert only exists after the state commit, so this
  // cannot be done inline where setError is called. Errors surfaced without a
  // user action, such as the format catalog failing on mount, keep focus where
  // it is and rely on the alert region alone.
  function reportBlockingError(message: string) {
    shouldFocusError.current = true;
    setError(message);
  }

  useEffect(() => {
    if (error && shouldFocusError.current) {
      shouldFocusError.current = false;
      errorAlertRef.current?.focus();
    }
  }, [error]);

  const handleConvert = async () => {
    if (!outputDirectory) {
      reportBlockingError(t["conversion.outputRequired"]);
      return;
    }

    const supportedFiles = selectedFiles.filter((path) =>
      isSupportedFormat(getFileBasename(path), formats),
    );

    if (supportedFiles.length === 0) {
      reportBlockingError(t["conversion.noSupportedFiles"]);
      return;
    }

    setIsConverting(true);
    setError(null);
    setStatusMessage("");
    setJobs([]);

    try {
      await startConversion(supportedFiles, outputDirectory, (job) => {
        upsertJob(job);
        updateStatusMessage(job);
      });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : t["conversion.unknownError"];
      reportBlockingError(message);
      setStatusMessage(`${t["conversion.errorPrefix"]} ${message}`);
    } finally {
      setIsConverting(false);
    }
  };

  const unsupportedFiles = selectedFiles.filter((path) => {
    const basename = getFileBasename(path);
    const supported = isSupportedFormat(basename, formats);
    const optional = requiresOptionalComponent(basename, formats);
    return !supported && !optional;
  });

  const optionalComponentFiles = selectedFiles.filter((path) => {
    const basename = getFileBasename(path);
    return requiresOptionalComponent(basename, formats);
  });

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

      {/* File selection and management area */}
      <div className="file-input-area">
        <button
          className="file-select-button"
          onClick={() => void handleSelectFiles()}
        >
          {t["conversion.selectFiles"]}
        </button>
        {selectedFiles.length === 0 && (
          <p className="drag-hint">{t["conversion.dragHint"]}</p>
        )}
      </div>

      {/* Selected files list */}
      {selectedFiles.length > 0 && !isConverting && (
        <div className="files-section">
          <h2>{t["conversion.selectedFiles"]}</h2>
          <ul className="file-list">
            {selectedFiles.map((filePath) => {
              const basename = getFileBasename(filePath);
              const supported = isSupportedFormat(basename, formats);
              const optional = requiresOptionalComponent(basename, formats);
              return (
                <li
                  key={filePath}
                  className={`file-item ${supported ? "supported" : optional ? "optional" : "unsupported"}`}
                >
                  <span>{basename}</span>
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
                    onClick={() => handleRemoveFile(filePath)}
                    aria-label={`${t["conversion.removeFile"]} ${basename}`}
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
            <button
              onClick={() => void handleSelectOutput()}
              className="secondary-button"
            >
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
            onClick={() => void handleConvert()}
            disabled={
              isConverting ||
              selectedFiles.length === 0 ||
              !outputDirectory ||
              selectedFiles.every(
                (f) => !isSupportedFormat(getFileBasename(f), formats),
              )
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
        <div
          className="error-message"
          role="alert"
          ref={errorAlertRef}
          tabIndex={-1}
        >
          <p>{error}</p>
          <button
            onClick={() => setError(null)}
            aria-label={t["conversion.closeError"]}
          >
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
                  <span className="job-name">
                    {getFileBasename(job.inputPath)}
                  </span>
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
                    {t["conversion.outputPath"]} <code>{job.outputPath}</code>
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
