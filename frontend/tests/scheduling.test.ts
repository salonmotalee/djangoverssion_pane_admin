import assert from "node:assert/strict";
import test from "node:test";
import {
  assignmentConflictId,
  authorizedSupervisors,
  calendarWeek,
  initialPreviewChoices,
  jalaliMonth,
  moveDate,
  saturdayWeek,
  selectedScheduleConflicts,
  todayTehran,
  uniqueAssignments,
  validateShift,
  type PreviewRow,
  type SchedulePreview,
} from "../src/lib/scheduling.ts";

test("Persian weeks start on Saturday and remain seven dates across Nowruz", () => {
  assert.equal(saturdayWeek("2026-03-20"), "2026-03-14");
  assert.deepEqual(calendarWeek("2026-03-21"), [
    "2026-03-21",
    "2026-03-22",
    "2026-03-23",
    "2026-03-24",
    "2026-03-25",
    "2026-03-26",
    "2026-03-27",
  ]);
  assert.equal(moveDate("2025-12-31", 1), "2026-01-01");
});

test("Jalali month targeting follows exact Nowruz and month boundaries", () => {
  assert.deepEqual(jalaliMonth("2026-03-20"), {
    year: 1404,
    month: 12,
    day: 29,
  });
  assert.deepEqual(jalaliMonth("2026-03-21"), { year: 1405, month: 1, day: 1 });
  assert.deepEqual(jalaliMonth("2026-04-21"), { year: 1405, month: 2, day: 1 });
  assert.equal(todayTehran(new Date("2026-10-13T21:00:00Z")), "2026-10-14");
});

test("copy preview never selects implicit replacement or duplicates", () => {
  const rows = [
    { index: 0, status: "existing", default_action: "replace" },
    { index: 1, status: "duplicate", default_action: "add" },
    { index: 2, status: "new", default_action: "add" },
  ] as PreviewRow[];
  assert.deepEqual(initialPreviewChoices(rows), [
    { index: 0, action: "preserve" },
    { index: 1, action: "skip" },
    { index: 2, action: "add" },
  ]);
});

test("batch selection includes only supervisors authorized for the chosen hall", () => {
  const supervisors = [
    { id: 1, first_name: "مریم", last_name: "رضایی", halls: [1] },
    { id: 2, first_name: "علی", last_name: "رضایی", halls: [2] },
    { id: 3, first_name: "مریم", last_name: "احمدی", halls: [1, 2] },
  ];
  assert.deepEqual(
    authorizedSupervisors(supervisors, 1, "مریم").map((row) => row.id),
    [1, 3],
  );
  assert.deepEqual(
    authorizedSupervisors(supervisors, 2, "رضایی").map((row) => row.id),
    [2],
  );
});

test("batch proposals deduplicate the same day, hall, shift and supervisor", () => {
  const row = { date: "2026-10-14", hall: 1, shift: 1, supervisor: 1 };
  assert.equal(
    uniqueAssignments([row, row, { ...row, supervisor: 2 }]).length,
    2,
  );
});

test("shift form catches incomplete and reversed intervals before requesting preview", () => {
  assert.ok(validateShift("", "08:00", "10:00"));
  assert.ok(validateShift("صبح", "10:00", "08:00"));
  assert.ok(validateShift("صبح", "08:00", "08:00"));
  assert.equal(validateShift("صبح", "08:00", "10:00"), null);
});

test("selective copy warnings follow surviving selected proposals and removals", () => {
  const preview = {
    conflicts: [
      { left: "row-0", right: "existing-7" },
      { left: "row-0", right: "row-1" },
    ],
  } as SchedulePreview;
  assert.equal(
    selectedScheduleConflicts(
      preview,
      [
        { index: 0, action: "add" },
        { index: 1, action: "skip" },
      ],
      [],
    ).length,
    1,
  );
  assert.equal(
    selectedScheduleConflicts(
      preview,
      [
        { index: 0, action: "add" },
        { index: 1, action: "skip" },
      ],
      [7],
    ).length,
    0,
  );
  assert.equal(
    selectedScheduleConflicts(
      preview,
      [
        { index: 0, action: "replace", replace_ids: [7] },
        { index: 1, action: "add" },
      ],
      [],
    ).length,
    1,
  );
  assert.equal(
    selectedScheduleConflicts(
      preview,
      [
        { index: 0, action: "preserve" },
        { index: 1, action: "skip" },
      ],
      [],
    ).length,
    0,
  );
  assert.equal(assignmentConflictId("existing-7"), 7);
});

test("unavailable copied personnel or shifts remain skipped", () => {
  assert.deepEqual(
    initialPreviewChoices([
      { index: 0, status: "invalid", default_action: "skip" },
    ] as PreviewRow[]),
    [{ index: 0, action: "skip" }],
  );
});
