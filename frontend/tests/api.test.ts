import assert from "node:assert/strict";
import test from "node:test";
import { ApiError, ensureCsrf, mutate, resetCsrf } from "../src/lib/api.ts";

test("login sends one fresh CSRF request before submitting credentials", async (t) => {
  const requests: { path: string; options?: RequestInit }[] = [];
  t.mock.method(
    globalThis,
    "fetch",
    async (path: string, options?: RequestInit) => {
      requests.push({ path, options });
      return Response.json(
        path.endsWith("csrf/")
          ? { csrfToken: "fresh-token" }
          : { username: "admin" },
      );
    },
  );
  resetCsrf();
  const result = await mutate<{ username: string }>("auth/login/", "POST", {
    username: "admin",
    password: "test-only-password",
  });
  assert.equal(result.username, "admin");
  assert.deepEqual(
    requests.map((request) => request.path),
    ["/api/auth/csrf/", "/api/auth/login/"],
  );
  assert.equal(
    new Headers(requests[1].options?.headers).get("X-CSRFToken"),
    "fresh-token",
  );
  assert.equal(requests[1].options?.credentials, "include");
});

test("unavailable or invalid CSRF responses prevent login and allow a later retry", async (t) => {
  for (const response of [
    new Response("Bad Gateway", { status: 502 }),
    new Response("<html>wrong API destination</html>"),
    Response.json({}),
    Response.json({ csrfToken: "" }),
  ]) {
    let calls = 0;
    const mock = t.mock.method(globalThis, "fetch", async () => {
      calls += 1;
      return response;
    });
    await assert.rejects(
      mutate("auth/login/", "POST", {}),
      (error: unknown) => {
        assert.ok(error instanceof ApiError);
        assert.equal(
          error.message,
          "سرویس ورود در دسترس نیست. کمی بعد دوباره تلاش کنید.",
        );
        return true;
      },
    );
    assert.equal(calls, 1, "Credentials must not be sent without a CSRF token");
    mock.mock.restore();
  }
  t.mock.method(globalThis, "fetch", async () =>
    Response.json({ csrfToken: "recovered-token" }),
  );
  assert.equal(await ensureCsrf(), "recovered-token");
});

test("connection failures are reported as an unavailable login service", async (t) => {
  t.mock.method(globalThis, "fetch", async () => {
    throw new TypeError("fetch failed");
  });
  await assert.rejects(ensureCsrf(), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 0);
    assert.equal(
      error.message,
      "سرویس ورود در دسترس نیست. کمی بعد دوباره تلاش کنید.",
    );
    return true;
  });
});
