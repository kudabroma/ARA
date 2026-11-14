import { describe, expect, it } from "vitest";
import { isFutureExpiry, isLuhnValid, isValidCvc, isValidEmail } from "@/lib/ara/checkout-validation";

describe("test checkout validation", () => {
  it("accepts a valid test card and rejects a failed Luhn checksum", () => {
    expect(isLuhnValid("4242 4242 4242 4242")).toBe(true);
    expect(isLuhnValid("4242 4242 4242 4241")).toBe(false);
  });

  it("requires a current-or-future MM/YY expiry", () => {
    const now = new Date(2025, 10, 14);
    expect(isFutureExpiry("11/25", now)).toBe(true);
    expect(isFutureExpiry("12/25", now)).toBe(true);
    expect(isFutureExpiry("10/25", now)).toBe(false);
    expect(isFutureExpiry("13/30", now)).toBe(false);
  });

  it("validates email and three- or four-digit CVC", () => {
    expect(isValidEmail("test@example.com")).toBe(true);
    expect(isValidEmail("not-an-email")).toBe(false);
    expect(isValidCvc("123")).toBe(true);
    expect(isValidCvc("1234")).toBe(true);
    expect(isValidCvc("12")).toBe(false);
  });
});
