import { useQuery } from "@tanstack/react-query";
import { backendConfigured, backendLanguage, request, type Language } from "@/lib/ara/api";
import { useAra, type CalculationEntry } from "./context";

export type DemoPreset = {
  preset_id: string;
  title: string;
  subtitle?: string;
  description?: string;
  payload: Record<string, any>;
};

/** Demo presets with titles in the given UI language; refetched when the language changes. */
export function useDemoPresets(language: Language) {
  const query = useQuery({
    queryKey: ["demo-presets", language],
    queryFn: () =>
      request<{ presets?: DemoPreset[] } | DemoPreset[]>(
        `/api/demo-presets?language=${backendLanguage(language)}`,
      ),
    enabled: backendConfigured(),
    retry: false,
    placeholderData: (previous) => previous,
  });
  const data = query.data;
  const items: DemoPreset[] = Array.isArray(data) ? data : data?.presets || [];
  return { ...query, items };
}

/** History label in the current UI language: preset entries use the translated preset title. */
export function useEntryLabel() {
  const a = useAra();
  const { items } = useDemoPresets(a.language);
  return (entry: CalculationEntry) =>
    (entry.presetId && items.find((p) => p.preset_id === entry.presetId)?.title) || entry.label;
}
