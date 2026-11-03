import { useState } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fr } from "../../app/locales/fr";
import type { AnalyzedUnit, Detection } from "../../app/worker/sidecarClient";
import { ReviewList } from "./ReviewList";
import { detectionKey } from "./review";

/**
 * This list is the whole point of the two round trips: the user sees what was
 * found and decides, one item at a time or a type at a time. Nothing here may
 * speak in colour alone, and nothing the format cannot rewrite may be offered
 * as a choice — it is still shown, so the user knows it is there.
 */

function detection(fields: Partial<Detection> = {}): Detection {
  return {
    unit_id: "content",
    start: 0,
    end: 11,
    entity_type: "PERSON",
    score: 0.9,
    text: "Jean Dupont",
    likely: true,
    ...fields,
  };
}

const units: AnalyzedUnit[] = [
  { id: "content", location: "document_body", rewritable: true },
  { id: "formulas", location: "sheet_formulas:Ventes", rewritable: false },
];

/** Render with selection state owned outside, as the page owns it. */
function Harness({
  detections,
  onChange = () => {},
}: {
  detections: Detection[];
  onChange?: (next: Set<string>) => void;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  return (
    <ReviewList
      detections={detections}
      units={units}
      selected={selected}
      onSelectionChange={(next) => {
        setSelected(next);
        onChange(next);
      }}
      t={fr}
    />
  );
}

describe("ReviewList", () => {
  it("says what was found, how sure it is, and where it is", () => {
    render(<Harness detections={[detection()]} />);

    const row = screen.getByRole("checkbox", { name: /Jean Dupont/ });

    expect(row).toHaveAccessibleName(
      expect.stringContaining(fr["anonymization.entity.PERSON"]),
    );
    expect(row).toHaveAccessibleName(
      expect.stringContaining(fr["anonymization.confidence.high"]),
    );
    expect(row).toHaveAccessibleName(
      expect.stringContaining(fr["anonymization.location.document_body"]),
    );
  });

  it("groups the detections under a translated type heading", () => {
    render(
      <Harness
        detections={[
          detection(),
          detection({
            entity_type: "EMAIL_ADDRESS",
            start: 20,
            end: 30,
            text: "jean@ex.fr",
          }),
        ]}
      />,
    );

    const groups = screen.getAllByRole("group");

    expect(groups.map((group) => group.textContent)).toEqual([
      expect.stringContaining(fr["anonymization.entity.PERSON"]),
      expect.stringContaining(fr["anonymization.entity.EMAIL_ADDRESS"]),
    ]);
  });

  it("reports one detection to the page when it is ticked", async () => {
    const onChange = vi.fn();
    const found = detection();
    render(<Harness detections={[found]} onChange={onChange} />);

    await userEvent.click(
      screen.getByRole("checkbox", { name: /Jean Dupont/ }),
    );

    expect(onChange).toHaveBeenCalledWith(new Set([detectionKey(found)]));
  });

  it("selects every detection of one type at once", async () => {
    const first = detection();
    const second = detection({ start: 20, end: 25, text: "Marie" });
    const other = detection({
      entity_type: "EMAIL_ADDRESS",
      start: 40,
      end: 50,
      text: "a@b.fr",
    });
    const onChange = vi.fn();
    render(<Harness detections={[first, second, other]} onChange={onChange} />);

    // Each type has its own bulk choice, so this one has to be the person
    // group's: ticking it must leave the email address alone.
    const people = screen.getByRole("group", {
      name: new RegExp(fr["anonymization.entity.PERSON"]),
    });
    await userEvent.click(
      within(people).getByRole("checkbox", {
        name: new RegExp(fr["anonymization.selectGroup"]),
      }),
    );

    expect(onChange).toHaveBeenCalledWith(
      new Set([detectionKey(first), detectionKey(second)]),
    );
  });

  it("unticks a whole type that was fully selected", async () => {
    const first = detection();
    const onChange = vi.fn();
    render(<Harness detections={[first]} onChange={onChange} />);
    const group = screen.getByRole("checkbox", {
      name: new RegExp(fr["anonymization.selectGroup"]),
    });

    await userEvent.click(group);
    await userEvent.click(group);

    expect(onChange).toHaveBeenLastCalledWith(new Set());
  });

  it("asks once about a value found several times", () => {
    const first = detection({ start: 0, end: 11 });
    const second = detection({ start: 40, end: 51 });
    const onChange = vi.fn();
    render(<Harness detections={[first, second]} onChange={onChange} />);

    const row = screen.getByRole("checkbox", { name: /Jean Dupont/ });
    expect(row).toHaveAccessibleName(expect.stringContaining("2"));

    return userEvent.click(row).then(() => {
      // One tick, both occurrences: they would get the same pseudonym anyway.
      expect(onChange).toHaveBeenCalledWith(
        new Set([detectionKey(first), detectionKey(second)]),
      );
    });
  });

  it("puts the values the model is least sure of below the rest", () => {
    render(
      <Harness
        detections={[
          detection({ text: "Participants", start: 0, end: 12, likely: false }),
          detection({ text: "Claire Dubois", start: 20, end: 33 }),
        ]}
      />,
    );

    const people = screen.getByRole("group", {
      name: new RegExp(fr["anonymization.entity.PERSON"]),
    });
    const rows = within(people)
      .getAllByRole("checkbox")
      .map((box) => box.closest("li")?.textContent ?? "");

    expect(rows.at(-1)).toEqual(expect.stringContaining("Participants"));
    expect(screen.getByText(fr["anonymization.lessLikely"])).toBeVisible();
  });

  it("says nothing about likelihood when every value is a solid one", () => {
    render(<Harness detections={[detection()]} />);

    expect(screen.queryByText(fr["anonymization.lessLikely"])).toBeNull();
  });

  it("shows text the format cannot rewrite, without offering it", () => {
    render(
      <Harness
        detections={[detection({ unit_id: "formulas", text: "Jean Dupont" })]}
      />,
    );

    expect(screen.getByText(/Jean Dupont/)).toBeInTheDocument();
    expect(screen.getByText(fr["anonymization.notRewritable"])).toBeVisible();
    expect(screen.queryByRole("checkbox", { name: /Jean Dupont/ })).toBeNull();
  });

  it("offers no bulk choice for a type that is only reported", () => {
    render(<Harness detections={[detection({ unit_id: "formulas" })]} />);

    expect(
      screen.queryByRole("checkbox", {
        name: new RegExp(fr["anonymization.selectGroup"]),
      }),
    ).toBeNull();
  });

  it("names the place a detection sits in, detail included", () => {
    render(
      <Harness
        detections={[detection({ unit_id: "formulas", text: "Marie" })]}
      />,
    );

    expect(screen.getByText(/Formules de la feuille Ventes/)).toBeVisible();
  });

  it("shows nothing at all when the documents were clean", () => {
    render(<Harness detections={[]} />);

    expect(screen.queryAllByRole("group")).toHaveLength(0);
  });
});
