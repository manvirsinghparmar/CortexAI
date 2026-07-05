import { describe, expect, it } from "vitest";
import { formatHistoryDateTime } from "../history/historyDate";

describe("formatHistoryDateTime", () => {
  it("uses Today and Yesterday labels for recent history", () => {
    const now = new Date(2026, 5, 10, 15, 30);
    const today = new Date(2026, 5, 10, 9, 5).toISOString();
    const yesterday = new Date(2026, 5, 9, 18, 45).toISOString();

    expect(formatHistoryDateTime(today, now)).toMatch(/^Today, /);
    expect(formatHistoryDateTime(yesterday, now)).toMatch(/^Yesterday, /);
  });

  it("uses a compact calendar date for older history", () => {
    const now = new Date(2026, 5, 10, 15, 30);
    const older = new Date(2026, 4, 2, 11, 0).toISOString();

    expect(formatHistoryDateTime(older, now)).toContain("2026");
  });

  it("returns an empty label for an invalid timestamp", () => {
    expect(formatHistoryDateTime("not-a-date")).toBe("");
  });
});
