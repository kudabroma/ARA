import { useState, useEffect, type ReactNode } from "react";
import { initialInputs, type Inputs, type Language } from "@/lib/ara/api";
import { translate } from "@/lib/ara/i18n";
import { AraContext, type Section, type Message } from "./context";
export function AraProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>("en");
  const [year, setYear] = useState(2025);
  const [inputs, setInputs] = useState<Inputs>(initialInputs);
  const [result, setResult] = useState<Record<string, any> | null>(null);
  const [section, setSection] = useState<Section>("new");
  const [lock, setLock] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [chatData, setChatData] = useState<Record<string, any>>({});
  const [sent, setSent] = useState(0);
  useEffect(() => {
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
        plan: "free",
        inputs,
        setInputs,
        result,
        setResult,
        section,
        setSection,
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
