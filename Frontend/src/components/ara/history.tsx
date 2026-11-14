import {
  FileText,
  MessageSquare,
  Sparkles,
  Pencil,
  Trash2,
  Plus,
  LockKeyhole,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { money, presetInputs } from "@/lib/ara/api";
import { formGuidance } from "@/lib/ara/form-guidance";
import type { Key } from "@/lib/ara/i18n";
import { useAra, type CalculationEntry, type CalculationSource } from "./context";
import { useEntryLabel } from "./use-demo-presets";

const sourceIcon: Record<CalculationSource, typeof FileText> = {
  form: FileText,
  chat: MessageSquare,
  preset: Sparkles,
};
const sourceKey: Record<CalculationSource, Key> = {
  form: "sourceForm",
  chat: "sourceChat",
  preset: "sourcePreset",
};

export function entryVisa(entry: CalculationEntry): string {
  return (
    entry.inputs?.visa ||
    entry.request["taxes"]?.visa_type ||
    entry.request["residency"]?.stays?.[0]?.visa_type ||
    ""
  );
}

/** Presentation-only summary of a stored backend response. */
export function entrySummary(entry: CalculationEntry) {
  const residency = entry.response["residency"] || {};
  const taxes = entry.response["taxes"] || {};
  const guidance = formGuidance(
    residency.residency_status,
    entryVisa(entry),
    Boolean(entry.response["form_8843"]),
  );
  return {
    residency,
    taxes,
    formBadge: guidance ? (guidance.form?.replace("Form ", "") ?? "Dual-status") : null,
  };
}

/** Edit an entry: load its inputs into the form; the next run is stored as a new entry. */
export function useEditEntry() {
  const a = useAra();
  return (entry: CalculationEntry) => {
    a.setInputs(entry.inputs ?? presetInputs(entry.request));
    a.setSection("new");
  };
}

export function HistoryPanel({
  selected,
  onToggleSelect,
  onCompare,
}: {
  selected: string[];
  onToggleSelect: (id: string) => void;
  onCompare: () => void;
}) {
  const a = useAra();
  const edit = useEditEntry();
  const labelOf = useEntryLabel();
  const time = new Intl.DateTimeFormat(a.language, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
  const activeId = a.plan === "free" ? a.history[0]?.id : a.activeId;
  return (
    <aside className="history-panel" aria-label={a.t("history")}>
      <div className="history-head">
        <h2>
          <span>{a.t("history")}</span>
          <span className="history-count">{a.history.length}</span>
        </h2>
        <Button size="sm" onClick={() => a.setSection("new")}>
          <Plus />
          {a.t("new")}
        </Button>
      </div>
      {a.plan === "pro" && a.history.length > 1 && (
        <div className="history-compare">
          <span title={a.t("compareHint")}>{a.t("compareHint")}</span>
          <Button size="sm" variant="outline" disabled={selected.length !== 2} onClick={onCompare}>
            {a.t("compare")}
          </Button>
        </div>
      )}
      {a.history.length === 0 ? (
        <p className="history-empty">{a.t("historyEmpty")}</p>
      ) : (
        <ul className="history-list">
          {a.history.map((entry, index) => {
            const locked = a.plan === "free" && index > 0;
            const { taxes, formBadge } = entrySummary(entry);
            const Icon = sourceIcon[entry.source];
            const label = labelOf(entry);
            const isActive = entry.id === activeId;
            const card = (
              <div
                className={`glass history-card ${isActive ? "active" : ""}`}
                aria-current={isActive}
              >
                <button
                  type="button"
                  className="history-card-main"
                  onClick={() => a.setActiveId(entry.id)}
                  disabled={locked}
                  title={label}
                >
                  <span className="history-card-meta">
                    <Icon size={14} aria-hidden="true" />
                    <span>{a.t(sourceKey[entry.source])}</span>
                    <span aria-hidden="true">·</span>
                    <time dateTime={new Date(entry.createdAt).toISOString()}>
                      {time.format(entry.createdAt)}
                    </time>
                    {formBadge && <span className="status-pill">{formBadge}</span>}
                  </span>
                  <strong className="history-card-label">{label}</strong>
                  {typeof taxes.net_tax_owed_or_refund === "number" && (
                    <span className={taxes.is_refund ? "history-refund" : "history-owe"}>
                      {a.t(taxes.is_refund ? "cardRefund" : "cardOwe")}{" "}
                      {money(Math.abs(taxes.net_tax_owed_or_refund))}
                    </span>
                  )}
                </button>
                <div className="history-card-footer">
                  {a.plan === "pro" && a.history.length > 1 && (
                    <label className="history-check">
                      <input
                        type="checkbox"
                        checked={selected.includes(entry.id)}
                        disabled={!selected.includes(entry.id) && selected.length >= 2}
                        onChange={() => onToggleSelect(entry.id)}
                      />
                      {a.t("compare")}
                    </label>
                  )}
                  <div className="history-card-icons">
                    <button
                      type="button"
                      className="history-icon-btn"
                      disabled={locked}
                      onClick={() => edit(entry)}
                      aria-label={a.t("editEntry")}
                      title={a.t("editEntry")}
                    >
                      <Pencil />
                    </button>
                    <button
                      type="button"
                      className="history-icon-btn danger"
                      disabled={locked}
                      onClick={() => a.removeEntry(entry.id)}
                      aria-label={a.t("deleteEntry")}
                      title={a.t("deleteEntry")}
                    >
                      <Trash2 />
                    </button>
                  </div>
                </div>
              </div>
            );
            return (
              <li key={entry.id}>
                {locked ? (
                  <div className="locked-block history-locked">
                    <div className="locked-content" aria-hidden="true">
                      {card}
                    </div>
                    <button type="button" className="lock-overlay" onClick={() => a.setLock(true)}>
                      <LockKeyhole size={16} className="text-accent-foreground" />
                      <span className="text-xs font-medium">{a.t("historyPro")}</span>
                    </button>
                  </div>
                ) : (
                  card
                )}
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}

export function CompareTable({
  entries,
  onClose,
}: {
  entries: CalculationEntry[];
  onClose: () => void;
}) {
  const a = useAra();
  const labelOf = useEntryLabel();
  const rows: [Key, (e: CalculationEntry) => string][] = [
    ["compareStatus", (e) => entrySummary(e).residency.status_label || "—"],
    ["yourForm", (e) => entrySummary(e).formBadge || "—"],
    ["total_tax", (e) => money(entrySummary(e).taxes.total_tax_liability)],
    ["self_employment_tax", (e) => money(entrySummary(e).taxes.self_employment_tax)],
    [
      "compareDeductions",
      (e) => {
        const t = entrySummary(e).taxes;
        return money((t.standard_deduction_applied || 0) + (t.qbi_deduction_applied || 0));
      },
    ],
    ["compareFica", (e) => money(entrySummary(e).taxes.erroneous_fica_refund_amount)],
    [
      "compareNet",
      (e) => {
        const t = entrySummary(e).taxes;
        if (typeof t.net_tax_owed_or_refund !== "number") return "—";
        return `${a.t(t.is_refund ? "refund" : "owe")} ${money(Math.abs(t.net_tax_owed_or_refund))}`;
      },
    ],
  ];
  return (
    <section className="glass mb-6 p-5" aria-label={a.t("compareTitle")}>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold">{a.t("compareTitle")}</h2>
        <Button size="icon" variant="ghost" onClick={onClose} aria-label={a.t("closeCompare")}>
          <X />
        </Button>
      </div>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th />
              {entries.map((e) => (
                <th key={e.id}>{labelOf(e)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([key, value]) => (
              <tr key={key}>
                <td>{a.t(key)}</td>
                {entries.map((e) => (
                  <td key={e.id}>{value(e)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
