import { create } from 'zustand';

export type ThemeMode = 'light' | 'dark' | 'system';
export type FontScale = 0.85 | 1 | 1.15 | 1.3;

const storageKey = 'ops-ui-settings-v1';

interface SavedSettings {
  themeMode?: unknown;
  fontScale?: unknown;
  humanReview?: unknown;
}

interface SettingsState {
  themeMode: ThemeMode;
  fontScale: FontScale;
  humanReview: boolean;
  setThemeMode: (themeMode: ThemeMode) => void;
  setFontScale: (fontScale: FontScale) => void;
  setHumanReview: (humanReview: boolean) => void;
}

const themeModes = new Set<ThemeMode>(['light', 'dark', 'system']);
const fontScales: FontScale[] = [0.85, 1, 1.15, 1.3];

function isThemeMode(value: unknown): value is ThemeMode {
  return typeof value === 'string' && themeModes.has(value as ThemeMode);
}

function isFontScale(value: unknown): value is FontScale {
  return typeof value === 'number' && fontScales.includes(value as FontScale);
}

function loadSettings(): Required<SavedSettings> {
  if (typeof window === 'undefined') {
    return { themeMode: 'dark', fontScale: 1, humanReview: false };
  }

  try {
    const legacyTheme = window.localStorage.getItem('hisar-theme');
    const parsed = JSON.parse(window.localStorage.getItem(storageKey) ?? '{}') as SavedSettings;
    const themeMode = isThemeMode(parsed.themeMode)
      ? parsed.themeMode
      : legacyTheme === 'light' || legacyTheme === 'dark'
        ? legacyTheme
        : 'dark';

    return {
      themeMode,
      fontScale: isFontScale(parsed.fontScale) ? parsed.fontScale : 1,
      humanReview: typeof parsed.humanReview === 'boolean' ? parsed.humanReview : false,
    };
  } catch {
    return { themeMode: 'dark', fontScale: 1, humanReview: false };
  }
}

function saveSettings(state: Pick<SettingsState, 'themeMode' | 'fontScale' | 'humanReview'>) {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(storageKey, JSON.stringify(state));
  } catch {
    // localStorage may be unavailable; settings still work in memory.
  }
}

const initial = loadSettings();

export const useSettingsStore = create<SettingsState>((set) => ({
  themeMode: initial.themeMode as ThemeMode,
  fontScale: initial.fontScale as FontScale,
  humanReview: initial.humanReview as boolean,
  setThemeMode: themeMode => set(state => {
    const next = { ...state, themeMode };
    saveSettings(next);
    return next;
  }),
  setFontScale: fontScale => set(state => {
    const next = { ...state, fontScale };
    saveSettings(next);
    return next;
  }),
  setHumanReview: humanReview => set(state => {
    const next = { ...state, humanReview };
    saveSettings(next);
    return next;
  }),
}));
