import assert from "node:assert/strict";
import test from "node:test";
import {
  contrastRatio,
  defaultAppearance,
  foreground,
  isHexColor,
  normalizeAppearance,
  readableColor,
  themeVariables,
} from "../src/lib/appearance.ts";

test("appearance normalizes invalid server data and keeps independent light and dark palettes", () => {
  for (const value of [null, [], "invalid", { version: 2 }]) {
    assert.deepEqual(normalizeAppearance(value), defaultAppearance());
  }
  const appearance = defaultAppearance();
  appearance.mode = "system";
  appearance.palettes.dark.primary = "#ABCDEF";
  const parsed = normalizeAppearance(appearance);
  assert.equal(parsed.mode, "system");
  assert.equal(parsed.palettes.dark.primary, "#abcdef");
  assert.equal(
    parsed.palettes.light.primary,
    defaultAppearance().palettes.light.primary,
  );
  appearance.palettes.light.primary = "url(https://example.com)";
  assert.equal(
    normalizeAppearance(appearance).palettes.light.primary,
    "#7860cc",
  );
  assert.equal(defaultAppearance().palettes.dark.primary, "#a78bfa");
});

test("custom colors cannot introduce arbitrary CSS", () => {
  for (const color of ["#ffffff", "#A12Bc3", "#000000"])
    assert.ok(isHexColor(color));
  for (const color of ["red", "#123", "#12345678", "#123456;", null, "url(x)"])
    assert.equal(isHexColor(color), false);
});

test("foreground and colored text remain readable on custom surfaces including midtones", () => {
  for (const surface of [
    "#ffffff",
    "#000000",
    "#1c2033",
    "#777777",
    "#808080",
    "#ff0000",
    "#00ff00",
    "#0000ff",
  ]) {
    assert.ok(contrastRatio(foreground(surface), surface) >= 4.5, surface);
    for (const accent of [
      "#ffffff",
      "#000000",
      "#a78bfa",
      "#ffaaaa",
      surface,
    ]) {
      const readable = readableColor(accent, surface);
      assert.ok(
        contrastRatio(readable, surface) >= 4.5,
        `${accent} on ${surface}`,
      );
    }
  }
  const palette = defaultAppearance().palettes.dark;
  const variables = themeVariables(palette);
  assert.equal(variables["--appearance-primary"], palette.primary);
  assert.ok(
    contrastRatio(variables["--appearance-on-primary"], palette.primary) >= 4.5,
  );
});
