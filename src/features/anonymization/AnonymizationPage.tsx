import { useEffect, useRef, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import { dictionaries, type Locale } from "../../app/i18n";
import type { FormatInfo, KeptDetection } from "../../app/worker/sidecarClient";
import {
  analyzeDocuments,
  anonymizeDocuments,
  loadAnonymizationFormats,
  stopClient,
  type AnalyzedDocument,
} from "./anonymizationApi";
import { ReviewList } from "./ReviewList";
import {
  anonymizedName,
  describeAnonymizationError,
  detectionKey,
  isSelectable,
} from "./review";
import "./AnonymizationPage.css";

interface AnonymizationPageProps {
  locale: Locale;
}

/** What the user is doing: picking files, deciding, or reading the outcome. */
type Phase = "select" | "analyzing" | "review" | "writing" | "results";

/** Keys of the kept detections, per document path. */
type Selection = Record<string, Set<string>>;

function basenameOf(path: string): string {
  return path.split(/[\\/]/).pop() || path;
}

export function AnonymizationPage({ locale }: AnonymizationPageProps) {
  const [formats, setFormats] = useState<FormatInfo[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [outputDirectory, setOutputDirectory] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("select");
  const [documents, setDocuments] = useState<AnalyzedDocument[]>([]);
  const [selection, setSelection] = useState<Selection>({});
  const [operator, setOperator] = useState("replace");
  const [results, setResults] = useState<AnalyzedDocument[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const errorAlertRef = useRef<HTMLDivElement>(null);
  const shouldFocusError = useRef(false);
  const t = dictionaries[locale];

  useEffect(() => {
    loadAnonymizationFormats()
      .then(setFormats)
      .catch(() => setError(t["anonymization.formatLoadError"]));

    return () => {
      void stopClient();
    };
  }, [t]);

  // Native drag and drop, subscribed exactly once for the lifetime of the
  // page: tying it to the dictionary would re-subscribe on every language
  // change and add every dropped file twice.
  useEffect(() => {
    let cancelled = false;
    let unlisten: (() => void) | null = null;

    try {
      void getCurrentWebview()
        .onDragDropEvent((event) => {
          if (event.payload.type !== "drop") return;
          const paths = event.payload.paths;
          if (paths && paths.length > 0) {
            setSelectedFiles((prev) => [...prev, ...paths]);
            setError(null);
          }
        })
        .then((unsubscribe) => {
          if (cancelled) {
            void unsubscribe();
            return;
          }
          unlisten = unsubscribe;
        })
        .catch((err) => console.error("Failed to set up drag/drop:", err));
    } catch (err) {
      // Drag and drop is not available in the test environment.
      console.debug("Drag/drop not available:", err);
    }

    return () => {
      cancelled = true;
      if (unlisten) void unlisten();
    };
  }, []);

  // Report a failure the user caused, and move focus to it. The alert only
  // exists after the state commit, so the focus call cannot happen inline.
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

  const isSupported = (path: string) =>
    formats.some((format) =>
      basenameOf(path).toLowerCase().endsWith(format.extension.toLowerCase()),
    );

  const handleSelectFiles = async () => {
    try {
      const selected = await open({
        multiple: true,
        title: t["anonymization.selectFiles"],
        filters: formats.map((format) => ({
          name: format.label,
          extensions: [format.extension.slice(1)],
        })),
      });
      if (selected) {
        const paths = Array.isArray(selected) ? selected : [selected];
        setSelectedFiles((prev) => [...prev, ...paths]);
        setError(null);
      }
    } catch (err) {
      console.error("Failed to select files:", err);
      reportBlockingError(t["anonymization.fileSelectError"]);
    }
  };

  const handleSelectOutput = async () => {
    try {
      const selected = await open({
        directory: true,
        title: t["anonymization.selectOutput"],
      });
      if (selected) setOutputDirectory(selected as string);
    } catch (err) {
      console.error("Failed to select output directory:", err);
      reportBlockingError(t["anonymization.outputSelectError"]);
    }
  };

  const upsert = (setter: typeof setDocuments, document: AnalyzedDocument) => {
    setter((prev) => {
      const index = prev.findIndex(
        (item) => item.inputPath === document.inputPath,
      );
      if (index === -1) return [...prev, document];
      const next = [...prev];
      next[index] = document;
      return next;
    });
  };

  const handleAnalyze = async () => {
    if (!outputDirectory) {
      reportBlockingError(t["anonymization.outputRequired"]);
      return;
    }
    const supported = selectedFiles.filter(isSupported);
    if (supported.length === 0) {
      reportBlockingError(t["anonymization.noSupportedFiles"]);
      return;
    }

    setPhase("analyzing");
    setError(null);
    setDocuments([]);
    setSelection({});
    setResults([]);
    setStatusMessage(t["anonymization.analyzing"]);

    try {
      await analyzeDocuments(supported, (document) =>
        upsert(setDocuments, document),
      );
      setPhase("review");
    } catch (err) {
      setPhase("select");
      reportBlockingError(
        err instanceof Error ? err.message : t["anonymization.unknownError"],
      );
    }
  };

  /** Every detection the user could keep, document by document. */
  const selectableKeys = (document: AnalyzedDocument): string[] =>
    document.detections
      .filter((detection) => isSelectable(detection, document.units))
      .map(detectionKey);

  const total = documents.reduce(
    (count, document) => count + selectableKeys(document).length,
    0,
  );
  const kept = Object.values(selection).reduce(
    (count, keys) => count + keys.size,
    0,
  );

  const setAll = (select: boolean) => {
    const next: Selection = {};
    if (select) {
      for (const document of documents) {
        next[document.inputPath] = new Set(selectableKeys(document));
      }
    }
    setSelection(next);
  };

  const handleAnonymize = async () => {
    const pending = documents
      .map((document) => {
        const keys = selection[document.inputPath] ?? new Set<string>();
        const detections: KeptDetection[] = document.detections
          .filter((detection) => keys.has(detectionKey(detection)))
          .map(({ unit_id, start, end, entity_type }) => ({
            unit_id,
            start,
            end,
            entity_type,
          }));
        return { inputPath: document.inputPath, detections };
      })
      .filter((document) => document.detections.length > 0);

    if (pending.length === 0 || !outputDirectory) return;

    setPhase("writing");
    setError(null);
    setResults([]);
    setStatusMessage(t["anonymization.writing"]);

    try {
      await anonymizeDocuments(
        pending,
        { outputDirectory, operator, language: locale },
        (document) => {
          upsert(setResults, document);
          setStatusMessage(
            document.status === "error"
              ? `${t["anonymization.errorPrefix"]} ${basenameOf(document.inputPath)} — ${describeAnonymizationError(document.errorCode, document.message, t)}`
              : `${t["anonymization.written"]} — ${basenameOf(document.inputPath)}`,
          );
        },
      );
      setPhase("results");
    } catch (err) {
      setPhase("review");
      reportBlockingError(
        err instanceof Error ? err.message : t["anonymization.unknownError"],
      );
    }
  };

  const unsupportedFiles = selectedFiles.filter((path) => !isSupported(path));
  const hasPdf = unsupportedFiles.some((path) =>
    path.toLowerCase().endsWith(".pdf"),
  );
  const inSelection = phase === "select" || phase === "analyzing";

  return (
    <div className="anonymization-page">
      <div role="status" aria-live="polite" className="announcement">
        {phase === "review"
          ? t["anonymization.kept"]
              .replace("{count}", String(kept))
              .replace("{total}", String(total))
          : statusMessage}
      </div>

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
            aria-label={t["anonymization.closeError"]}
          >
            ✕
          </button>
        </div>
      )}

      {inSelection && (
        <>
          {formats.length > 0 && (
            <section className="format-section">
              <h2>{t["anonymization.supportedFormats"]}</h2>
              <p className="format-list">
                {formats.map((format) => format.label).join(", ")}
              </p>
            </section>
          )}

          <div className="file-input-area">
            <button
              className="file-select-button"
              onClick={() => void handleSelectFiles()}
            >
              {t["anonymization.selectFiles"]}
            </button>
            {selectedFiles.length === 0 && (
              <p className="drag-hint">{t["anonymization.dragHint"]}</p>
            )}
          </div>

          {selectedFiles.length > 0 && (
            <section className="files-section">
              <h2>{t["anonymization.selectedFiles"]}</h2>
              <ul className="file-list">
                {selectedFiles.map((path) => (
                  <li
                    key={path}
                    className={`file-item ${isSupported(path) ? "supported" : "unsupported"}`}
                  >
                    <span>{basenameOf(path)}</span>
                    {!isSupported(path) && (
                      <span className="status-badge unsupported">
                        {t["anonymization.unsupported"]}
                      </span>
                    )}
                    <button
                      className="remove-button"
                      onClick={() =>
                        setSelectedFiles((prev) =>
                          prev.filter((item) => item !== path),
                        )
                      }
                      aria-label={`${t["anonymization.removeFile"]} ${basenameOf(path)}`}
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>

              {hasPdf && <p className="info">{t["anonymization.pdfNotice"]}</p>}
            </section>
          )}

          <section className="output-section">
            <button
              className="secondary-button"
              onClick={() => void handleSelectOutput()}
            >
              {outputDirectory
                ? t["anonymization.changeOutput"]
                : t["anonymization.selectOutput"]}
            </button>
            {outputDirectory && (
              <p className="output-path">
                {t["anonymization.outputPath"]} <code>{outputDirectory}</code>
              </p>
            )}
            <p className="output-help">{t["anonymization.outputHelp"]}</p>
          </section>

          <button
            className="primary"
            onClick={() => void handleAnalyze()}
            disabled={selectedFiles.length === 0 || phase === "analyzing"}
          >
            {phase === "analyzing"
              ? t["anonymization.analyzing"]
              : t["anonymization.analyze"]}
          </button>
        </>
      )}

      {(phase === "review" || phase === "writing") && (
        <section className="review-section">
          <h2>{t["anonymization.review"]}</h2>
          <p>{t["anonymization.reviewHelp"]}</p>

          <div className="bulk-actions">
            <button className="secondary-button" onClick={() => setAll(true)}>
              {t["anonymization.selectAll"]}
            </button>
            <button className="secondary-button" onClick={() => setAll(false)}>
              {t["anonymization.clearAll"]}
            </button>
          </div>

          {documents.map((document) => (
            <section className="document-section" key={document.inputPath}>
              <h3>{basenameOf(document.inputPath)}</h3>

              {document.status === "error" && (
                <p className="document-error">
                  {describeAnonymizationError(
                    document.errorCode,
                    document.message,
                    t,
                  )}
                </p>
              )}

              {document.status === "success" &&
                document.detections.length === 0 && (
                  <p className="document-clean">
                    {t["anonymization.nothingFound"]}
                  </p>
                )}

              <ReviewList
                detections={document.detections}
                units={document.units}
                selected={selection[document.inputPath] ?? new Set<string>()}
                onSelectionChange={(next) =>
                  setSelection((prev) => ({
                    ...prev,
                    [document.inputPath]: next,
                  }))
                }
                t={t}
              />

              {document.notes.length > 0 && (
                <div className="document-notes">
                  <h4>{t["anonymization.notes"]}</h4>
                  <ul>
                    {document.notes.map((note) => (
                      <li key={note}>
                        {t[`anonymization.note.${note}` as keyof typeof t] ??
                          note}
                        {/* The worker reports no reference count, so the
                            number of cells a shared value reaches cannot be
                            stated — only that there is more than one. */}
                        {note === "xlsx_shared_strings_reused" && (
                          <span className="note-detail">
                            {t["anonymization.sharedValue"]}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {document.status === "success" &&
                document.detections.length > 0 && (
                  <p className="output-preview">
                    {t["anonymization.confirmFile"].replace(
                      "{name}",
                      anonymizedName(document.inputPath, locale),
                    )}
                  </p>
                )}
            </section>
          ))}

          <fieldset className="operator-choice">
            <legend>{t["anonymization.operator"]}</legend>
            {(["replace", "mask"] as const).map((choice) => (
              <label key={choice}>
                <input
                  type="radio"
                  name="operator"
                  value={choice}
                  checked={operator === choice}
                  onChange={() => setOperator(choice)}
                />
                <span>{t[`anonymization.operator.${choice}`]}</span>
              </label>
            ))}
          </fieldset>

          <button
            className="primary"
            onClick={() => void handleAnonymize()}
            disabled={kept === 0 || phase === "writing"}
          >
            {phase === "writing"
              ? t["anonymization.writing"]
              : t["anonymization.confirm"]}
          </button>

          <button
            className="secondary-button"
            onClick={() => setPhase("select")}
            disabled={phase === "writing"}
          >
            {t["anonymization.back"]}
          </button>
        </section>
      )}

      {phase === "results" && (
        <section className="results-section">
          <h2>{t["anonymization.written"]}</h2>
          <ul className="result-list">
            {results.map((document) => (
              <li
                key={document.inputPath}
                className={`result-item result-${document.status}`}
              >
                <span className="result-name">
                  {basenameOf(document.inputPath)}
                </span>
                <span className="result-status">
                  {t[`anonymization.status.${document.status}`]}
                </span>
                {document.outputPath && (
                  <p className="output-file">
                    {t["anonymization.outputPath"]}{" "}
                    <code>{document.outputPath}</code>
                  </p>
                )}
                {document.status === "error" && (
                  <p className="result-error">
                    {describeAnonymizationError(
                      document.errorCode,
                      document.message,
                      t,
                    )}
                  </p>
                )}
              </li>
            ))}
          </ul>

          <button
            className="secondary-button"
            onClick={() => {
              setPhase("select");
              setSelectedFiles([]);
              setDocuments([]);
              setSelection({});
              setResults([]);
            }}
          >
            {t["anonymization.back"]}
          </button>
        </section>
      )}
    </div>
  );
}
