export type ThemeMode = "light" | "dark" | "system";

export interface ColorwayOption {
  id: string;
  name: string;
  swatchBg: string;
  swatchAccent: string;
}

export const LIGHT_COLORWAYS: ColorwayOption[] = [
  { id: "warm", name: "Warm", swatchBg: "#f5f2ec", swatchAccent: "#b3633f" },
  {
    id: "porcelain",
    name: "Porcelain",
    swatchBg: "#f7f8fa",
    swatchAccent: "#5a6b8c",
  },
  { id: "sage", name: "Sage", swatchBg: "#f2f5ef", swatchAccent: "#6f8f5f" },
  {
    id: "blossom",
    name: "Blossom",
    swatchBg: "#faf4f3",
    swatchAccent: "#b0655f",
  },
];

export const DARK_COLORWAYS: ColorwayOption[] = [
  {
    id: "graphite",
    name: "Graphite",
    swatchBg: "#221f1d",
    swatchAccent: "#d08a66",
  },
  {
    id: "midnight",
    name: "Midnight",
    swatchBg: "#1b2027",
    swatchAccent: "#5fa8a4",
  },
  { id: "forest", name: "Forest", swatchBg: "#1d211b", swatchAccent: "#93ad7e" },
  { id: "amoled", name: "AMOLED", swatchBg: "#000000", swatchAccent: "#9d6cf3" },
];

const DEFAULT_LIGHT_COLORWAY = "warm";
const DEFAULT_DARK_COLORWAY = "graphite";

export function resolveTheme(mode: ThemeMode): "light" | "dark" {
  if (mode === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }
  return mode;
}

export function colorwaysFor(mode: ThemeMode): ColorwayOption[] {
  return resolveTheme(mode) === "dark" ? DARK_COLORWAYS : LIGHT_COLORWAYS;
}

export function applyTheme(mode: ThemeMode, colorway: string | null): void {
  const resolved = resolveTheme(mode);
  const root = document.documentElement;
  root.dataset.theme = resolved;

  const familyDefaults = {
    light: DEFAULT_LIGHT_COLORWAY,
    dark: DEFAULT_DARK_COLORWAY,
  };
  const familyOptions = (resolved === "dark" ? DARK_COLORWAYS : LIGHT_COLORWAYS).map(
    (c) => c.id,
  );
  const valid =
    colorway && familyOptions.includes(colorway)
      ? colorway
      : familyDefaults[resolved];
  root.dataset.colorway = valid;
}
