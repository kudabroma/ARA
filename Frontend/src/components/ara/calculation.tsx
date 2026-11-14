import { useState, useEffect, useRef, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Globe2,
  Wallet,
  Landmark,
  FileText,
  ChevronDown,
  Plus,
  Trash2,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  LockKeyhole,
  CircleHelp,
  AlertCircle,
  LoaderCircle,
  ArrowUpRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useAra } from "./context";
import {
  ApiError,
  request,
  buildBody,
  backendConfigured,
  presetInputs,
  type Inputs,
} from "@/lib/ara/api";
import type { Key } from "@/lib/ara/i18n";
const visas = ["F-1", "OPT", "J-1", "H-1B", "O-1", "L-1", "Other"];
const incomeKeys = [
  "w2_wages",
  "w2_federal_withheld",
  "w2_fica_withheld",
  "gross_1099_income",
  "business_deductions",
  "estimated_payments_already_made",
] as const;
const profileKeys = [
  "name",
  "us_address",
  "home_address",
  "passport_country",
  "passport_number",
  "first_entry_date",
  "days_present_current",
  "days_present_prior_1",
  "days_present_prior_2",
  "days_excluded",
  "school_name",
  "school_address",
  "school_phone",
  "dso_name",
  "dso_address",
  "dso_phone",
] as const;
function Section({
  icon: Icon,
  title,
  hint,
  children,
  defaultOpen = false,
  openSignal = 0,
}: {
  icon: typeof Globe2;
  title: string;
  hint: string;
  children: ReactNode;
  defaultOpen?: boolean;
  openSignal?: number;
}) {
  const [open, setOpen] = useState(defaultOpen);
  useEffect(() => {
    if (openSignal > 0) setOpen(true);
  }, [openSignal]);
  return (
    <section className="form-section">
      <Button
        type="button"
        variant="ghost"
        className="section-trigger"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <span className="flex items-center gap-3">
          <span className="section-icon">
            <Icon size={19} />
          </span>
          <span>
            <h2>{title}</h2>
            <p>{hint}</p>
          </span>
        </span>
        <ChevronDown
          size={16}
          className={open ? "rotate-180 text-muted-foreground" : "text-muted-foreground"}
        />
      </Button>
      {open && <div className="section-body">{children}</div>}
    </section>
  );
}
export function Calculation() {
  const a = useAra();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [sample, setSample] = useState(false);
  const residencyRef = useRef<HTMLDivElement>(null);
  const [residencyOpenSignal, setResidencyOpenSignal] = useState(0);
  const presets = useQuery({
    queryKey: ["demo-presets"],
    queryFn: () => request<any>("/api/demo-presets"),
    enabled: backendConfigured(),
    retry: false,
  });
  const items = Array.isArray(presets.data) ? presets.data : presets.data?.presets || [];
  const update = (patch: Partial<Inputs>) => a.setInputs((prev) => ({ ...prev, ...patch }));
  const invalid = (key: string) => error?.fields.some((f) => f.endsWith(key)) || false;
  const run = async (body?: unknown) => {
    setError(null);
    setBusy(true);
    try {
      a.setResult(
        await request("/api/analyze-all", body || buildBody(a.inputs, a.year, a.language)),
      );
      a.setSection("results");
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("network_error"));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    setError(null);
  }, [a.inputs]);
  const field = (
    key: string,
    label: string,
    value: string,
    onChange: (v: string) => void,
    type = "text",
    placeholder = "",
  ) => (
    <label className="field">
      {label}
      <input
        aria-invalid={invalid(key)}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
  return (
    <>
      <div className="mb-7 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="mb-3 flex items-center gap-2 text-[11px] font-medium text-accent-foreground">
            <span className="size-1.5 rounded-full bg-primary" />
            {a.t("ready")}
          </div>
          <h1 className="page-heading">{a.t("title")}</h1>
          <p className="page-subtitle">{a.t("subtitle")}</p>
        </div>
      </div>
      <div className="workspace-grid">
        <div>
          <div className="flex items-center justify-between">
            <h2 className="text-[10px] font-semibold tracking-[1.5px] text-muted-foreground">
              {a.t("quick")}
            </h2>
            <span className="text-[10px] text-muted-foreground">{a.t("quickHint")}</span>
          </div>
          {presets.isError && <div role="alert" className="notice my-4 flex items-center justify-between gap-3"><span>{a.t("network_error")}</span><Button variant="ghost" size="sm" onClick={() => presets.refetch()} disabled={presets.isFetching}>{a.t("retry")}</Button></div>}
          {items.length > 0 ? (
            <div className="quick-starts">
              {items.slice(0, 3).map((preset: any, i: number) => (
                <Button
                  variant="outline"
                  className="quick-chip"
                  disabled={busy}
                  key={preset.id || i}
                  onClick={() => {
                    a.setInputs(presetInputs(preset.payload));
                    run({ ...preset.payload, language: a.language === "ru" ? "ru" : "en" });
                  }}
                >
                  <Sparkles size={16} />
                  <span>
                    <strong>{preset.title}</strong>
                    <small>{preset.description}</small>
                  </span>
                </Button>
              ))}
            </div>
          ) : (
            <div className="my-4 mb-6 flex items-center gap-3 rounded-xl border border-dashed border-border px-4 py-4 text-xs text-muted-foreground">
              <Sparkles size={16} className="text-primary" />
              {a.t("presetsUnavailable")}
            </div>
          )}
          <form
            className="glass"
            onSubmit={(e) => {
              e.preventDefault();
              run();
            }}
          >
            <div ref={residencyRef} className="scroll-mt-24">
              <Section
                icon={Globe2}
                title={a.t("residency")}
                hint={a.t("residencyHint")}
                defaultOpen
                openSignal={residencyOpenSignal}
              >
                <div className="field-grid">
                  <label className="field">
                    {a.t("visa")}
                    <select
                      value={a.inputs.visa}
                      onChange={(e) => update({ visa: e.target.value })}
                    >
                      {visas.map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  </label>
                  {field(
                    "country_of_citizenship",
                    a.t("country"),
                    a.inputs.country,
                    (v) => update({ country: v }),
                    "text",
                    a.t("countryPlaceholder"),
                  )}
                </div>
                <div className="mt-6 flex items-center justify-between">
                  <h3 className="text-xs font-medium">{a.t("stays")}</h3>
                  <span className="text-[10px] text-muted-foreground">{a.t("optionalExit")}</span>
                </div>
                {a.inputs.stays.map((s, i) => (
                  <div key={i} className="stay-grid">
                    <label className="field">
                      {a.t("visa")}
                      <select
                        value={s.visa_type}
                        onChange={(e) =>
                          update({
                            stays: a.inputs.stays.map((p, n) =>
                              n === i ? { ...p, visa_type: e.target.value } : p,
                            ),
                          })
                        }
                      >
                        {visas.map((v) => (
                          <option key={v}>{v}</option>
                        ))}
                      </select>
                    </label>
                    {field(
                      "entry_date",
                      a.t("entry"),
                      s.entry_date,
                      (v) =>
                        update({
                          stays: a.inputs.stays.map((p, n) =>
                            n === i ? { ...p, entry_date: v } : p,
                          ),
                        }),
                      "date",
                    )}
                    {field(
                      "exit_date",
                      a.t("exit"),
                      s.exit_date,
                      (v) =>
                        update({
                          stays: a.inputs.stays.map((p, n) =>
                            n === i ? { ...p, exit_date: v } : p,
                          ),
                        }),
                      "date",
                    )}
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      title={a.t("removeStay")}
                      aria-label={a.t("removeStay")}
                      onClick={() => update({ stays: a.inputs.stays.filter((_, n) => n !== i) })}
                    >
                      <Trash2 size={14} />
                    </Button>
                  </div>
                ))}
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="mt-3 text-accent-foreground"
                  onClick={() =>
                    update({
                      stays: [
                        ...a.inputs.stays,
                        { visa_type: a.inputs.visa, entry_date: "", exit_date: "" },
                      ],
                    })
                  }
                >
                  <Plus />
                  {a.t("addStay")}
                </Button>
                <div className="mt-5 field-grid">
                  <label className="flex items-center gap-3 text-xs">
                    <Switch
                      checked={a.inputs.green}
                      onCheckedChange={(green) => update({ green })}
                    />
                    {a.t("green")}
                  </label>
                  {field(
                    "prior_exempt_calendar_years",
                    a.t("exempt"),
                    a.inputs.exempt,
                    (v) => update({ exempt: v }),
                    "text",
                    a.t("exemptHint"),
                  )}
                </div>
              </Section>
            </div>
            <Section icon={Wallet} title={a.t("income")} hint={a.t("incomeHint")} defaultOpen>
              <label className="field mb-5">
                {a.t("filing")}
                <select
                  value={a.inputs.filing}
                  onChange={(e) => update({ filing: e.target.value })}
                >
                  {["single", "married_joint", "married_separate", "head_of_household"].map((v) => (
                    <option value={v} key={v}>
                      {a.t(v as Key)}
                    </option>
                  ))}
                </select>
              </label>
              <div className="field-grid">
                {incomeKeys.map((k) => (
                  <label className="field" key={k}>
                    {a.t(k)}
                    <div className="money-field">
                      <span>$</span>
                      <input
                        aria-invalid={invalid(k)}
                        type="number"
                        min="0"
                        step="0.01"
                        placeholder="0.00"
                        value={a.inputs.income[k] || ""}
                        onChange={(e) =>
                          update({ income: { ...a.inputs.income, [k]: e.target.value } })
                        }
                      />
                    </div>
                  </label>
                ))}
              </div>
            </Section>
            <Section icon={Landmark} title={a.t("bank")} hint={a.t("bankHint")}>
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={a.inputs.transactionMode === "csv" ? "secondary" : "ghost"}
                  onClick={() => update({ transactionMode: "csv" })}
                >
                  {a.t("csv")}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={a.inputs.transactionMode === "manual" ? "secondary" : "ghost"}
                  onClick={() => update({ transactionMode: "manual" })}
                >
                  {a.t("manual")}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="ml-auto"
                  onClick={() => {
                    update({
                      transactionMode: "csv",
                      csv: "date,description,amount\n2025-02-01,Client invoice,2500\n2025-02-03,Adobe subscription,-59.99\n2025-02-05,Groceries,-82.50",
                    });
                    setSample(true);
                  }}
                >
                  <FileText />
                  {a.t("sample")}
                </Button>
              </div>
              {a.inputs.transactionMode === "csv" ? (
                <label className="field">
                  {a.t("csv")}
                  <textarea
                    rows={6}
                    value={a.inputs.csv}
                    onChange={(e) => update({ csv: e.target.value })}
                    placeholder={"date,description,amount"}
                  />
                </label>
              ) : (
                <>
                  {a.inputs.manual.map((row, i) => (
                    <div className="stay-grid" key={i}>
                      {(["date", "description", "amount"] as const).map((k) =>
                        field(
                          k,
                          a.t(k),
                          row[k],
                          (v) =>
                            update({
                              manual: a.inputs.manual.map((r, n) =>
                                n === i ? { ...r, [k]: v } : r,
                              ),
                            }),
                          k === "date" ? "date" : k === "amount" ? "number" : "text",
                        ),
                      )}
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        aria-label={a.t("remove")}
                        onClick={() =>
                          update({ manual: a.inputs.manual.filter((_, n) => n !== i) })
                        }
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      update({
                        manual: [...a.inputs.manual, { date: "", description: "", amount: "" }],
                      })
                    }
                  >
                    <Plus />
                    {a.t("addTransaction")}
                  </Button>
                </>
              )}
              {sample && (
                <p className="mt-2 text-[10px] text-muted-foreground">{a.t("sampleNote")}</p>
              )}
            </Section>
            <Section icon={FileText} title={a.t("form")} hint={a.t("formHint")}>
              <div className="field-grid">
                {profileKeys.map((k) => (
                  <div key={k}>
                    {field(
                      k,
                      a.t(k),
                      String(a.inputs.profile[k] || ""),
                      (v) => update({ profile: { ...a.inputs.profile, [k]: v } }),
                      k === "first_entry_date" ? "date" : k.startsWith("days_") ? "number" : "text",
                    )}
                  </div>
                ))}
                <label className="flex items-center gap-3 text-xs">
                  <Switch
                    checked={Boolean(a.inputs.profile["is_student"])}
                    onCheckedChange={(v) =>
                      update({ profile: { ...a.inputs.profile, is_student: v } })
                    }
                  />
                  {a.t("is_student")}
                </label>
              </div>
            </Section>
            {error && (
              <div role="alert" className="notice mx-5 my-4 flex items-start gap-3">
                <AlertCircle className="mt-1 size-4 shrink-0" />
                <span>
                  {["not_connected", "network_error", "invalid_input"].includes(error.message)
                    ? a.t(error.message as Key)
                    : error.message}{" "}
                  {error.status === 422 && a.t("invalid_input")}
                </span>
                <Button type="button" variant="ghost" size="sm" onClick={() => run()}>
                  {a.t("retry")}
                </Button>
              </div>
            )}
            <div className="calculate-bar">
              <span className="flex items-center gap-2 text-[10px] text-muted-foreground">
                <LockKeyhole size={12} />
                {a.t("secure")}
              </span>
              <Button type="submit" className="calculate" disabled={busy}>
                {busy ? <LoaderCircle className="animate-spin" /> : <Sparkles />}
                {a.t(busy ? "calculating" : "calculate")}
                {!busy && <ArrowRight />}
              </Button>
            </div>
          </form>
        </div>
        <aside className="rail">
          <div className="glass p-5">
            <span className="section-icon">
              <CircleHelp size={20} />
            </span>
            <h3 className="mt-3 text-sm font-semibold">{a.t("residentQuestion")}</h3>
            <p className="mt-3 text-xs leading-6 text-muted-foreground">
              {a.t("residencyFormIntro")}
            </p>
            <h4 className="mt-4 text-xs font-medium">{a.t("whoStruggles")}</h4>
            <ul className="mt-2 list-disc space-y-2 pl-4 text-xs leading-5 text-muted-foreground">
              {(
                [
                  "struggleStudents",
                  "struggleExchange",
                  "struggleWorkers",
                  "struggleMoved",
                ] as const
              ).map((k) => (
                <li key={k}>{a.t(k)}</li>
              ))}
            </ul>
            <Button
              variant="link"
              className="mt-2 h-auto p-0 text-xs"
              onClick={() => {
                setResidencyOpenSignal((n) => n + 1);
                residencyRef.current?.scrollIntoView({
                  behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
                    ? "instant"
                    : "smooth",
                  block: "start",
                });
              }}
            >
              {a.t("checkStatus")}
              <ArrowRight size={13} />
            </Button>
          </div>
          <div className="rail-pro">
            <Sparkles size={21} className="text-accent-foreground" />
            <h3>{a.t("lockedHint")}</h3>
            <p>
              {a.t("pro2")}
              <br />
              {a.t("pro3")}
              <br />
              {a.t("pro4")}
            </p>
            <Button asChild variant="outline" className="mt-5 w-full text-xs">
              <Link to="/pricing">
                {a.t("upgrade")}
                <ArrowUpRight />
              </Link>
            </Button>
            <p className="mt-3 text-center text-[10px]">$12{a.t("month")}</p>
          </div>
        </aside>
      </div>
    </>
  );
}
