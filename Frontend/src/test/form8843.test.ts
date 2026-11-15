import { describe, expect, it } from "vitest";
import { form8843FromCalculation, needsForm8843, TAX_YEAR } from "@/lib/ara/api";

// analyze-all request + response of a chat calculation: F-1 since Sep 2023, no Form 8843 profile
const request = {
  residency: {
    tax_year: TAX_YEAR,
    country_of_citizenship: "Kazakhstan",
    stays: [{ visa_type: "F-1", entry_date: "2023-09-01" }],
  },
  taxes: { tax_year: TAX_YEAR, visa_type: "F-1", gross_1099_income: 85000 },
};
const response = {
  residency: {
    tax_year: TAX_YEAR,
    exempt_individual_active: true,
    filing_plan: [{ form_code: "Form 8843" }, { form_code: "Form 1040-NR" }],
    year_breakdown: [
      { year: 2026, total_physical_days: 365, exempt_days: 365 },
      { year: 2025, total_physical_days: 365, exempt_days: 365 },
      { year: 2024, total_physical_days: 366, exempt_days: 366 },
    ],
  },
};

describe("Form 8843 from a calculation", () => {
  it("is needed only when the backend says so", () => {
    expect(needsForm8843(response)).toBe(true);
    expect(needsForm8843({ residency: { exempt_individual_active: false, filing_plan: [] } })).toBe(
      false,
    );
  });

  it("asks only for personal fields; visa, dates and days come from the calculation", () => {
    const base = form8843FromCalculation(request, response);
    expect(base.isStudent).toBe(true);
    expect(base.missing).toEqual([
      "first_name",
      "last_name",
      "us_address",
      "home_country_address",
      "country_of_passport",
      "passport_number",
      "school_or_program_name",
      "director_or_dso_name",
    ]);
    expect(base.payload).toMatchObject({
      tax_year: 2026,
      visa_type: "F-1",
      first_entry_date: "2023-09-01",
      country_of_citizenship: "Kazakhstan",
      days_present_current_year: 365,
      days_present_prior_year_1: 365,
      days_present_prior_year_2: 366,
      days_excluded_current_year: 365,
      is_student: true,
    });
  });

  it("is complete once the inline form is filled", () => {
    const personal = {
      first_name: "Aigerim",
      last_name: "Nurlanova",
      us_address: "1 Main St",
      home_country_address: "Astana",
      country_of_passport: "Kazakhstan",
      passport_number: "N1",
      school_or_program_name: "State University",
      director_or_dso_name: "J. Doe",
    };
    const filled = form8843FromCalculation(request, response, personal);
    expect(filled.missing).toEqual([]);
    expect(filled.payload.last_name).toBe("Nurlanova");
  });

  it("reuses a saved profile, so nothing is asked again", () => {
    const withProfile = {
      ...request,
      form_8843_profile: {
        first_name: "Demo",
        last_name: "Raman",
        us_address: "x",
        home_country_address: "y",
        country_of_passport: "India",
        passport_number: "DEMO",
        school_or_program_name: "Demo U",
        director_or_dso_name: "Demo DSO",
      },
    };
    expect(form8843FromCalculation(withProfile, response).missing).toEqual([]);
  });
});
