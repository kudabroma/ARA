import { describe, expect, it } from "vitest";
import {
  buildBody,
  backendLanguage,
  canSendChat,
  initialInputs,
  backendConfigured,
  BASE_URL,
} from "@/lib/ara/api";
describe("ARA product rules", () => {
  it("allows five free messages, not six", () => {
    expect(canSendChat("free", 4)).toBe(true);
    expect(canSendChat("free", 5)).toBe(false);
  });
  it("allows unlimited Pro messages", () => {
    expect(canSendChat("pro", 500)).toBe(true);
  });
  it("sends the selected language to the backend", () => {
    expect(backendLanguage("es")).toBe("es");
    expect(backendLanguage("ru")).toBe("ru");
    expect(backendLanguage("en")).toBe("en");
  });
  it("omits empty optional blocks", () => {
    const b = buildBody(initialInputs, 2025, "en");
    expect(b.residency.tax_year).toBe(2025);
    expect(b).not.toHaveProperty("taxes");
    expect(b).not.toHaveProperty("transactions");
    expect(b).not.toHaveProperty("form_8843_profile");
  });
  it("never sends frontend residency status to taxes", () => {
    const b = buildBody({ ...initialInputs, income: { gross_1099_income: "50000" } }, 2026, "es");
    expect(b.taxes).toMatchObject({ gross_1099_income: 50000, tax_year: 2026 });
    expect(b.taxes).not.toHaveProperty("residency_status");
  });
  it("uses the configured backend URL", () => {
    expect(BASE_URL).toBe((import.meta.env.VITE_API_URL ?? "").replace(/\/$/, ""));
    expect(backendConfigured()).toBe(BASE_URL.length > 0);
  });
  it("maps UI Form 8843 fields to the backend contract and requires a name", () => {
    const body = buildBody(
      {
        ...initialInputs,
        profile: {
          name: "Ada Lovelace",
          home_address: "London",
          passport_country: "UK",
          days_present_current: "120",
          days_excluded: "30",
        },
      },
      2025,
      "en",
    );
    expect(body.form_8843_profile).toMatchObject({
      tax_year: 2025,
      first_name: "Ada",
      last_name: "Lovelace",
      home_country_address: "London",
      country_of_passport: "UK",
      days_present_current_year: 120,
      days_excluded_current_year: 30,
    });

    const noName = buildBody(
      { ...initialInputs, profile: { us_address: "123 Main St" } },
      2025,
      "en",
    );
    expect(noName).not.toHaveProperty("form_8843_profile");
  });
});
