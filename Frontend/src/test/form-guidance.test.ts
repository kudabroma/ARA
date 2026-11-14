import { describe, it, expect } from "vitest";
import { formGuidance } from "@/lib/ara/form-guidance";

describe("Backend residency form guidance", () => {
  it("shows Form 1040 only for backend resident status", () => {
    expect(formGuidance("RESIDENT_ALIEN", "F-1", true)).toMatchObject({
      form: "Form 1040",
      checklist: false,
      form8843: false,
    });
  });
  it("shows Form 1040-NR and the checklist for backend nonresident status", () => {
    expect(formGuidance("NONRESIDENT_ALIEN", "H-1B", false)).toMatchObject({
      form: "Form 1040-NR",
      checklist: true,
      form8843: false,
    });
  });
  it("adds Form 8843 for F, J, or M visas for nonresidents", () => {
    for (const visa of ["F-1", "J-1", "M-1"])
      expect(formGuidance("NONRESIDENT_ALIEN", visa, false)?.form8843).toBe(true);
  });
  it("adds Form 8843 when the backend returns it for a nonresident", () => {
    expect(formGuidance("NONRESIDENT_ALIEN", "OPT", true)?.form8843).toBe(true);
  });
  it("shows dual-status guidance and checklist only for backend dual status", () => {
    expect(formGuidance("DUAL_STATUS_ALIEN", "H-1B", false)).toMatchObject({
      form: null,
      explanation: "dualFormText",
      checklist: true,
    });
  });
  it("does not infer residency from a visa when status is missing or unknown", () => {
    expect(formGuidance(undefined, "F-1", true)).toBeNull();
    expect(formGuidance("UNKNOWN", "H-1B", false)).toBeNull();
  });
});
