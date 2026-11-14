import { describe, expect, it } from "vitest";
import {
  buildBody,
  backendLanguage,
  canSendChat,
  initialInputs,
  backendConfigured,
} from "@/lib/ara/api";
describe("ARA product rules", () => {
  it("allows five free messages, not six", () => {
    expect(canSendChat("free", 4)).toBe(true);
    expect(canSendChat("free", 5)).toBe(false);
  });
  it("allows unlimited Pro messages", () => {
    expect(canSendChat("pro", 500)).toBe(true);
  });
  it("maps Spanish to backend English and Russian to Russian", () => {
    expect(backendLanguage("es")).toBe("en");
    expect(backendLanguage("ru")).toBe("ru");
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
  it("keeps calculations disconnected while URL is a placeholder", () => {
    expect(backendConfigured()).toBe(false);
  });
});
