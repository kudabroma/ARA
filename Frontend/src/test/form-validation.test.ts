import { describe, expect, it } from "vitest";
import { initialInputs, validateInputs } from "@/lib/ara/api";

const today = new Date("2026-11-15T12:00:00Z");
const filled = {
  ...initialInputs,
  visa: "OPT",
  country: "Kazakhstan",
  stays: [{ visa_type: "OPT", entry_date: "2024-08-20", exit_date: "" }],
  income: { w2_wages: "45000" },
};
const fields = (input: typeof filled) =>
  validateInputs(input, today).map((e) => `${e.field}:${e.message}`);

describe("New calculation form validation", () => {
  it("an empty form is not sent", () => {
    expect(fields(initialInputs)).toEqual([
      "country:errCountry",
      "stays.0.entry_date:errEntry",
      "income:errIncome",
    ]);
  });
  it("a filled form passes; exit date is optional", () => {
    expect(fields(filled)).toEqual([]);
  });
  it("checks entry dates", () => {
    expect(
      fields({ ...filled, stays: [{ visa_type: "OPT", entry_date: "2027-01-01", exit_date: "" }] }),
    ).toEqual(["stays.0.entry_date:errEntryFuture"]);
    expect(
      fields({
        ...filled,
        stays: [{ visa_type: "OPT", entry_date: "2025-05-01", exit_date: "2025-01-01" }],
      }),
    ).toEqual(["stays.0.entry_date:errEntryAfterExit"]);
    expect(fields({ ...filled, stays: [] })).toEqual(["stays:errStays"]);
  });
  it("needs income > 0, a bank statement, or the explicit no-income switch", () => {
    expect(fields({ ...filled, income: { w2_wages: "0" } })).toEqual(["income:errIncome"]);
    expect(fields({ ...filled, income: {}, noIncome: true })).toEqual([]);
    expect(
      fields({ ...filled, income: {}, csv: "date,description,amount\n2026-02-01,Client,2500" }),
    ).toEqual([]);
  });
});
