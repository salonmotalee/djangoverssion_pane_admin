// Start the local API before exposing the development login page.
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const root = resolve(frontend, "..");
const backend = resolve(root, "backend");
const windows = process.platform === "win32";
// Match Next.js development dotenv precedence without overwriting exported values.
for (const name of [
  ".env.development.local",
  ".env.local",
  ".env.development",
  ".env",
]) {
  const path = resolve(frontend, name);
  if (existsSync(path)) process.loadEnvFile(path);
}
const origin = new URL(
  (process.env.DJANGO_API_ORIGIN || "http://127.0.0.1:8000").trim(),
);
const local =
  origin.protocol === "http:" &&
  ["localhost", "127.0.0.1"].includes(origin.hostname) &&
  origin.port === "8000";
const children = [];
const servers = [];

function run(command, args, cwd) {
  const child = spawn(command, args, {
    cwd,
    stdio: "inherit",
    detached: !windows,
  });
  children.push(child);
  child.on("error", (error) => {
    console.error(error.message);
  });
  return child;
}

function completed(child) {
  return new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("exit", (code, signal) => {
      if (code === 0) resolve();
      else
        reject(new Error(`Development process stopped (${code ?? signal}).`));
    });
  });
}

async function apiReady() {
  try {
    const response = await fetch(new URL("/api/auth/csrf/", origin), {
      signal: AbortSignal.timeout(2000),
      redirect: "error",
    });
    const data = await response.json();
    return (
      response.ok &&
      response.headers.get("set-cookie")?.includes("csrftoken=") &&
      typeof data.csrfToken === "string" &&
      data.csrfToken.length > 0
    );
  } catch {
    return false;
  }
}

function stop() {
  for (const child of children) {
    if (!child.pid || child.exitCode !== null || child.signalCode !== null)
      continue;
    if (windows)
      spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
        stdio: "ignore",
      });
    else {
      try {
        process.kill(-child.pid, "SIGTERM");
      } catch (error) {
        if (error.code !== "ESRCH") throw error;
      }
    }
  }
}
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    stop();
    process.exit(0);
  });
}

try {
  if (!(await apiReady())) {
    if (!local)
      throw new Error(
        "DJANGO_API_ORIGIN is unavailable. Start the configured API first.",
      );
    const executable = windows ? "Scripts/python.exe" : "bin/python";
    const python = [
      resolve(root, ".venv", executable),
      resolve(backend, ".venv", executable),
    ].find(existsSync);
    if (!python)
      throw new Error(
        "Create .venv and install backend/requirements.txt first (see README).",
      );
    await completed(
      run(python, ["manage.py", "migrate", "--noinput"], backend),
    );
    const api = run(
      python,
      ["manage.py", "runserver", "127.0.0.1:8000"],
      backend,
    );
    // Attach immediately, including during readiness polling.
    const apiExit = completed(api);
    servers.push(apiExit);
    apiExit.catch(() => {});
    const deadline = Date.now() + 30000;
    while (!(await apiReady())) {
      if (api.exitCode !== null || api.signalCode !== null) await apiExit;
      if (Date.now() >= deadline)
        throw new Error(
          "Django did not become ready. Inspect its startup output and backend/.env.",
        );
      await new Promise((resolve) => setTimeout(resolve, 200));
    }
  }
  console.log("Django CSRF endpoint ready; starting Next.js.");
  const require = createRequire(import.meta.url);
  const next = run(
    process.execPath,
    [
      require.resolve("next/dist/bin/next"),
      "dev",
      "--hostname",
      "127.0.0.1",
      ...process.argv.slice(2),
    ],
    frontend,
  );
  servers.push(completed(next));
  await Promise.race(servers);
  // A server exiting cleanly still ends this combined development session.
  if (next.exitCode !== null) console.log("Next.js stopped.");
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
} finally {
  stop();
}
