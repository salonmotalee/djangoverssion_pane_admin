import assert from "node:assert/strict";
import test from "node:test";
import {
  clockTime,
  compareSessions,
  type StudySession,
} from "../src/lib/operations.ts";

test("all session views can sort chronologically, with deterministic same-start ordering", () => {
  const session = (id: number, start_time: string, end_time: string) =>
    ({ id, start_time, end_time }) as StudySession;
  const rows = [
    session(1, "14:00:00", "16:00:00"),
    session(3, "08:00", "10:00"),
    session(2, "08:00:00", "09:30:00"),
    session(4, "11:00:00", "12:00:00"),
  ];
  assert.deepEqual(
    rows.toSorted(compareSessions).map((row) => row.id),
    [2, 3, 4, 1],
  );
  assert.equal(rows[0].id, 1, "Sorting a view must not mutate API data");
});

test("time-only labels retain their clock value without timezone conversion", () => {
  assert.equal(clockTime("08:30:00"), "۰۸:۳۰");
  assert.equal(clockTime("23:59:00"), "۲۳:۵۹");
});
