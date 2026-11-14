import { useState } from "react";
import { ArrowRight, Download, FileText, LoaderCircle, LockKeyhole, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError, form8843FileName, request, toForm8843Request, type Inputs } from "@/lib/ara/api";
import { useAra, type CalculationEntry } from "./context";
import { useEntryLabel } from "./use-demo-presets";

type Form8843Doc = { filename?: string; mime_type?: string; pdf_base64: string };

const docOf = (entry: CalculationEntry): Form8843Doc | null => {
  const doc = entry.response["form_8843"];
  return doc && typeof doc.pdf_base64 === "string" && doc.pdf_base64 ? doc : null;
};

/** Form 8843 profile name + tax year stored with the calculation. */
function docMeta(entry: CalculationEntry) {
  const profile = entry.request["form_8843_profile"] || {};
  const first = String(profile.first_name || "").trim();
  const last = String(profile.last_name || "").trim();
  const year = Number(profile.tax_year || entry.request["residency"]?.tax_year) || null;
  return { name: [first, last].filter(Boolean).join(" "), lastName: last, year };
}

/** UI profile with a name, from the entry's form snapshot or the current form inputs. */
function profileSource(entry: CalculationEntry | null, current: Inputs): Inputs | null {
  const hasName = (inputs?: Inputs) => {
    const name = inputs?.profile["name"];
    return typeof name === "string" && name.trim().length > 0;
  };
  if (entry?.inputs && hasName(entry.inputs)) return entry.inputs;
  return hasName(current) ? current : null;
}

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

export function Documents() {
  const a = useAra();
  const labelOf = useEntryLabel();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const docs = a.history.filter((e) => docOf(e));
  const active = a.active;
  // Backend fact (exempt individual: F/J/M days excluded), never inferred on the client.
  const activeExempt = Boolean(active?.response["residency"]?.exempt_individual_active);
  const source = profileSource(active, a.inputs);
  const canGenerate = Boolean(active && !docOf(active) && activeExempt && source);
  const time = new Intl.DateTimeFormat(a.language, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

  const download = (entry: CalculationEntry) => {
    if (a.plan !== "pro") {
      a.setLock(true);
      return;
    }
    const doc = docOf(entry);
    if (!doc) return;
    const { lastName, year } = docMeta(entry);
    downloadPdf(doc.pdf_base64, form8843FileName(lastName, year ?? a.year));
  };

  const generate = async () => {
    if (!active || !source) return;
    setBusy(true);
    setError("");
    try {
      const year = Number(active.request["residency"]?.tax_year) || a.year;
      const profile = toForm8843Request(
        { ...source.profile, visa_type: source.visa, country_of_citizenship: source.country },
        year,
      );
      const doc = await request<Form8843Doc>("/api/form-8843/base64", profile);
      a.updateEntry(active.id, {
        request: { ...active.request, form_8843_profile: profile },
        response: { ...active.response, form_8843: doc },
      });
    } catch (e) {
      setError(
        a.t(
          e instanceof ApiError && e.message === "not_connected"
            ? "not_connected"
            : "network_error",
        ),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h1 className="page-heading">{a.t("documents")}</h1>
      <p className="page-subtitle">Form 8843</p>
      <div className="mt-8 grid max-w-2xl gap-4">
        {docs.map((entry) => {
          const { name, year } = docMeta(entry);
          return (
            <article className="glass doc-card" key={entry.id}>
              <span className="section-icon">
                <FileText size={20} />
              </span>
              <div className="min-w-0 flex-1">
                <h2 className="font-semibold">Form 8843{name ? ` · ${name}` : ""}</h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  {a.t("year")}: {year ?? "—"} · {time.format(entry.createdAt)}
                </p>
                <p className="mt-1 truncate text-sm text-muted-foreground" title={labelOf(entry)}>
                  {labelOf(entry)}
                </p>
              </div>
              <Button
                className="shrink-0"
                variant={a.plan === "pro" ? "default" : "outline"}
                onClick={() => download(entry)}
              >
                {a.plan === "pro" ? <Download /> : <LockKeyhole />}
                {a.plan === "pro" ? a.t("downloadPdf") : a.t("unlock")}
              </Button>
            </article>
          );
        })}

        {canGenerate && (
          <div className="glass p-6">
            <p className="text-sm leading-7 text-muted-foreground">{a.t("generate8843Hint")}</p>
            <Button className="mt-4" onClick={generate} disabled={busy}>
              {busy ? <LoaderCircle className="animate-spin" /> : <Sparkles />}
              {a.t("generate8843")}
            </Button>
          </div>
        )}

        {docs.length === 0 && !canGenerate && (
          <div className="glass p-8">
            <span className="section-icon">
              <FileText size={22} />
            </span>
            <h2 className="mt-5 text-xl font-semibold">Form 8843</h2>
            <p className="my-5 text-sm leading-7 text-muted-foreground">{a.t("documentHint")}</p>
            <Button onClick={a.openForm8843}>
              {a.t("fill8843")}
              <ArrowRight />
            </Button>
          </div>
        )}

        {error && (
          <div role="alert" className="notice">
            {error}
          </div>
        )}
      </div>
    </>
  );
}
