import { useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import {
  LockKeyhole,
  ArrowRight,
  FileText,
  ExternalLink,
  ShieldCheck,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { useAra, type CalculationEntry } from "./context";
import { CompareTable, HistoryPanel, entryVisa, useEditEntry } from "./history";
import { money, type Language } from "@/lib/ara/api";
import type { Key } from "@/lib/ara/i18n";
import { formGuidance } from "@/lib/ara/form-guidance";
export function Locked({ children }: { children: ReactNode }) {
  const a = useAra();
  if (a.plan === "pro") return <>{children}</>;
  return (
    <div className="locked-block">
      <div className="locked-content" aria-hidden="true">
        {children}
      </div>
      <div className="lock-overlay">
        <LockKeyhole size={21} className="text-accent-foreground" />
        <Button variant="outline" onClick={() => a.setLock(true)}>
          {a.t("unlock")}
          <ArrowRight />
        </Button>
      </div>
    </div>
  );
}
function Readable({ value }: { value: unknown }) {
  const a = useAra();
  if (value === undefined || value === null) return null;
  if (typeof value === "string")
    return (
      <div className="markdown">
        <ReactMarkdown>{value}</ReactMarkdown>
      </div>
    );
  if (typeof value === "number") return <span>{value}</span>;
  if (typeof value === "boolean") return <span>{a.t(value ? "yes" : "no")}</span>;
  if (Array.isArray(value))
    return (
      <div className="space-y-4">
        {value.map((v, i) => (
          <Readable key={i} value={v} />
        ))}
      </div>
    );
  return null;
}
function formatBackendDates(value: unknown, language: Language) {
  if (typeof value !== "string") return "—";
  return value.replace(/\b\d{4}-\d{2}-\d{2}\b/g, (iso) => {
    const [year, month, day] = iso.split("-").map(Number);
    const date = new Date(Date.UTC(year, month - 1, day));
    if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== iso) return iso;
    return new Intl.DateTimeFormat(language, {
      year: "numeric",
      month: "short",
      day: "numeric",
      timeZone: "UTC",
    }).format(date);
  });
}
export function Results() {
  const a = useAra();
  const edit = useEditEntry();
  const [selected, setSelected] = useState<string[]>([]);
  const [comparing, setComparing] = useState(false);
  // Free shows only the latest calculation; older ones are locked in the history column.
  const shown = a.plan === "free" ? (a.history[0] ?? null) : a.active;
  const existing = selected.filter((id) => a.history.some((e) => e.id === id));
  const compared = a.history.filter((e) => existing.includes(e.id));
  return (
    <>
      <div className="mb-8 flex justify-between items-center">
        <h1 className="page-heading">{a.t("results")}</h1>
        {shown && (
          <Button variant="outline" onClick={() => edit(shown)}>
            {a.t("edit")}
          </Button>
        )}
      </div>
      <div className="results-layout">
        <HistoryPanel
          selected={existing}
          onToggleSelect={(id) =>
            setSelected((prev) =>
              prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id].slice(-2),
            )
          }
          onCompare={() => setComparing(true)}
        />
        {/* With an empty history only the history column (and its empty state) is shown. */}
        {shown && (
          <div className="min-w-0">
            {comparing && a.plan === "pro" && compared.length === 2 && (
              <CompareTable entries={compared} onClose={() => setComparing(false)} />
            )}
            <ResultDetail entry={shown} />
          </div>
        )}
      </div>
    </>
  );
}
function ResultDetail({ entry }: { entry: CalculationEntry }) {
  const a = useAra();
  const r = entry.response,
    taxes = r["taxes"] || {},
    residency = r["residency"] || {};
  const breakdown = [
    "net_self_employment_income",
    "standard_deduction_applied",
    "qbi_deduction_applied",
    "taxable_income",
    "federal_income_tax",
    "self_employment_tax",
  ] as const;
  const tx = r["transactions"]?.transactions || [];
  const transactionData = r["transactions"];
  const yearRows = Array.isArray(residency.year_breakdown) ? residency.year_breakdown : [];
  const filingForms = Array.isArray(residency.filing_plan) ? residency.filing_plan : [];
  const quarterlyRows = Array.isArray(taxes.quarterly_schedule) ? taxes.quarterly_schedule : [];
  const guidance = formGuidance(
    residency.residency_status,
    entryVisa(entry),
    Boolean(r["form_8843"]),
  );
  return (
    <>
      {guidance && (
        <>
          <section className="result-block pt-0" aria-label={a.t("yourForm")}>
            <h2>{a.t("yourForm")}</h2>
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-3xl font-semibold text-accent-foreground">
                {guidance.form || a.t("dualReturn")}
              </p>
              {guidance.form8843 && <span className="status-pill">+ Form 8843</span>}
            </div>
            <p className="mt-4 text-sm leading-7 text-muted-foreground">
              {a.t(guidance.explanation)}
            </p>
            {residency.software_warnings && (
              <div className="notice mt-4">
                <h3 className="mb-2 text-xs font-semibold">{a.t("wrongFormRisk")}</h3>
                <Readable value={residency.software_warnings} />
              </div>
            )}
          </section>
          {guidance.checklist && (
            <section className="result-block" aria-label={a.t("beforeSoftware")}>
              <h2>{a.t("beforeSoftware")}</h2>
              <ul className="space-y-3 text-sm leading-6 text-muted-foreground">
                {(["checkSoftware", "checkUniversity", "checkItin", "checkPreparer"] as const).map(
                  (k) => (
                    <li className="flex gap-3" key={k}>
                      <ShieldCheck size={17} className="mt-1 shrink-0 text-primary" />
                      {a.t(k)}
                    </li>
                  ),
                )}
              </ul>
            </section>
          )}
        </>
      )}
      <div className="glass p-8">
        <span className="status-pill">{residency.status_label || a.t("noData")}</span>
        <p className="mt-6 text-sm text-muted-foreground">
          {a.t(taxes.is_refund ? "refund" : "owe")}
        </p>
        <p
          className={`mt-2 text-5xl font-semibold ${taxes.is_refund ? "text-accent-foreground" : ""}`}
        >
          {money(taxes.net_tax_owed_or_refund)}
        </p>
        {taxes.filing_status_note && (
          <p className="mt-4 text-xs text-muted-foreground">{taxes.filing_status_note}</p>
        )}
      </div>
      {!guidance && residency.software_warnings && (
        <div className="notice mt-4">
          <Readable value={residency.software_warnings} />
        </div>
      )}
      {taxes.erroneous_fica_refund_amount > 0 && (
        <div className="mt-4 rounded-xl border border-border bg-accent p-5 text-accent-foreground">
          <ShieldCheck className="mb-2 size-5" />
          {a.t("found")}: <strong>{money(taxes.erroneous_fica_refund_amount)}</strong>
        </div>
      )}
      <section className="result-block">
        <Locked>
          <div className="stat-grid">
            {[
              ["total_tax_liability", "total_tax"],
              ["self_employment_tax", "self_employment_tax"],
              ["Deduction_tax_savings_usd", "Deduction_tax_savings_usd"],
              ["erroneous_fica_refund_amount", "erroneous_fica_refund_amount"],
            ].map(([field, label]) => (
              <div className="stat" key={field}>
                <p>{a.t(label as Key)}</p>
                <strong>{money(taxes[field])}</strong>
              </div>
            ))}
          </div>
        </Locked>
      </section>
      <section className="result-block">
        <h2>{a.t("breakdown")}</h2>
        <Locked>
          <table className="data-table">
            <tbody>
              {breakdown.map((k) => (
                <tr key={k}>
                  <td>{a.t(k)}</td>
                  <td>{money(taxes[k])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Locked>
      </section>
      <section className="result-block">
        <h2>{a.t("dayCounts")}</h2>
        <Locked>
          {yearRows.length ? (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    {[
                      "yearHeader",
                      "daysInUs",
                      "exemptDays",
                      "countableDays",
                      "multiplier",
                      "weightedCountableDays",
                    ].map((key) => (
                      <th key={key}>{a.t(key as Key)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {yearRows.map((row: any) => (
                    <tr key={row.year}>
                      <td>{row.year}</td>
                      <td>{row.total_physical_days}</td>
                      <td>{row.exempt_days}</td>
                      <td>{row.countable_days}</td>
                      <td>{row.weight}</td>
                      <td>{row.weighted_countable_days}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {yearRows.map((row: any) =>
                row.exempt_reason ? (
                  <p key={`${row.year}-reason`} className="mt-2 text-xs text-muted-foreground">
                    <strong>{row.year} · {a.t("exemptReason")}:</strong> {row.exempt_reason}
                  </p>
                ) : null,
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">{a.t("noData")}</p>
          )}
          <h3 className="my-4 font-medium">{a.t("learnMore")}</h3>
          {filingForms.length ? (
            <div className="grid gap-3">
              {filingForms.map((form: any, i: number) => (
                <article className="rounded-xl border border-border p-4" key={`${form.form_code}-${i}`}>
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <strong>{form.form_code}</strong>
                    <span className="status-pill">
                      {a.t(form.mandatory ? "required" : "optional")}
                    </span>
                  </div>
                  <h4 className="font-medium">{form.title}</h4>
                  <p className="mt-2 text-sm text-muted-foreground">
                    <strong>{a.t("deadline")}:</strong>{" "}
                    {formatBackendDates(form.deadline, a.language)}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{form.reason}</p>
                  {typeof form.official_url === "string" &&
                    form.official_url.startsWith("https://") && (
                      <Button asChild variant="outline" size="sm" className="mt-3">
                        <a href={form.official_url} target="_blank" rel="noopener noreferrer">
                          {a.t("openIRS")}
                          <ExternalLink />
                        </a>
                      </Button>
                    )}
                </article>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">{a.t("noData")}</p>
          )}
        </Locked>
      </section>
      <section className="result-block">
        <h2>{a.t("deductions")}</h2>
        <Locked>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  {["date", "description", "amount", "categories", "schedule"].map((k) => (
                    <th key={k}>{a.t(k as Key)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tx.map((t: any, i: number) => (
                  <tr key={i}>
                    <td>{formatBackendDates(t.date, a.language)}</td>
                    <td>{t.description}</td>
                    <td>{money(t.amount)}</td>
                    <td>
                      <span className="status-pill">{t.classification}</span>
                    </td>
                    <td>{t.schedule_c_category || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {transactionData ? (
            <>
              <dl className="stat-grid mt-4">
                {[
                  ["total_income_1099", "totalIncome1099"],
                  ["total_business_expenses_raw", "businessExpensesRaw"],
                  ["total_deductible_expenses", "deductibleExpenses"],
                  ["total_personal_expenses", "personalExpenses"],
                  ["estimated_total_tax_savings", "estimatedSavings"],
                ].map(([field, label]) => (
                  <div className="stat" key={field}>
                    <dt>{a.t(label as Key)}</dt>
                    <dd>{money(transactionData[field])}</dd>
                  </div>
                ))}
              </dl>
              {transactionData.category_summary &&
                Object.entries(transactionData.category_summary).length > 0 && (
                  <div className="mt-4">
                    <h3 className="mb-2 font-medium">{a.t("categorySummary")}</h3>
                    <ul className="space-y-2 text-sm">
                      {Object.entries(transactionData.category_summary).map(([category, total]) => (
                        <li className="flex justify-between gap-4" key={category}>
                          <span>{category}</span>
                          <strong>{money(total)}</strong>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
            </>
          ) : (
            <p className="mt-4 text-sm text-muted-foreground">{a.t("noData")}</p>
          )}
        </Locked>
      </section>
      <section className="result-block">
        <h2>{a.t("fica")}</h2>
        <Locked>
          <Readable value={taxes.erroneous_fica_explanation || a.t("noData")} />
          <p className="mt-4 text-sm leading-7 text-muted-foreground">{a.t("ficaNextSteps")}</p>
        </Locked>
      </section>
      <section className="result-block">
        <h2>{a.t("quarterly")}</h2>
        <Locked>
          {quarterlyRows.length ? (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    {["quarter", "period", "deadline", "amountDue"].map((key) => (
                      <th key={key}>{a.t(key as Key)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {quarterlyRows.map((row: any) => (
                    <tr key={row.quarter}>
                      <td>{row.quarter}</td>
                      <td>{row.period}</td>
                      <td>{formatBackendDates(row.due_date, a.language)}</td>
                      <td>{money(row.amount_due)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">{a.t("noData")}</p>
          )}
          {typeof taxes.irs_direct_pay_url === "string" &&
            taxes.irs_direct_pay_url.startsWith("https://") && (
              <Button asChild variant="outline" className="mt-4">
                <a href={taxes.irs_direct_pay_url} target="_blank" rel="noopener noreferrer">
                  {a.t("irs")}
                  <ExternalLink />
                </a>
              </Button>
            )}
        </Locked>
      </section>
      <section className="result-block">
        <h2>{a.t("ai")}</h2>
        <Locked>
          <Readable value={r["ai_explanation"]?.explanation_markdown || a.t("noData")} />
        </Locked>
      </section>
      <div className="mt-6 flex flex-wrap items-center gap-4">
        <Button disabled>
          <FileText />
          {a.t("efile")}
        </Button>
        <span className="text-xs text-muted-foreground">{a.t("coming")}</span>
      </div>
    </>
  );
}
