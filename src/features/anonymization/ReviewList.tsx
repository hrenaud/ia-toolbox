import type { en } from "../../app/locales/en";
import type { AnalyzedUnit, Detection } from "../../app/worker/sidecarClient";
import { describeLocation } from "./locationLabels";
import type { ValueRow } from "./review";
import {
  confidenceWord,
  detectionKey,
  groupByEntity,
  groupByValue,
  isSelectable,
} from "./review";

type Translations = Record<keyof typeof en, string>;

interface ReviewListProps {
  detections: Detection[];
  units: AnalyzedUnit[];
  /** Keys of the detections the user has kept, owned by the page. */
  selected: ReadonlySet<string>;
  onSelectionChange: (next: Set<string>) => void;
  t: Translations;
}

/**
 * What one document holds, grouped by type then by value, each row a choice.
 *
 * Grouping is what makes a decision possible on a document with two hundred
 * detections: "every email address" is something a user can decide, "item 47"
 * is not. Grouping by value is the same argument one level down — a name found
 * eight times is one decision, and showing it eight times turned a ten-line
 * document into fifty questions. Each row says its type, how sure the detector
 * is and where it sits, all three in words: this list is the only place the
 * user sees any of it.
 *
 * The values the model is least sure of sit under their own heading at the
 * bottom of their type, because they are mostly ordinary words and reading
 * them mixed into the real ones is what made the list unusable.
 */
export function ReviewList({
  detections,
  units,
  selected,
  onSelectionChange,
  t,
}: ReviewListProps) {
  const toggleGroup = (keys: string[]) => {
    const next = new Set(selected);
    const all = keys.every((key) => next.has(key));
    for (const key of keys) {
      if (all) next.delete(key);
      else next.add(key);
    }
    onSelectionChange(next);
  };

  return (
    <>
      {groupByEntity(detections).map((group) => {
        const label =
          t[`anonymization.entity.${group.entityType}` as keyof Translations] ??
          group.entityType;
        const selectableKeys = group.detections
          .filter((detection) => isSelectable(detection, units))
          .map(detectionKey);

        const rows = groupByValue(group.detections);
        const likely = rows.filter((row) => row.likely);
        const unlikely = rows.filter((row) => !row.likely);

        const renderRow = (row: ValueRow) => {
          const keys = row.detections
            .filter((detection) => isSelectable(detection, units))
            .map(detectionKey);
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
          const confidence =
            t[
              `anonymization.confidence.${confidenceWord(
                Math.max(...row.detections.map((found) => found.score)),
              )}` as keyof Translations
            ];
          const times =
            row.detections.length > 1
              ? t["anonymization.occurrences"].replace(
                  "{count}",
                  String(row.detections.length),
                )
              : "";
          const detail = (
            <>
              <span className="review-text">{row.text}</span>
              <span className="review-meta">
                {label} · {confidence}
                {place && ` · ${place}`}
                {times && ` · ${times}`}
              </span>
            </>
          );
          const key = detectionKey(row.detections[0]);

          // A value the format cannot rewrite is shown and not offered:
          // hiding it would be the user's only sign that it is in the file.
          if (keys.length === 0) {
            return (
              <li className="review-item frozen" key={key}>
                {detail}
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
              <label>
                <input
                  type="checkbox"
                  checked={keys.every((one) => selected.has(one))}
                  onChange={() => toggleGroup(keys)}
                />
                {detail}
              </label>
            </li>
          );
        };

        return (
          <fieldset className="review-group" key={group.entityType}>
            <legend>
              {label} ({rows.length})
            </legend>

            {selectableKeys.length > 0 && (
              <label className="review-group-select">
                <input
                  type="checkbox"
                  checked={selectableKeys.every((key) => selected.has(key))}
                  onChange={() => toggleGroup(selectableKeys)}
                />
                <span>{t["anonymization.selectGroup"]}</span>
              </label>
            )}

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
          </fieldset>
        );
      })}
    </>
  );
}
