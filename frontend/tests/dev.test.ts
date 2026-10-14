import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  copyFileSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

function launch(t: test.TestContext, origin: string, migrationFails = false) {
  const root = mkdtempSync(join(tmpdir(), "madar-dev-test-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const frontend = join(root, "frontend");
  const backend = join(root, "backend");
  const interpreter = join(
    root,
    ".venv",
    process.platform === "win32" ? "Scripts" : "bin",
  );
  const next = join(frontend, "node_modules", "next", "dist", "bin");
  for (const directory of [frontend, backend, interpreter, next])
    mkdirSync(directory, { recursive: true });
  const script = join(frontend, "scripts", "dev.mjs");
  mkdirSync(join(frontend, "scripts"));
  copyFileSync(new URL("../scripts/dev.mjs", import.meta.url), script);
  // Use a portable executable stub for Python; no Python installation is needed.
  copyFileSync(
    process.execPath,
    join(interpreter, process.platform === "win32" ? "python.exe" : "python"),
  );
  const events = join(root, "events.jsonl");
  writeFileSync(
    join(backend, "manage.py"),
    `const fs = require("node:fs");
fs.appendFileSync(process.env.DEV_TEST_EVENTS, JSON.stringify(process.argv.slice(2)) + "\\n");
process.exit(process.env.DEV_TEST_FAIL_MIGRATION === "1" ? 1 : 0);
`,
  );
  writeFileSync(
    join(next, "next"),
    `require("node:fs").appendFileSync(process.env.DEV_TEST_EVENTS, JSON.stringify(["next"]) + "\\n");`,
  );
  const preload = join(root, "ready-api.mjs");
  writeFileSync(
    preload,
    `globalThis.fetch = async () => Response.json({csrfToken: "test-token"}, {headers: {"set-cookie": "csrftoken=test-token"}});`,
  );
  const env = { ...process.env };
  delete env.NODE_OPTIONS;
  const result = spawnSync(process.execPath, ["--import", preload, script], {
    cwd: frontend,
    env: {
      ...env,
      DJANGO_API_ORIGIN: origin,
      DEV_TEST_EVENTS: events,
      DEV_TEST_FAIL_MIGRATION: migrationFails ? "1" : "0",
    },
    encoding: "utf8",
    timeout: 10000,
  });
  assert.ifError(result.error);
  return {
    result,
    events: readFileSync(events, "utf8")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line)),
  };
}

test("a ready local API is migrated before Next.js starts without a second Django server", (t) => {
  const { result, events } = launch(t, "http://127.0.0.1:8000");
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(events, [["migrate", "--noinput"], ["next"]]);
});

test("a failed migration prevents exposing the frontend", (t) => {
  const { result, events } = launch(t, "http://localhost:8000", true);
  assert.equal(result.status, 1);
  assert.deepEqual(events, [["migrate", "--noinput"]]);
});

test("an external API starts the frontend without changing the local database", (t) => {
  const { result, events } = launch(t, "https://api.example.invalid");
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(events, [["next"]]);
});
