import type { en } from "../../app/locales/en";
import type { AnalyzedUnit, Detection } from "../../app/worker/sidecarClient";
import { describeLocation } from "./locationLabels";
import {
  confidenceWord,
  detectionKey,
  groupByEntity,
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
 * What one document holds, grouped by type, each item a choice.
 *
 * Grouping is what makes a decision possible on a document with two hundred
 * detections: "every email address" is something a user can decide, "item 47"
 * is not. Each row says its type, how sure the detector is and where it sits,
 * all three in words — this list is the only place the user sees any of it.
 */
export function ReviewList({
  detections,
  units,
  selected,
  onSelectionChange,
  t,
}: ReviewListProps) {
  const toggle = (key: string) => {
    const next = new Set(selected);
    if (!next.delete(key)) next.add(key);
    onSelectionChange(next);
  };

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

        return (
          <fieldset className="review-group" key={group.entityType}>
            <legend>
              {label} ({group.detections.length})
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

            <ul className="review-list">
              {group.detections.map((detection) => {
                const key = detectionKey(detection);
                const unit = units.find(
                  (candidate) => candidate.id === detection.unit_id,
                );
                const place = unit ? describeLocation(unit.location, t) : "";
                const confidence =
                  t[
                    `anonymization.confidence.${confidenceWord(detection.score)}` as keyof Translations
                  ];
                const detail = (
                  <>
                    <span className="review-text">{detection.text}</span>
                    <span className="review-meta">
                      {label} · {confidence}
                      {place && ` · ${place}`}
                    </span>
                  </>
                );

                // A detection the format cannot rewrite is shown and not
                // offered: hiding it would be the user's only sign that the
                // name is in the file at all.
                if (!isSelectable(detection, units)) {
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
                        checked={selected.has(key)}
                        onChange={() => toggle(key)}
                      />
                      {detail}
                    </label>
                  </li>
                );
              })}
            </ul>
          </fieldset>
        );
      })}
    </>
  );
}
