export type ThemeMode = "light" | "dark";
export type ThemePreference = ThemeMode | "system";
export type ThemePalette = {
  primary: string;
  background: string;
  surface: string;
  sidebar: string;
  success: string;
  warning: string;
  danger: string;
};
export type Appearance = {
  version: 1;
  mode: ThemePreference;
  palettes: Record<ThemeMode, ThemePalette>;
};

export const DEFAULT_PALETTES: Record<ThemeMode, ThemePalette> = {
  light: {
    primary: "#7860cc",
    background: "#f6f7fb",
    surface: "#ffffff",
    sidebar: "#22233c",
    success: "#258673",
    warning: "#94621b",
    danger: "#c44761",
  },
  dark: {
    primary: "#a78bfa",
    background: "#101321",
    surface: "#1c2033",
    sidebar: "#151829",
    success: "#5ad1a4",
    warning: "#f3bf70",
    danger: "#fb889a",
  },
};

export function defaultAppearance(): Appearance {
  return {
    version: 1,
    mode: "light",
    palettes: {
      light: { ...DEFAULT_PALETTES.light },
      dark: { ...DEFAULT_PALETTES.dark },
    },
  };
}

export function isHexColor(value: unknown): value is string {
  return typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value);
}

export function normalizeAppearance(value: unknown): Appearance {
  const result = defaultAppearance();
  if (!value || typeof value !== "object") return result;
  const data = value as Partial<Appearance>;
  if (data.version !== 1) return result;
  if (data.mode && ["light", "dark", "system"].includes(data.mode))
    result.mode = data.mode;
  for (const mode of ["light", "dark"] as const) {
    for (const key of Object.keys(
      result.palettes[mode],
    ) as (keyof ThemePalette)[]) {
      const color = data.palettes?.[mode]?.[key];
      if (isHexColor(color)) result.palettes[mode][key] = color.toLowerCase();
    }
  }
  return result;
}

function channels(hex: string): number[] {
  return [1, 3, 5].map((start) => parseInt(hex.slice(start, start + 2), 16));
}

function luminance(hex: string): number {
  const [r, g, b] = channels(hex).map((channel) => {
    const value = channel / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(first: string, second: string): number {
  const a = luminance(first),
    b = luminance(second);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

export function foreground(background: string): string {
  if (contrastRatio("#101321", background) >= 4.5) return "#101321";
  return contrastRatio("#ffffff", background) >= 4.5 ? "#ffffff" : "#000000";
}

/** Keep the selected hue when possible, adjusting only text to WCAG AA contrast. */
export function readableColor(color: string, background: string): string {
  if (contrastRatio(color, background) >= 4.5) return color;
  const source = channels(color),
    target = channels(foreground(background));
  for (let step = 1; step <= 20; step++) {
    const mixed =
      "#" +
      source
        .map((channel, i) =>
          Math.round(channel + ((target[i] - channel) * step) / 20)
            .toString(16)
            .padStart(2, "0"),
        )
        .join("");
    if (contrastRatio(mixed, background) >= 4.5) return mixed;
  }
  return foreground(background);
}

export function themeVariables(palette: ThemePalette): Record<string, string> {
  const text = foreground(palette.surface);
  const variables: Record<string, string> = {
    "--appearance-background": palette.background,
    "--appearance-background-text": foreground(palette.background),
    "--appearance-surface": palette.surface,
    "--appearance-text": text,
    "--appearance-sidebar": palette.sidebar,
    "--appearance-sidebar-text": foreground(palette.sidebar),
    "--appearance-primary": palette.primary,
    "--appearance-on-primary": foreground(palette.primary),
    "--appearance-accent": readableColor(palette.primary, palette.surface),
    "--appearance-background-accent": readableColor(
      palette.primary,
      palette.background,
    ),
  };
  for (const key of ["success", "warning", "danger"] as const) {
    variables[`--appearance-${key}`] = readableColor(
      palette[key],
      palette.surface,
    );
    variables[`--appearance-on-${key}`] = foreground(
      variables[`--appearance-${key}`],
    );
  }
  return variables;
}
