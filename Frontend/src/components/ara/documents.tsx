import { useState } from "react";
import { ArrowRight, Download, FileText, LoaderCircle, LockKeyhole, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  ApiError,
  form8843FileName,
  form8843FromCalculation,
  needsForm8843,
  request,
  TAX_YEAR,
  type Form8843Field,
} from "@/lib/ara/api";
import type { Key } from "@/lib/ara/i18n";
import { useAra, type CalculationEntry } from "./context";
import { useEntryLabel } from "./use-demo-presets";

type Form8843Doc = { filename?: string; mime_type?: string; pdf_base64: string };

const docOf = (entry: CalculationEntry): Form8843Doc | null => {
  const doc = entry.response["form_8843"];
  return doc && typeof doc.pdf_base64 === "string" && doc.pdf_base64 ? doc : null;
};

/** UI label for each personal Form 8843 field. */
const FIELD_LABEL: Record<Form8843Field, Key> = {
  first_name: "firstName",
  last_name: "lastName",
  us_address: "us_address",
  home_country_address: "home_address",
  country_of_passport: "passport_country",
  passport_number: "passport_number",
  school_or_program_name: "school_name",
  director_or_dso_name: "dso_name",
};

function downloadPdf(base64: string, filename: string) {
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function DocumentCard({ entry }: { entry: CalculationEntry }) {
  const a = useAra();
  const labelOf = useEntryLabel();
  const [draft, setDraft] = useState<Partial<Record<Form8843Field, string>>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const doc = docOf(entry);
  // Fields to ask for = what is missing before the user types anything (stable while typing).
  const base = form8843FromCalculation(entry.request, entry.response, {}, entry.inputs);
  const filled = form8843FromCalculation(entry.request, entry.response, draft, entry.inputs);
  const name = [filled.payload.first_name, filled.payload.last_name].filter(Boolean).join(" ");
  const year = filled.payload.tax_year || TAX_YEAR;
  const time = new Intl.DateTimeFormat(a.language, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
  const locked = a.plan !== "pro";

  const download = () => {
    if (locked) return a.setLock(true);
    if (!doc) return;
    const lastName = String(
      entry.request["form_8843_profile"]?.last_name || filled.payload.last_name,
    );
    downloadPdf(doc.pdf_base64, form8843FileName(lastName, year));
  };

  const generate = async () => {
    if (locked) return a.setLock(true);
    if (filled.missing.length) return;
    setBusy(true);
    setError("");
    try {
      const pdf = await request<Form8843Doc>("/api/form-8843/base64", filled.payload);
      a.updateEntry(entry.id, {
        request: { ...entry.request, form_8843_profile: filled.payload },
        response: { ...entry.response, form_8843: pdf },
      });
    } catch (e) {
      const notConnected = e instanceof ApiError && e.message === "not_connected";
      setError(a.t(notConnected ? "not_connected" : "network_error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="glass doc-card" aria-label={`Form 8843 · ${labelOf(entry)}`}>
      <div className="doc-card-head">
        <span className="section-icon">
          <FileText size={20} />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold">Form 8843{name ? ` · ${name}` : ""}</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {a.t("taxYearLabel").replace("{year}", String(year))} · {time.format(entry.createdAt)}
          </p>
          <p className="mt-1 truncate text-sm text-muted-foreground" title={labelOf(entry)}>
            {labelOf(entry)}
          </p>
        </div>
        {doc && (
          <Button className="shrink-0" variant={locked ? "outline" : "default"} onClick={download}>
            {locked ? <LockKeyhole /> : <Download />}
            {locked ? a.t("unlock") : a.t("downloadPdf")}
          </Button>
        )}
      </div>

      {!doc && (
        <form
          className="doc-card-form"
          onSubmit={(e) => {
            e.preventDefault();
            generate();
          }}
        >
          <p className="text-xs leading-6 text-muted-foreground">{a.t("docMissingHint")}</p>
          {base.missing.length > 0 && (
            <div className="field-grid">
              {base.missing.map((field) => (
                <label className="field" key={field}>
                  {a.t(FIELD_LABEL[field])}
                  <input
                    value={draft[field] ?? ""}
                    onChange={(e) => setDraft((d) => ({ ...d, [field]: e.target.value }))}
                    required
                    autoComplete="off"
                  />
                </label>
              ))}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <Button
              // Free: the lock opens the upgrade dialog (a submit would stop at the required fields)
              type={locked ? "button" : "submit"}
              onClick={locked ? () => a.setLock(true) : undefined}
              variant={locked ? "outline" : "default"}
              disabled={busy || (!locked && filled.missing.length > 0)}
            >
              {busy ? (
                <LoaderCircle className="animate-spin" />
              ) : locked ? (
                <LockKeyhole />
              ) : (
                <Sparkles />
              )}
              {locked ? a.t("unlock") : a.t("generatePdf")}
            </Button>
            {error && (
              <span role="alert" className="text-xs text-destructive">
                {error}
              </span>
            )}
          </div>
        </form>
      )}
    </article>
  );
}

export function Documents() {
  const a = useAra();
  // Backend fact per calculation: Form 8843 is needed for exempt individuals (F/J/M/Q days).
  const needing = a.history.filter((e) => needsForm8843(e.response));

  return (
    <>
      <h1 className="page-heading">{a.t("documents")}</h1>
      <p className="page-subtitle">Form 8843</p>
      <div className="mt-8 grid max-w-3xl gap-4">
        {needing.map((entry) => (
          <DocumentCard entry={entry} key={entry.id} />
        ))}

        {needing.length === 0 && (
          <div className="glass p-8">
            <span className="section-icon">
              <FileText size={22} />
            </span>
            <h2 className="mt-5 text-xl font-semibold">Form 8843</h2>
            <p className="my-5 text-sm leading-7 text-muted-foreground">
              {a.t(a.history.length ? "not8843Needed" : "documentHint")}
            </p>
            {a.history.length === 0 && (
              <Button onClick={a.openForm8843}>
                {a.t("fill8843")}
                <ArrowRight />
              </Button>
            )}
          </div>
        )}
      </div>
    </>
  );
}
