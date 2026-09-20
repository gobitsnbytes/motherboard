import { describe, expect, test } from "bun:test";

import { ageOnDate } from "./onboarding-age";

const today = new Date(2026, 8, 20);

describe("ageOnDate", () => {
  test("calculates age after the birthday", () => {
    expect(ageOnDate("2010-08-02", today)).toBe(16);
  });

  test("calculates age before the birthday", () => {
    expect(ageOnDate("2008-10-01", today)).toBe(17);
  });

  test("handles the eighteenth birthday boundary", () => {
    expect(ageOnDate("2008-09-20", today)).toBe(18);
  });

  test("rejects malformed, impossible, and future dates", () => {
    expect(ageOnDate("20-09-2010", today)).toBeNull();
    expect(ageOnDate("2010-02-30", today)).toBeNull();
    expect(ageOnDate("2027-01-01", today)).toBeNull();
  });
});
