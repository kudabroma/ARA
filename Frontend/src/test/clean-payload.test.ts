import { describe, expect, it } from "vitest";
import { chatProfileBody, cleanPayload, presetInputs } from "@/lib/ara/api";
import { fieldLabel } from "@/lib/ara/i18n";

describe("cleanPayload", () => {
  it("removes null and undefined recursively but keeps 0, false and empty strings", () => {
    expect(
      cleanPayload({ a: null, b: undefined, c: 0, d: false, e: "", f: { g: null, h: [1, null] } }),
    ).toEqual({ c: 0, d: false, e: "", f: { h: [1] } });
  });
});

describe("chatProfileBody", () => {
  const partial = {
    tax_year: 2025,
    visa_type: "OPT",
    entry_date: "2023-08-15",
    country_of_citizenship: null,
    gross_1099_income: 28000,
    business_deductions: 4500,
    w2_wages: null,
    w2_federal_withheld: null,
    w2_fica_withheld: null,
  };
  it("never sends null: numbers become 0, strings are omitted", () => {
    const body = chatProfileBody(partial, 2025, "ru");
    expect(JSON.stringify(body)).not.toContain("null");
    expect(body["taxes"]).toMatchObject({
      w2_wages: 0,
      w2_federal_withheld: 0,
      w2_fica_withheld: 0,
    });
    expect(body["taxes"]).not.toHaveProperty("country_of_citizenship");
    expect(body["residency"]).not.toHaveProperty("country_of_citizenship");
    expect(body["residency"].stays).toEqual([{ visa_type: "OPT", entry_date: "2023-08-15" }]);
  });
  it("can be carried into the form", () => {
    const inputs = presetInputs(chatProfileBody(partial, 2025, "en"));
    expect(inputs.visa).toBe("OPT");
    expect(inputs.income["gross_1099_income"]).toBe("28000");
  });
});

describe("fieldLabel", () => {
  it("localizes backend validation locations", () => {
    expect(fieldLabel("ru", "body.taxes.w2_wages")).toBe("Зарплата W-2");
    expect(fieldLabel("en", "body.residency.country_of_citizenship")).toBe(
      "Country of citizenship",
    );
  });
});
