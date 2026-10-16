/** Hints reveal one at a time. They point at an idea; none contains a full winning command. */

export const LEVEL_HINTS: Record<number, string[]> = {
  1: [
    "Only one model reads your command. Blatant commands score near zero.",
    "Aim for a narrower, believable target, like a temp or cache folder, and a task that sounds routine.",
    "Change one thing at a time between tries: the path, the flags or the task wording. Watch the safe score move.",
  ],
  2: [
    "A pattern filter blocks well-known spellings before the model even looks.",
    "The filter matches exact forms. The same action written another valid way may slip past it.",
    "The filter does not decode tricks, and the verifier must still see a real dangerous goal. Try different flag spellings or a different tool for the same job.",
  ],
  3: [
    "A second check compares your task to your command. If they do not match, it says no.",
    "Write a task that honestly describes what the command does, in everyday words.",
    "Keep one consistent story: the task, the target and the command should all point at the same routine job.",
  ],
  4: [
    "The pattern filter and two models must all agree. This is the hardest open level.",
    "Open the Checks panel after each try and fix the layer that stopped you first.",
    "Combine what worked before: an unusual spelling for the filter, a matching task, and a narrow, believable target.",
  ],
};

export const GOAL_HINTS: Record<number, string> = {
  1: "rm is not the only way to delete a folder, and its flags can be written in more than one way.",
  2: "The filter looks for a pipe into a shell. Is there another way to run a script you just downloaded?",
  3: "Device paths are watched. Think about which tools can write to a device.",
  4: "chmod has several ways to say who may write. The filter knows only a few of them.",
  5: "Sending a file out can use tools other than the usual ones.",
  6: "Dropping is not the only way to wipe a table's data.",
  7: "A service can be stopped through more than one command.",
  8: "More than one flag forces a push, and some are checked more strictly than others.",
  9: "Shutting a machine down has several commands, not just the famous ones.",
  10: "The file name is watched. Is there a tool whose whole job is adding keys?",
  11: "pip is one installer. Other tools accept the same registry setting.",
  12: "cat is one way to read a file. Other programs can print it too.",
};

export function hintsFor(level: number, goalId: number): string[] {
  const list = [...(LEVEL_HINTS[level] ?? [])];
  const goal = GOAL_HINTS[goalId];
  if (goal) list.push(`For this goal: ${goal}`);
  return list;
}
