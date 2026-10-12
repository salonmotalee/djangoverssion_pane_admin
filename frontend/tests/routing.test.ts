import assert from "node:assert/strict";
import test from "node:test";
import {
  CENTRAL_ROUTES,
  isPortalSlug,
  RESERVED_SLUGS,
} from "../src/lib/routing.ts";

test("system paths cannot be organization slugs", () => {
  for (const slug of [...CENTRAL_ROUTES, ...RESERVED_SLUGS]) {
    assert.equal(isPortalSlug(slug), false, slug);
  }
});

test("public slugs use a stable lowercase single path segment", () => {
  for (const slug of [
    "aftab",
    "hall-123",
    "org-legacy01",
    "a12",
    "a".repeat(48),
  ]) {
    assert.equal(isPortalSlug(slug), true, slug);
  }
  for (const slug of [
    "Aftab",
    "ab",
    "",
    "aftab/dashboard",
    "a--b",
    "-hall",
    "hall-",
    "a".repeat(49),
    "آفتاب",
    "_next",
  ]) {
    assert.equal(isPortalSlug(slug), false, slug);
  }
});
