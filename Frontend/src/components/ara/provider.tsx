import { useState, useEffect, useCallback, type ReactNode } from "react";
import { initialInputs, type Inputs, type Language } from "@/lib/ara/api";
import { translate } from "@/lib/ara/i18n";
import {
  AraContext,
  HISTORY_LIMIT,
  type CalculationEntry,
  type Section,
  type Message,
  type Theme,
} from "./context";

const THEME_KEY = "ara-theme";
/** Switch the <html> theme class; colours cross-fade for 200 ms unless reduced motion is on. */
function applyTheme(next: Theme, setState: (t: Theme) => void) {
  const root = document.documentElement;
  const animate = !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  if (animate) root.classList.add("theme-switching");
  root.classList.toggle("dark", next === "dark");
  root.style.colorScheme = next;
  setState(next);
  if (animate) window.setTimeout(() => root.classList.remove("theme-switching"), 250);
}

export function AraProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>("en");
  const [plan, setPlan] = useState<"free" | "pro">("pro");
  const [inputs, setInputs] = useState<Inputs>(initialInputs);
  const [history, setHistory] = useState<CalculationEntry[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const addEntry = useCallback((entry: Omit<CalculationEntry, "id" | "createdAt">) => {
    const id = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    setHistory((prev) =>
      [{ ...entry, id, createdAt: Date.now() }, ...prev].slice(0, HISTORY_LIMIT),
    );
    setActiveId(id);
  }, []);
  const updateEntry = useCallback((id: string, patch: Partial<CalculationEntry>) => {
    setHistory((prev) => prev.map((e) => (e.id === id ? { ...e, ...patch } : e)));
  }, []);
  const removeEntry = useCallback((id: string) => {
    setHistory((prev) => {
      const next = prev.filter((e) => e.id !== id);
      setActiveId((current) => (current === id ? (next[0]?.id ?? null) : current));
      return next;
    });
  }, []);
  const active = history.find((e) => e.id === activeId) ?? null;
  const [section, setSection] = useState<Section>("chat");
  const [pendingForm8843, setPendingForm8843] = useState(false);
  const openForm8843 = useCallback(() => {
    setPendingForm8843(true);
    setSection("new");
  }, []);
  const clearPendingForm8843 = useCallback(() => setPendingForm8843(false), []);
  const [lock, setLock] = useState(false);
  // Pro never shows the "Pro feature" dialog, even if it was open when the plan switched.
  useEffect(() => {
    if (plan === "pro") setLock(false);
  }, [plan]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [chatData, setChatData] = useState<Record<string, any>>({});
  const [sent, setSent] = useState(0);
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("plan") === "free") {
      setPlan("free");
    }
    try {
      const l = localStorage.getItem("ara-language");
      if (l === "en" || l === "ru" || l === "es") setLanguageState(l);
    } catch {}
  }, []);
  // Theme: <html class="dark"> is already set before paint by the script in __root.tsx.
  const [theme, setThemeState] = useState<Theme>("light");
  useEffect(() => {
    const root = document.documentElement;
    setThemeState(root.classList.contains("dark") ? "dark" : "light");
    let saved: string | null = null;
    try {
      saved = localStorage.getItem(THEME_KEY);
    } catch {
      // storage blocked (private mode): fall back to the system theme
    }
    if (saved === "light" || saved === "dark") return;
    // No manual choice yet: follow the system setting live.
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!media) return;
    const onChange = () => applyTheme(media.matches ? "dark" : "light", setThemeState);
    media.addEventListener?.("change", onChange);
    return () => media.removeEventListener?.("change", onChange);
  }, []);
  const setTheme = useCallback((next: Theme) => {
    applyTheme(next, setThemeState);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      // storage blocked (private mode): fall back to the system theme
    }
  }, []);
  const setLanguage = (l: Language) => {
    setLanguageState(l);
    try {
      localStorage.setItem("ara-language", l);
    } catch {}
  };
  return (
    <AraContext.Provider
      value={{
        language,
        setLanguage,
        t: (k) => translate(language, k),
        plan,
        setPlan,
        theme,
        setTheme,
        inputs,
        setInputs,
        history,
        activeId,
        setActiveId,
        addEntry,
        updateEntry,
        removeEntry,
        active,
        result: active?.response ?? null,
        section,
        setSection,
        pendingForm8843,
        openForm8843,
        clearPendingForm8843,
        lock,
        setLock,
        messages,
        setMessages,
        chatData,
        setChatData,
        sent,
        setSent,
      }}
    >
      {children}
    </AraContext.Provider>
  );
}
