import assert from "node:assert/strict";
import test from "node:test";
import type { Hall } from "../src/lib/operations.ts";
import {
  editableSupervisorHalls,
  loadSupervisorHalls,
  normalizeSupervisorPhone,
  supervisorStatus,
  type Supervisor,
} from "../src/lib/supervisors.ts";

test("supervisor phones normalize Persian, Arabic and international mobile formats", () => {
  assert.equal(normalizeSupervisorPhone("۰۹۱۲ ۳۴۵-۶۷۸۹"), "09123456789");
  assert.equal(normalizeSupervisorPhone("٠٩١٢٣٤٥٦٧٨٩"), "09123456789");
  assert.equal(normalizeSupervisorPhone("+98 912 345 6789"), "09123456789");
  assert.equal(normalizeSupervisorPhone("0098-912-345-6789"), "09123456789");
  assert.equal(normalizeSupervisorPhone("02112345678"), null);
  assert.equal(normalizeSupervisorPhone("0912345678"), null);
});

test("archived status stays distinct from inactive collaboration", () => {
  const supervisor = { is_active: false, archived_at: null } as Supervisor;
  assert.equal(supervisorStatus(supervisor), "inactive");
  assert.equal(supervisorStatus({ ...supervisor, is_active: true }), "active");
  assert.equal(
    supervisorStatus({ ...supervisor, archived_at: "2026-10-14T10:00:00Z" }),
    "archived",
  );
  assert.equal(
    supervisorStatus({
      ...supervisor,
      is_active: true,
      archived_at: "2026-10-14T10:00:00Z",
    }),
    "archived",
  );
});

test("editing excludes archived hall links and preserves input records", () => {
  const supervisor = {
    hall_details: [
      { id: 2, name: "فعال", is_active: true },
      { id: 3, name: "بایگانی", is_active: false },
    ],
  } as Supervisor;
  assert.deepEqual(editableSupervisorHalls(supervisor), [2]);
  assert.equal(supervisor.hall_details.length, 2);
  assert.deepEqual(editableSupervisorHalls(), []);
});

test("hall assignment choices load beyond the first hundred and deduplicate records", async () => {
  const requests: number[] = [];
  const halls = await loadSupervisorHalls(async (page) => {
    requests.push(page);
    return {
      count: 205,
      previous: page === 1 ? null : "previous",
      next: page < 3 ? "next" : null,
      results: Array.from(
        { length: page === 3 ? 6 : 100 },
        (_, index) =>
          ({
            id: page === 3 ? 200 + index : (page - 1) * 100 + index + 1,
            name: `سالن ${page}-${index}`,
            is_active: true,
          }) as Hall,
      ),
    };
  });
  assert.deepEqual(requests, [1, 2, 3]);
  assert.equal(halls.length, 205);
  assert.equal(halls.at(-1)?.id, 205);
});

test("hall choice failures reject instead of saving a partial assignment list", async () => {
  await assert.rejects(
    loadSupervisorHalls(async (page) => {
      if (page === 2) throw new Error("page 2 unavailable");
      return { count: 101, previous: null, next: "next", results: [] };
    }),
    /page 2 unavailable/,
  );
});
