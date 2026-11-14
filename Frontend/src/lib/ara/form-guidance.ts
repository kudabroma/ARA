// Presentation only: this never derives residency from dates, visas, or income.
export function formGuidance(status: unknown, visa: string, hasForm8843: boolean) {
  switch (status) {
    case "RESIDENT_ALIEN":
      return {
        form: "Form 1040",
        explanation: "residentFormText" as const,
        checklist: false,
        form8843: false,
      };
    case "NONRESIDENT_ALIEN":
      return {
        form: "Form 1040-NR",
        explanation: "nonresidentFormText" as const,
        checklist: true,
        form8843: hasForm8843 || /^(F|J|M)(?:-|$)/i.test(visa),
      };
    case "DUAL_STATUS_ALIEN":
      return { form: null, explanation: "dualFormText" as const, checklist: true, form8843: false };
    default:
      return null;
  }
}
