import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { ArrowUp, Check, Sparkles, LoaderCircle, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAra } from "./context";
import { ApiError, request, backendLanguage, canSendChat, money } from "@/lib/ara/api";
import type { Key } from "@/lib/ara/i18n";
export function Chat() {
  const a = useAra();
  const liveTaxes = a.chatData["live_calculation"]?.["taxes"];
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const send = async (content: string) => {
    if (!content.trim() || busy) return;
    if (!canSendChat(a.plan, a.sent)) {
      a.setLock(true);
      return;
    }
    setBusy(true);
    setError("");
    const history = [
      { role: "assistant" as const, content: a.t("chatIntro") },
      ...a.messages,
      { role: "user" as const, content },
    ];
    try {
      const data = await request<any>("/api/chat", {
        messages: history,
        collected_profile: a.chatData["collected_profile"] || {},
        language: backendLanguage(a.language),
      });
      a.setMessages([
        ...a.messages,
        { role: "user", content },
        { role: "assistant", content: data.reply },
      ]);
      a.setChatData(data);
      a.setSent((n) => n + 1);
      setText("");
    } catch (e) {
      const m = e instanceof ApiError ? e.message : "network_error";
      setError(["not_connected", "network_error", "invalid_input"].includes(m) ? a.t(m as Key) : m);
    } finally {
      setBusy(false);
    }
  };
  const full = async () => {
    setBusy(true);
    setError("");
    try {
      const profile = a.chatData["collected_profile"] || {};
      const body = profile.residency
        ? { ...profile, language: backendLanguage(a.language) }
        : {
            language: backendLanguage(a.language),
            residency: {
              tax_year: a.year,
              stays: profile.stays || [],
              country_of_citizenship: profile.country_of_citizenship,
              prior_exempt_calendar_years: profile.prior_exempt_calendar_years || [],
              has_green_card: profile.has_green_card || false,
            },
            taxes: Object.fromEntries(
              Object.entries({ tax_year: a.year, ...profile }).filter(
                ([k]) =>
                  ![
                    "residency_status",
                    "stays",
                    "prior_exempt_calendar_years",
                    "has_green_card",
                  ].includes(k),
              ),
            ),
          };
      a.setResult(await request("/api/analyze-all", body));
      a.setSection("results");
    } catch (e) {
      setError(
        e instanceof ApiError && e.message === "not_connected"
          ? a.t("not_connected")
          : a.t("network_error"),
      );
    } finally {
      setBusy(false);
    }
  };
  const known = Object.entries(a.chatData["collected_profile"] || {}).filter(
    ([, v]) => v !== null && v !== undefined,
  );
  const missing = a.chatData["missing_fields"] || [];
  const total = known.length + missing.length;
  return (
    <>
      <div className="mb-8">
        <h1 className="page-heading">{a.t("chat")}</h1>
        <p className="page-subtitle">{a.t("assistance")}</p>
      </div>
      <div className="chat-grid">
        <div className="glass chat-window">
          <div className="chat-messages">
            <div className="flex items-center gap-2 text-xs font-semibold text-accent-foreground">
              <Sparkles size={16} />
              ARATax
            </div>
            <div className="chat-bubble">{a.t("chatIntro")}</div>
            {a.messages.length === 0 && (
              <div className="flex flex-wrap gap-2">
                {(["chatResidencyStarter", "chatFormStarter"] as const).map((k) => (
                  <Button
                    key={k}
                    variant="outline"
                    size="sm"
                    className="h-auto whitespace-normal py-2 text-left"
                    disabled={busy}
                    onClick={() => send(a.t(k))}
                  >
                    {a.t(k)}
                  </Button>
                ))}
              </div>
            )}
            {a.messages.map((m, i) => (
              <div key={i} className={`chat-bubble markdown ${m.role === "user" ? "user" : ""}`}>
                <ReactMarkdown>{m.content}</ReactMarkdown>
              </div>
            ))}
            {busy && <LoaderCircle className="animate-spin text-primary" />}
            {error && (
              <div role="alert" className="notice">
                {error}
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {(a.chatData["suggested_replies"] || []).map((s: string) => (
                <Button variant="outline" size="sm" key={s} disabled={busy} onClick={() => send(s)}>
                  {s}
                </Button>
              ))}
            </div>
            {a.chatData["is_complete"] && (
              <Button disabled={busy} onClick={full}>
                {a.t("fullResults")}
                <ArrowRight />
              </Button>
            )}
          </div>
          {!canSendChat(a.plan, a.sent) && (
            <p className="px-5 pb-3 text-xs text-muted-foreground">{a.t("chatLimit")}</p>
          )}
          <form
            className="chat-composer"
            onSubmit={(e) => {
              e.preventDefault();
              send(text);
            }}
          >
            <textarea
              className="chat-input"
              rows={2}
              placeholder={a.t("chatPlaceholder")}
              value={text}
              onChange={(e) => setText(e.target.value)}
              aria-label={a.t("chatPlaceholder")}
            />
            <Button
              type="submit"
              size="icon"
              disabled={busy || !text.trim()}
              title={a.t("send")}
              aria-label={a.t("send")}
            >
              <ArrowUp />
            </Button>
          </form>
        </div>
        <aside>
          <div className="rail-section">
            <h3>{a.t("progress")}</h3>
            <progress
              className="h-1.5 w-full accent-primary"
              max={100}
              value={total ? (known.length / total) * 100 : 0}
            />
            <p className="mt-2 text-xs">{total ? Math.round((known.length / total) * 100) : 0}%</p>
          </div>
          <div className="rail-section">
            <h3>{a.t("known")}</h3>
            {known.map(([k, v]) => (
              <div key={k} className="my-3 text-xs">
                <div className="flex items-center gap-2">
                  <Check size={13} className="text-primary" />
                  {k.replaceAll("_", " ")}
                </div>
                <p className="ml-5 break-words">
                  {typeof v === "object" ? JSON.stringify(v) : String(v)}
                </p>
              </div>
            ))}
          </div>
          <div className="rail-section">
            <h3>{a.t("needed")}</h3>
            {missing.map((k: string) => (
              <p key={k}>{k.replaceAll("_", " ")}</p>
            ))}
          </div>
          {liveTaxes?.net_tax_owed_or_refund !== undefined && (
            <div className="rail-pro">
              <h3>{a.t("chatLive")}</h3>
              <p className="text-sm text-muted-foreground">
                {a.t(liveTaxes.is_refund ? "refund" : "owe")}
              </p>
              <strong className="text-2xl">
                {money(liveTaxes.net_tax_owed_or_refund)}
              </strong>
            </div>
          )}
        </aside>
      </div>
    </>
  );
}
