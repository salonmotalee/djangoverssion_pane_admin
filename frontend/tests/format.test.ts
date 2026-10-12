import test from "node:test";
import assert from "node:assert/strict";
import {
  date,
  isIranianPhone,
  latinDigits,
  queryString,
} from "../src/lib/format.ts";
test("Persian and Arabic digits normalize without altering identifiers", () => {
  assert.equal(latinDigits("۰۹۱۲٣۴۵۶۷۸۹"), "09123456789");
  assert.equal(latinDigits("ABC-۰۱۲"), "ABC-012");
});
test("Iranian phone validation accepts supported formats and rejects incomplete numbers", () => {
  assert.equal(isIranianPhone("۰۹۱۲ ۳۴۵ ۶۷۸۹"), true);
  assert.equal(isIranianPhone("+989123456789"), true);
  assert.equal(isIranianPhone("00989123456789"), true);
  assert.equal(isIranianPhone("091234"), false);
  assert.equal(isIranianPhone("08123456789"), false);
});
test("date-only ISO values format in the Persian calendar without local timezone drift", () => {
  assert.match(date("2026-03-21"), /۱.*فروردین.*۱۴۰۵/);
  assert.equal(date(null), "—");
});
test("query construction excludes empty filters and escapes search terms", () => {
  assert.equal(
    queryString({ page: 2, search: "الف & ب", status: "", deleted: undefined }),
    "page=2&search=%D8%A7%D9%84%D9%81+%26+%D8%A8",
  );
});
