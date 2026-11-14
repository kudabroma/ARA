import { useState, useEffect, useCallback, type ReactNode } from "react";
import { initialInputs, type Inputs, type Language } from "@/lib/ara/api";
import { translate } from "@/lib/ara/i18n";
import {
  AraContext,
  HISTORY_LIMIT,
  type CalculationEntry,
  type Section,
  type Message,
} from "./context";
export function AraProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>("en");
  const [year, setYear] = useState(2025);
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
        year,
        setYear,
        plan,
        setPlan,
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
