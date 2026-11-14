import { type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import {
  ChartNoAxesCombined,
  LockKeyhole,
  ArrowRight,
  Download,
  FileText,
  ExternalLink,
  ShieldCheck,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { useAra } from "./context";
import { money } from "@/lib/ara/api";
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
  if (value === undefined || value === null) return null;
  if (typeof value === "string")
    return (
      <div className="markdown">
        <ReactMarkdown>{value}</ReactMarkdown>
      </div>
    );
  if (typeof value === "number" || typeof value === "boolean") return <span>{String(value)}</span>;
  if (Array.isArray(value))
    return (
      <div className="space-y-4">
        {value.map((v, i) => (
          <Readable key={i} value={v} />
        ))}
      </div>
    );
  if (typeof value === "object")
    return (
      <dl className="space-y-3">
        {Object.entries(value).map(([k, v]) => (
          <div key={k} className="border-b border-border pb-3">
            <dt className="mb-1 text-xs font-medium text-muted-foreground">
              {k.replaceAll("_", " ")}
            </dt>
            <dd>
              <Readable value={v} />
            </dd>
          </div>
        ))}
      </dl>
    );
  return null;
}
export function Results() {
  const a = useAra();
  if (!a.result)
    return (
      <>
        <h1 className="page-heading">{a.t("results")}</h1>
        <div className="empty-view">
          <span className="empty-icon">
            <ChartNoAxesCombined size={30} />
          </span>
          <h2>{a.t("empty")}</h2>
          <p>{a.t("emptyHint")}</p>
          <Button onClick={() => a.setSection("new")}>
            {a.t("new")}
            <ArrowRight />
          </Button>
        </div>
      </>
    );
  const r = a.result,
    taxes = r["taxes"] || {},
    residency = r["residency"] || {};
  const breakdown = [
    "net_1099_income",
    "standard_deduction",
    "qbi_deduction",
    "taxable_income",
    "federal_income_tax",
    "self_employment_tax",
  ] as const;
  const tx = r["transactions"]?.transactions || r["transactions"]?.categorized_transactions || [];
  const guidance = formGuidance(residency.residency_status, a.inputs.visa, Boolean(r["form_8843"]));
  return (
    <>
      <div className="mb-8 flex justify-between items-center">
        <h1 className="page-heading">{a.t("results")}</h1>
        <Button variant="outline" onClick={() => a.setSection("new")}>
          {a.t("edit")}
        </Button>
      </div>
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
              "total_tax",
              "self_employment_tax",
              "money_saved_by_deductions",
              "erroneous_fica_refund_amount",
            ].map((k) => (
              <div className="stat" key={k}>
                <p>{a.t(k as Key)}</p>
                <strong>{money(taxes[k])}</strong>
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
          <Readable value={residency.year_breakdown || a.t("noData")} />
          <h3 className="my-4 font-medium">{a.t("learnMore")}</h3>
          <Readable value={residency.filing_plan || a.t("noData")} />
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
                    <td>{t.date}</td>
                    <td>{t.description}</td>
                    <td>{money(t.amount)}</td>
                    <td>
                      <span className="status-pill">{t.category}</span>
                    </td>
                    <td>{t.schedule_c_category || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Readable value={r["transactions"]?.totals || a.t("noData")} />
        </Locked>
      </section>
      <section className="result-block">
        <h2>{a.t("fica")}</h2>
        <Locked>
          <Readable value={taxes.erroneous_fica_explanation || a.t("noData")} />
          <Readable value={taxes.erroneous_fica_next_steps} />
        </Locked>
      </section>
      <section className="result-block">
        <h2>{a.t("quarterly")}</h2>
        <Locked>
          <Readable value={taxes.quarterly_schedule || a.t("noData")} />
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
export function Documents() {
  const a = useAra();
  const pdf = a.result?.["form_8843"]?.pdf_base64;
  const download = () => {
    if (a.plan !== "pro") {
      a.setLock(true);
      return;
    }
    if (typeof pdf !== "string") return;
    const bytes = Uint8Array.from(atob(pdf), (c) => c.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `Form-8843-${a.year}.pdf`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (
    <>
      <h1 className="page-heading">{a.t("documents")}</h1>
      <p className="page-subtitle">Form 8843</p>
      <div className="glass mt-8 max-w-2xl p-8">
        <span className="section-icon">
          <FileText size={22} />
        </span>
        <h2 className="mt-5 text-xl font-semibold">Form 8843</h2>
        <p className="my-5 text-sm leading-7 text-muted-foreground">{a.t("documentHint")}</p>
        {a.plan === "free" ? (
          <Button variant="outline" onClick={() => a.setLock(true)}>
            <LockKeyhole />
            {a.t("unlock")}
          </Button>
        ) : pdf ? (
          <Button onClick={download}>
            <Download />
            {a.t("download")}
          </Button>
        ) : (
          <Button onClick={() => a.setSection("new")}>
            {a.t("edit")}
            <ArrowRight />
          </Button>
        )}
      </div>
    </>
  );
}
