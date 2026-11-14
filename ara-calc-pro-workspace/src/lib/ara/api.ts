export const BASE_URL = "https://YOUR-VERCEL-BACKEND.vercel.app";
export const backendConfigured = () => !BASE_URL.includes("YOUR-VERCEL-BACKEND");
export type Language = "en" | "ru" | "es";
export const backendLanguage = (language: Language) => (language === "ru" ? "ru" : "en");
export const canSendChat = (plan: "free" | "pro", sent: number) => plan === "pro" || sent < 5;
export class ApiError extends Error {
  constructor(
    message: string,
    public status = 0,
    public fields: string[] = [],
  ) {
    super(message);
  }
}
export async function request<T>(path: string, body?: unknown): Promise<T> {
  if (!backendConfigured()) throw new ApiError("not_connected");
  let response: Response;
  try {
    response = await fetch(
      `${BASE_URL}${path}`,
      body
        ? {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          }
        : { method: "GET" },
    );
  } catch {
    throw new ApiError("network_error");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const details = Array.isArray(data.detail) ? data.detail : [];
    throw new ApiError(
      typeof data.detail === "string" ? data.detail : data.message || "invalid_input",
      response.status,
      details.map((e: { loc?: string[] }) => e.loc?.join(".") || ""),
    );
  }
  return data as T;
}
export const money = (value: unknown) =>
  typeof value === "number"
    ? new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      }).format(value)
    : "—";
export type Stay = { visa_type: string; entry_date: string; exit_date: string };
export type Inputs = {
  visa: string;
  country: string;
  green: boolean;
  exempt: string;
  stays: Stay[];
  filing: string;
  income: Record<string, string>;
  csv: string;
  manual: { date: string; description: string; amount: string }[];
  transactionMode: "csv" | "manual";
  profile: Record<string, string | boolean>;
};
export const initialInputs: Inputs = {
  visa: "OPT",
  country: "",
  green: false,
  exempt: "",
  stays: [{ visa_type: "OPT", entry_date: "", exit_date: "" }],
  filing: "single",
  income: {},
  csv: "",
  manual: [],
  transactionMode: "csv",
  profile: {},
};
export function buildBody(input: Inputs, year: number, language: Language) {
  const income = Object.fromEntries(
    Object.entries(input.income)
      .filter(([, v]) => v !== "")
      .map(([k, v]) => [k, Number(v)]),
  );
  return {
    language: backendLanguage(language),
    residency: {
      tax_year: year,
      stays: input.stays
        .filter((s) => s.entry_date)
        .map((s) => ({ ...s, exit_date: s.exit_date || null })),
      prior_exempt_calendar_years: input.exempt
        .split(/[,\s]+/)
        .filter(Boolean)
        .map(Number),
      has_green_card: input.green,
      country_of_citizenship: input.country,
      closer_connection_eligible: false,
    },
    ...(Object.keys(income).length
      ? {
          taxes: {
            tax_year: year,
            filing_status: input.filing,
            visa_type: input.visa,
            country_of_citizenship: input.country,
            ...income,
          },
        }
      : {}),
    ...(input.transactionMode === "csv" && input.csv.trim()
      ? { transactions: { tax_year: year, csv_text: input.csv } }
      : input.manual.length && input.transactionMode === "manual"
        ? {
            transactions: {
              tax_year: year,
              transactions: input.manual.map((t) => ({ ...t, amount: Number(t.amount) })),
            },
          }
        : {}),
    ...(Object.keys(input.profile).length
      ? {
          form_8843_profile: Object.fromEntries(
            Object.entries(input.profile)
              .filter(([, v]) => v !== "")
              .map(([k, v]) => [k, k.startsWith("days_") ? Number(v) : v]),
          ),
        }
      : {}),
  };
}
export function presetInputs(payload: Record<string, any>): Inputs {
  const r = payload["residency"] || {},
    t = payload["taxes"] || {};
  return {
    ...initialInputs,
    visa: t.visa_type || r.stays?.[0]?.visa_type || "OPT",
    country: r.country_of_citizenship || t.country_of_citizenship || "",
    green: r.has_green_card || false,
    exempt: (r.prior_exempt_calendar_years || []).join(", "),
    stays: r.stays?.length
      ? r.stays.map((s: Stay) => ({ ...s, exit_date: s.exit_date || "" }))
      : initialInputs.stays,
    filing: t.filing_status || "single",
    income: Object.fromEntries(
      [
        "w2_wages",
        "w2_federal_withheld",
        "w2_fica_withheld",
        "gross_1099_income",
        "business_deductions",
        "estimated_payments_already_made",
      ]
        .filter((k) => t[k] !== undefined)
        .map((k) => [k, String(t[k])]),
    ),
    csv: payload["transactions"]?.csv_text || "",
    profile: payload["form_8843_profile"] || {},
  };
}
