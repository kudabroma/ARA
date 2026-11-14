import { createContext, useContext } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { Inputs, Language } from "@/lib/ara/api";
import type { Key } from "@/lib/ara/i18n";

export type Section = "new" | "chat" | "results" | "documents";
export type Message = { role: "user" | "assistant"; content: string };
export type State = {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: Key) => string;
  year: number;
  setYear: (year: number) => void;
  plan: "free" | "pro";
  setPlan: (plan: "free" | "pro") => void;
  inputs: Inputs;
  setInputs: Dispatch<SetStateAction<Inputs>>;
  result: Record<string, any> | null;
  setResult: (result: Record<string, any>) => void;
  section: Section;
  setSection: (section: Section) => void;
  lock: boolean;
  setLock: (locked: boolean) => void;
  messages: Message[];
  setMessages: Dispatch<SetStateAction<Message[]>>;
  chatData: Record<string, any>;
  setChatData: (data: Record<string, any>) => void;
  sent: number;
  setSent: Dispatch<SetStateAction<number>>;
};

// Preserve only the context identity across preview hot updates, never user data.
// Session values still live in AraProvider's React state, including during SSR.
export const AraContext =
  (import.meta.hot?.data?.["araContext"] as React.Context<State | null> | undefined) ??
  createContext<State | null>(null);
if (import.meta.hot?.data) import.meta.hot.data["araContext"] = AraContext;

export function useAra() {
  const value = useContext(AraContext);
  if (!value) throw new Error("ARA provider missing");
  return value;
}
