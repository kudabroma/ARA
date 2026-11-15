export const BASE_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
export const backendConfigured = () => BASE_URL.length > 0;
/** The only tax year the app works with; every request sends it. */
export const TAX_YEAR = 2026;
export type Language = "en" | "ru" | "es";
export const backendLanguage = (language: Language) => language;
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
/** Recursively drops null/undefined values so the backend falls back to field defaults. */
export function cleanPayload<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.filter((v) => v !== null && v !== undefined).map(cleanPayload) as T;
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([, v]) => v !== null && v !== undefined)
        .map(([k, v]) => [k, cleanPayload(v)]),
    ) as T;
  }
  return value;
}
export type AnalyzeBody = Record<string, any>;
export const analyzeAll = <T = Record<string, any>>(body: AnalyzeBody) =>
  request<T>("/api/analyze-all", cleanPayload(body));
const chatTaxNumbers = [
  "gross_1099_income",
  "business_deductions",
  "w2_wages",
  "w2_federal_withheld",
  "w2_fica_withheld",
] as const;
/** Maps the chat's collected_profile to an analyze-all body; missing numbers become 0, missing strings are omitted. */
export function chatProfileBody(
  profile: Record<string, any>,
  year: number,
  language: Language,
): AnalyzeBody {
  if (profile["residency"])
    return cleanPayload({ ...profile, language: backendLanguage(language) });
  const taxYear = profile["tax_year"] || year;
  const stays = Array.isArray(profile["stays"])
    ? profile["stays"]
    : profile["entry_date"]
      ? [{ visa_type: profile["visa_type"] || "Other", entry_date: profile["entry_date"] }]
      : [];
  const numbers = Object.fromEntries(
    chatTaxNumbers.map((k) => {
      const n = Number(profile[k]);
      return [k, profile[k] === null || profile[k] === undefined || !Number.isFinite(n) ? 0 : n];
    }),
  );
  return cleanPayload({
    language: backendLanguage(language),
    residency: {
      tax_year: taxYear,
      stays,
      country_of_citizenship: profile["country_of_citizenship"],
      prior_exempt_calendar_years: profile["prior_exempt_calendar_years"] || [],
      has_green_card: Boolean(profile["has_green_card"]),
    },
    taxes: {
      tax_year: taxYear,
      visa_type: profile["visa_type"],
      country_of_citizenship: profile["country_of_citizenship"],
      ...numbers,
    },
  });
}
const compactMoney = (n: number) =>
  n >= 1000 ? `$${Math.round(n / 100) / 10}k`.replace(".0k", "k") : `$${Math.round(n)}`;
/** Short history label, e.g. "OPT · W-2 $45k + 1099 $28k". */
export function calculationLabel(body: AnalyzeBody): string {
  const taxes = body["taxes"] || {};
  const visa = taxes.visa_type || body["residency"]?.stays?.[0]?.visa_type || "";
  const income = [
    ["W-2", Number(taxes.w2_wages) || 0],
    ["1099", Number(taxes.gross_1099_income) || 0],
  ]
    .filter(([, v]) => (v as number) > 0)
    .map(([k, v]) => `${k} ${compactMoney(v as number)}`)
    .join(" + ");
  return [visa, income].filter(Boolean).join(" · ") || "—";
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
export type Form8843Payload = {
  tax_year: number;
  first_name: string;
  last_name: string;
  us_address: string;
  home_country_address: string;
  visa_type: string;
  current_nonimmigrant_status: string;
  country_of_citizenship: string;
  country_of_passport: string;
  passport_number: string;
  first_entry_date: string;
  days_present_current_year: number;
  days_present_prior_year_1: number;
  days_present_prior_year_2: number;
  days_excluded_current_year: number;
  is_student: boolean;
  school_or_program_name: string;
  school_or_program_address: string;
  school_or_program_phone: string;
  director_or_dso_name: string;
  director_or_dso_Address: string;
  director_or_dso_phone: string;
};
export function toForm8843Request(uiProfile: Inputs["profile"], taxYear: number): Form8843Payload {
  const text = (key: string) => {
    const value = uiProfile[key];
    return typeof value === "string" ? value : "";
  };
  const number = (key: string) => {
    const parsed = Number(uiProfile[key] || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const name = text("name").trim();
  const firstSpace = name.indexOf(" ");
  return {
    tax_year: taxYear,
    first_name: firstSpace < 0 ? name : name.slice(0, firstSpace),
    last_name: firstSpace < 0 ? "" : name.slice(firstSpace + 1).trim(),
    us_address: text("us_address"),
    home_country_address: text("home_address"),
    visa_type: text("visa_type"),
    current_nonimmigrant_status: text("current_nonimmigrant_status"),
    country_of_citizenship: text("country_of_citizenship"),
    country_of_passport: text("passport_country"),
    passport_number: text("passport_number"),
    first_entry_date: text("first_entry_date"),
    days_present_current_year: number("days_present_current"),
    days_present_prior_year_1: number("days_present_prior_1"),
    days_present_prior_year_2: number("days_present_prior_2"),
    days_excluded_current_year: number("days_excluded"),
    is_student: uiProfile["is_student"] === true,
    school_or_program_name: text("school_name"),
    school_or_program_address: text("school_address"),
    school_or_program_phone: text("school_phone"),
    director_or_dso_name: text("dso_name"),
    director_or_dso_Address: text("dso_address"),
    director_or_dso_phone: text("dso_phone"),
  };
}
/** "Form8843_{LastName}_{year}.pdf"; the last name is reduced to filename-safe characters. */
/** Personal fields Form 8843 needs that a calculation cannot provide. */
export const FORM_8843_PERSONAL_FIELDS = [
  "first_name",
  "last_name",
  "us_address",
  "home_country_address",
  "country_of_passport",
  "passport_number",
] as const;
/** Extra fields for students (Part III of Form 8843). */
export const FORM_8843_STUDENT_FIELDS = ["school_or_program_name", "director_or_dso_name"] as const;
export type Form8843Field =
  (typeof FORM_8843_PERSONAL_FIELDS)[number] | (typeof FORM_8843_STUDENT_FIELDS)[number];
// Visa codes filed as "student" on Form 8843. Annotation only: whether the form is needed at all
// comes from the backend residency result (exempt individual), never from the visa.
const STUDENT_VISAS = new Set([
  "F-1",
  "F-2",
  "OPT",
  "STEM-OPT",
  "J-1",
  "J-1-STUDENT",
  "M-1",
  "M-2",
  "Q-1",
]);

/** Backend fact: the residency result says Form 8843 is required (exempt F/J/M/Q days). */
export function needsForm8843(response: Record<string, any>): boolean {
  const residency = response["residency"] || {};
  const plan: { form_code?: string }[] = Array.isArray(residency.filing_plan)
    ? residency.filing_plan
    : [];
  return (
    residency.exempt_individual_active === true || plan.some((f) => f.form_code === "Form 8843")
  );
}

/**
 * Form 8843 body for one calculation: visa, first entry and day counts come from the calculation
 * (request stays + backend year_breakdown); personal fields from what the user already entered,
 * then from `personal` (the inline form on the Documents page).
 */
export function form8843FromCalculation(
  requestBody: Record<string, any>,
  response: Record<string, any>,
  personal: Partial<Record<Form8843Field, string>> = {},
  inputs?: Inputs,
): { payload: Form8843Payload; isStudent: boolean; missing: Form8843Field[] } {
  const residency = response["residency"] || {};
  const year = Number(residency.tax_year || requestBody["residency"]?.tax_year) || TAX_YEAR;
  const stays: Stay[] = [...(requestBody["residency"]?.stays || [])].sort((x: Stay, y: Stay) =>
    String(x.entry_date).localeCompare(String(y.entry_date)),
  );
  const visa: string =
    requestBody["taxes"]?.visa_type || stays[stays.length - 1]?.visa_type || inputs?.visa || "";
  const rows: { year: number; total_physical_days: number; exempt_days: number }[] = Array.isArray(
    residency.year_breakdown,
  )
    ? residency.year_breakdown
    : [];
  const days = (y: number) => rows.find((r) => r.year === y)?.total_physical_days ?? 0;
  const fromInputs =
    inputs && Object.keys(inputs.profile).length
      ? toForm8843Request({ ...inputs.profile, visa_type: inputs.visa }, year)
      : null;
  const saved = (requestBody["form_8843_profile"] || {}) as Partial<Form8843Payload>;
  const pick = (key: keyof Form8843Payload) =>
    String(personal[key as Form8843Field] ?? saved[key] ?? fromInputs?.[key] ?? "").trim();
  const isStudent = STUDENT_VISAS.has(visa.toUpperCase()) || saved.is_student === true;
  const payload: Form8843Payload = {
    tax_year: year,
    first_name: pick("first_name"),
    last_name: pick("last_name"),
    us_address: pick("us_address"),
    home_country_address: pick("home_country_address"),
    visa_type: visa,
    current_nonimmigrant_status: saved.current_nonimmigrant_status || visa,
    country_of_citizenship:
      saved.country_of_citizenship || requestBody["residency"]?.country_of_citizenship || "",
    country_of_passport: pick("country_of_passport"),
    passport_number: pick("passport_number"),
    first_entry_date: saved.first_entry_date || stays[0]?.entry_date || "",
    days_present_current_year: days(year),
    days_present_prior_year_1: days(year - 1),
    days_present_prior_year_2: days(year - 2),
    days_excluded_current_year: rows.find((r) => r.year === year)?.exempt_days ?? 0,
    is_student: isStudent,
    school_or_program_name: pick("school_or_program_name"),
    school_or_program_address:
      saved.school_or_program_address || fromInputs?.school_or_program_address || "",
    school_or_program_phone:
      saved.school_or_program_phone || fromInputs?.school_or_program_phone || "",
    director_or_dso_name: pick("director_or_dso_name"),
    director_or_dso_Address:
      saved.director_or_dso_Address || fromInputs?.director_or_dso_Address || "",
    director_or_dso_phone: saved.director_or_dso_phone || fromInputs?.director_or_dso_phone || "",
  };
  const required: Form8843Field[] = [
    ...FORM_8843_PERSONAL_FIELDS,
    ...(isStudent ? FORM_8843_STUDENT_FIELDS : []),
  ];
  return { payload, isStudent, missing: required.filter((k) => !payload[k]) };
}
export function form8843FileName(lastName: string, year: number) {
  const safe = lastName
    .normalize("NFKD")
    .replace(/[^\p{L}\p{N}-]+/gu, "")
    .slice(0, 40);
  return safe ? `Form8843_${safe}_${year}.pdf` : `Form8843_${year}.pdf`;
}
export function buildBody(input: Inputs, year: number, language: Language) {
  const income = Object.fromEntries(
    Object.entries(input.income)
      .filter(([, v]) => v !== "")
      .map(([k, v]) => [k, Number(v)]),
  );
  const name = input.profile["name"];
  const formProfile =
    typeof name === "string" && name.trim()
      ? toForm8843Request(
          {
            ...input.profile,
            visa_type: input.visa,
            country_of_citizenship: input.country,
          },
          year,
        )
      : undefined;
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
    ...(formProfile ? { form_8843_profile: formProfile } : {}),
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
    profile: payload["form_8843_profile"]
      ? {
          name: [payload["form_8843_profile"].first_name, payload["form_8843_profile"].last_name]
            .filter(Boolean)
            .join(" "),
          us_address: payload["form_8843_profile"].us_address || "",
          home_address: payload["form_8843_profile"].home_country_address || "",
          current_nonimmigrant_status:
            payload["form_8843_profile"].current_nonimmigrant_status || "",
          passport_country: payload["form_8843_profile"].country_of_passport || "",
          passport_number: payload["form_8843_profile"].passport_number || "",
          first_entry_date: payload["form_8843_profile"].first_entry_date || "",
          days_present_current: String(payload["form_8843_profile"].days_present_current_year ?? 0),
          days_present_prior_1: String(payload["form_8843_profile"].days_present_prior_year_1 ?? 0),
          days_present_prior_2: String(payload["form_8843_profile"].days_present_prior_year_2 ?? 0),
          days_excluded: String(payload["form_8843_profile"].days_excluded_current_year ?? 0),
          is_student: Boolean(payload["form_8843_profile"].is_student),
          school_name: payload["form_8843_profile"].school_or_program_name || "",
          school_address: payload["form_8843_profile"].school_or_program_address || "",
          school_phone: payload["form_8843_profile"].school_or_program_phone || "",
          dso_name: payload["form_8843_profile"].director_or_dso_name || "",
          dso_address: payload["form_8843_profile"].director_or_dso_Address || "",
          dso_phone: payload["form_8843_profile"].director_or_dso_phone || "",
        }
      : {},
  };
}
