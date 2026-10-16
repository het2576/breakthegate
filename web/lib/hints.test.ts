import { describe, expect, it } from "vitest";

import { GOAL_HINTS, LEVEL_HINTS, hintsFor } from "./hints";

describe("hints", () => {
  it("has three hints for each open level and one for each of the 12 goals", () => {
    for (const level of [1, 2, 3, 4]) expect(LEVEL_HINTS[level]).toHaveLength(3);
    for (let goal = 1; goal <= 12; goal++) expect(GOAL_HINTS[goal]).toBeTruthy();
  });

  it("puts the goal hint last and gives nothing for a locked level without a goal", () => {
    expect(hintsFor(1, 1)).toHaveLength(4);
    expect(hintsFor(1, 1).at(-1)).toMatch(/^For this goal:/);
    expect(hintsFor(5, 99)).toEqual([]);
  });

  it("points at ideas and never hands over a full command", () => {
    const all = [...Object.values(LEVEL_HINTS).flat(), ...Object.values(GOAL_HINTS)].join("\n");
    expect(all).not.toMatch(/rm -r|ssh-copy-id|pipx install|authorized_keys|--index-url|<\(curl/);
  });

  it("follows the copy rules: no em dashes, no arrows", () => {
    const all = [...Object.values(LEVEL_HINTS).flat(), ...Object.values(GOAL_HINTS)].join("\n");
    expect(all).not.toMatch(/[—→]/);
  });
});
