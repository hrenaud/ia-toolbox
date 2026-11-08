import type { en } from "../../app/locales/en";
import type { AnalyzedUnit, Detection } from "../../app/worker/sidecarClient";
import { describeLocation } from "./locationLabels";
import type { ValueRow } from "./review";
import {
  ENTITY_TYPES,
  columnPreview,
  confidenceWord,
  detectionKey,
  groupByValue,
  isSelectable,
  showsConfidence,
  valueKey,
} from "./review";

type Translations = Record<keyof typeof en, string>;

interface ReviewListProps {
  detections: Detection[];
  units: AnalyzedUnit[];
  /** Keys of the detections the user has kept, owned by the page. */
  selected: ReadonlySet<string>;
  /** The type the user chose for a value, by `valueKey`, when they chose one. */
  types: Readonly<Record<string, string>>;
  onSelectionChange: (next: Set<string>) => void;
  onTypeChange: (key: string, entityType: string) => void;
  t: Translations;
}

/**
 * What one document holds: one row per value, each row one decision.
 *
 * Grouping by type was the first design and it asked the same question several
 * times — a name found eight times was eight rows, and two models disagreeing
 * about one name put it under two headings, both claiming to be sure. So a
 * value appears once, with the first occurrence in its context, and the type is
 * a proposal in a menu the user can change: their answer applies to every
 * occurrence of that value. Place and count are in words, because this list is
 * the only place the user sees any of it.
 *
 * The values the model is least sure of sit under their own heading at the
 * bottom, because they are mostly ordinary words and reading them mixed into
 * the real ones is what made the list unusable.
 */
export function ReviewList({
  detections,
  units,
  selected,
  types,
  onSelectionChange,
  onTypeChange,
  t,
}: ReviewListProps) {
  const toggleRow = (keys: string[]) => {
    const next = new Set(selected);
    const all = keys.every((key) => next.has(key));
    for (const key of keys) {
      if (all) next.delete(key);
      else next.add(key);
    }
    onSelectionChange(next);
  };

  const typeLabel = (entityType: string) =>
    t[`anonymization.entity.${entityType}` as keyof Translations] ?? entityType;

  const rows = groupByValue(detections);
  const likely = rows.filter((row) => row.likely);
  const unlikely = rows.filter((row) => !row.likely);

  const renderRow = (row: ValueRow) => {
    const key = valueKey(row.detections[0]);
    const keys = row.detections
      .filter((detection) => isSelectable(detection, units))
      .map(detectionKey);
    const entityType = types[key] ?? row.entityType;
    const places = new Set(
      row.detections.map((detection) => {
        const unit = units.find(
          (candidate) => candidate.id === detection.unit_id,
        );
        return unit ? describeLocation(unit.location, t) : "";
      }),
    );
    // One place, or none: naming the first of several would be wrong.
    const place = places.size === 1 ? [...places][0] : "";
    // A column row is about the column, so the column is what it is called,
    // and the values it will replace are the evidence underneath. Naming the
    // first of eight names would be describing the row by one of its answers.
    const label = row.column && place ? place : row.text;
    const excerpt = row.column ? columnPreview(row) : row.excerpt;
    // Nothing to report about a column: the evidence is the column itself, not
    // the characters, so the score is ours and saying "high" would be circular.
    const confidence =
      showsConfidence(entityType) && !row.column
        ? t[
            `anonymization.confidence.${confidenceWord(
              Math.max(...row.detections.map((found) => found.score)),
            )}` as keyof Translations
          ]
        : "";
    const times = row.column
      ? t["anonymization.columnCells"].replace(
          "{count}",
          String(row.detections.length),
        )
      : row.detections.length > 1
        ? t["anonymization.occurrences"].replace(
            "{count}",
            String(row.detections.length),
          )
        : "";
    const meta = [confidence, row.column ? "" : place, times]
      .filter(Boolean)
      .join(" · ");

    // A value the format cannot rewrite is shown and not offered: hiding it
    // would be the user's only sign that it is in the file. Its type is not
    // offered either — correcting it would change nothing.
    if (keys.length === 0) {
      return (
        <li className="review-item frozen" key={key}>
          <span className="review-text">{label}</span>
          <span className="review-meta">
            {[typeLabel(entityType), meta].filter(Boolean).join(" · ")}
          </span>
          {excerpt && <span className="review-excerpt">{excerpt}</span>}
          <span className="review-badge">
            {t["anonymization.notRewritable"]}
          </span>
          <span className="review-help">
            {t["anonymization.notRewritableHelp"]}
          </span>
        </li>
      );
    }

    return (
      <li className="review-item" key={key}>
        <label className="review-choice">
          <input
            type="checkbox"
            checked={keys.every((one) => selected.has(one))}
            onChange={() => toggleRow(keys)}
          />
          <span className="review-text">{label}</span>
          {meta && <span className="review-meta">{meta}</span>}
        </label>
        {excerpt && <span className="review-excerpt">{excerpt}</span>}
        <select
          className="review-type"
          aria-label={t["anonymization.typeOf"].replace("{value}", label)}
          value={entityType}
          onChange={(event) => onTypeChange(key, event.target.value)}
        >
          {/* A type this build does not know is still the worker's answer, so
              it is offered rather than silently turned into something else. */}
          {(ENTITY_TYPES.includes(entityType as (typeof ENTITY_TYPES)[number])
            ? ENTITY_TYPES
            : [entityType, ...ENTITY_TYPES]
          ).map((option) => (
            <option key={option} value={option}>
              {typeLabel(option)}
            </option>
          ))}
        </select>
      </li>
    );
  };

  if (rows.length === 0) return null;

  return (
    <>
      <ul className="review-list">{likely.map(renderRow)}</ul>

      {unlikely.length > 0 && (
        <>
          <p className="review-less-likely">
            <strong>{t["anonymization.lessLikely"]}</strong>
            <span className="review-help">
              {t["anonymization.lessLikelyHelp"]}
            </span>
          </p>
          <ul className="review-list">{unlikely.map(renderRow)}</ul>
        </>
      )}
    </>
  );
}
