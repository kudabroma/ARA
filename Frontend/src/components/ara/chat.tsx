import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import ReactMarkdown from "react-markdown";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowDown, ArrowRight, ArrowUp, Check, ChevronDown, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAra, type Message } from "./context";
import {
  ApiError,
  request,
  analyzeAll,
  backendLanguage,
  calculationLabel,
  canSendChat,
  chatProfileBody,
  money,
  presetInputs,
} from "@/lib/ara/api";
import { fieldLabel, type Key } from "@/lib/ara/i18n";

const MAX_INPUT_LINES = 5;
const MIN_CHAT_HEIGHT = 480;
/** Typewriter: ~20 ms per word, but the whole answer never takes longer than ~1.2 s. */
const WORD_MS = 20;
const MAX_TYPING_MS = 1200;

/** Reveals text word by word; plain text while typing, Markdown once finished (no flicker). */
function TypedText({
  text,
  typing,
  onDone,
  onProgress,
}: {
  text: string;
  typing: boolean;
  onDone: () => void;
  onProgress: () => void;
}) {
  const tokens = useRef(text.split(/(\s+)/));
  const [shown, setShown] = useState(typing ? 0 : tokens.current.length);
  useEffect(() => {
    if (!typing) {
      setShown(tokens.current.length);
      return;
    }
    const total = tokens.current.length;
    // tokens alternate word / whitespace, so a word costs two tokens
    const perToken = Math.min(WORD_MS / 2, MAX_TYPING_MS / Math.max(total, 1));
    const start = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const next = Math.min(total, Math.floor((now - start) / perToken) + 1);
      setShown(next);
      onProgress();
      if (next >= total) onDone();
      else frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [typing]);
  if (!typing || shown >= tokens.current.length) return <ReactMarkdown>{text}</ReactMarkdown>;
  // plain text while typing; drop Markdown markers so "**" never flashes before the final render
  const partial = tokens.current
    .slice(0, shown)
    .join("")
    .replace(/\*\*|__|`/g, "");
  return <p className="whitespace-pre-wrap">{partial}</p>;
}

export function Chat() {
  const a = useAra();
  const reduced = useReducedMotion() ?? false;
  const liveTaxes = a.chatData["live_calculation"]?.["taxes"];
  const liveStatus = a.chatData["live_calculation"]?.["residency"]?.["status_label"];
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [typingIdx, setTypingIdx] = useState<number | null>(null);
  const [newBelow, setNewBelow] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const [chatHeight, setChatHeight] = useState<number | null>(null);
  const windowRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const atBottom = useRef(true);
  // Messages that already existed when the tab opened are not animated again.
  const initialCount = useRef(a.messages.length);

  // ---- Fixed-height chat window: fill the viewport below the heading, keep the footer visible.
  useLayoutEffect(() => {
    const measure = () => {
      const win = windowRef.current;
      const main = win?.closest("main");
      if (!win || !main) return;
      const rect = win.getBoundingClientRect();
      const top = rect.top + window.scrollY;
      const below = main.getBoundingClientRect().bottom - rect.bottom;
      const next = Math.max(MIN_CHAT_HEIGHT, Math.floor(window.innerHeight - top - below));
      setChatHeight((prev) => (prev !== null && Math.abs(prev - next) < 2 ? prev : next));
    };
    measure();
    window.addEventListener("resize", measure);
    const main = windowRef.current?.closest("main");
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    if (main) observer?.observe(main);
    return () => {
      window.removeEventListener("resize", measure);
      observer?.disconnect();
    };
  }, [a.language]);

  // ---- Scrolling: follow new content only while the user is at the bottom.
  const scrollToBottom = useCallback(
    (smooth = true) => {
      const list = listRef.current;
      if (!list) return;
      list.scrollTo?.({ top: list.scrollHeight, behavior: smooth && !reduced ? "smooth" : "auto" });
      atBottom.current = true;
      setNewBelow(false);
    },
    [reduced],
  );
  const onListScroll = () => {
    const list = listRef.current;
    if (!list) return;
    atBottom.current = list.scrollHeight - list.scrollTop - list.clientHeight < 48;
    if (atBottom.current) setNewBelow(false);
  };
  const follow = useCallback(
    (smooth = true) => {
      if (atBottom.current) scrollToBottom(smooth);
      else setNewBelow(true);
    },
    [scrollToBottom],
  );
  useEffect(() => {
    follow();
  }, [a.messages.length, busy, error, follow]);
  useLayoutEffect(() => {
    scrollToBottom(false); // open the tab at the latest message
  }, [scrollToBottom]);

  // ---- Composer: auto-grow up to MAX_INPUT_LINES, then scroll inside.
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    const style = getComputedStyle(el);
    const line = parseFloat(style.lineHeight) || 20;
    const chrome = (parseFloat(style.paddingTop) || 0) + (parseFloat(style.paddingBottom) || 0) + 2;
    const max = line * MAX_INPUT_LINES + chrome;
    const needed = el.scrollHeight + 2;
    el.style.height = `${Math.min(needed, max)}px`;
    el.style.overflowY = needed > max ? "auto" : "hidden";
  }, [text]);

  const finishTyping = () => setTypingIdx(null);

  const send = async (raw: string) => {
    const content = raw.trim();
    if (!content || busy) return;
    if (!canSendChat(a.plan, a.sent)) {
      a.setLock(true);
      return;
    }
    finishTyping();
    const previous = a.messages;
    a.setMessages([...previous, { role: "user", content }]); // optimistic
    setText("");
    setBusy(true);
    setError("");
    atBottom.current = true;
    try {
      const data = await request<any>("/api/chat", {
        messages: [
          { role: "assistant", content: a.t("chatIntro") },
          ...previous,
          { role: "user", content },
        ],
        collected_profile: a.chatData["collected_profile"] || {},
        language: backendLanguage(a.language),
      });
      a.setMessages((m: Message[]) => [...m, { role: "assistant", content: data.reply }]);
      setTypingIdx(reduced ? null : previous.length + 1);
      a.setChatData(data);
      a.setSent((n) => n + 1);
    } catch (e) {
      a.setMessages(previous);
      setText(content);
      const m = e instanceof ApiError ? e.message : "network_error";
      setError(["not_connected", "network_error", "invalid_input"].includes(m) ? a.t(m as Key) : m);
    } finally {
      setBusy(false);
    }
  };
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends, Shift+Enter adds a line; never send while an IME composition is active.
    if (e.key !== "Enter" || e.shiftKey || e.nativeEvent.isComposing || e.keyCode === 229) return;
    e.preventDefault();
    send(text);
  };

  const [fullFailed, setFullFailed] = useState(false);
  const chatBody = () => chatProfileBody(a.chatData["collected_profile"] || {}, a.year, a.language);
  const fillInForm = () => {
    a.setInputs(presetInputs(chatBody()));
    a.setSection("new");
  };
  const full = async () => {
    setBusy(true);
    setError("");
    setFullFailed(false);
    try {
      const body = chatBody();
      const response = await analyzeAll(body);
      a.addEntry({
        source: "chat",
        label: calculationLabel(body),
        request: body,
        response,
        language: a.language,
      });
      a.setSection("results");
    } catch (e) {
      setFullFailed(true);
      if (e instanceof ApiError && e.message === "not_connected") setError(a.t("not_connected"));
      else if (e instanceof ApiError && e.status === 422) {
        const fields = [...new Set(e.fields.filter(Boolean).map((f) => fieldLabel(a.language, f)))];
        setError(a.t("missingData").replace("{fields}", fields.join(", ") || "—"));
      } else setError(a.t("network_error"));
    } finally {
      setBusy(false);
    }
  };

  const known = Object.entries(a.chatData["collected_profile"] || {}).filter(
    ([k, v]) => v !== null && v !== undefined && k !== "tax_year",
  );
  const missing: string[] = a.chatData["missing_fields"] || [];
  const total = known.length + missing.length;
  const progress = total ? known.length / total : 0;
  const typing = typingIdx !== null;
  const chips: string[] =
    a.messages.length === 0
      ? [a.t("chatResidencyStarter"), a.t("chatFormStarter")]
      : a.chatData["suggested_replies"] || [];
  const showChips = !busy && !typing && chips.length > 0;
  const appear = reduced
    ? { initial: false as const }
    : {
        initial: { opacity: 0, y: 6 },
        animate: { opacity: 1, y: 0 },
        transition: { duration: 0.18, ease: "easeOut" as const },
      };

  return (
    <>
      <div className="mb-6">
        <h1 className="page-heading">{a.t("chatTitle")}</h1>
        <p className="page-subtitle">{a.t("chatSubtitle")}</p>
      </div>
      <div
        className="chat-grid"
        style={chatHeight ? ({ "--chat-h": `${chatHeight}px` } as React.CSSProperties) : undefined}
      >
        <div className="glass chat-window" ref={windowRef}>
          <div className="chat-header">
            <Sparkles size={16} />
            ARATax
          </div>
          <div className="chat-scroll-wrap">
            <div
              className="chat-messages"
              ref={listRef}
              onScroll={onListScroll}
              aria-live="polite"
              aria-busy={busy}
            >
              <div className="chat-bubble">{a.t("chatIntro")}</div>
              {a.messages.map((m, i) => (
                <motion.div
                  key={i}
                  className={`chat-bubble markdown ${m.role === "user" ? "user" : ""}`}
                  {...(i < initialCount.current ? { initial: false as const } : appear)}
                  onClick={i === typingIdx ? finishTyping : undefined}
                >
                  {m.role === "user" ? (
                    <p className="whitespace-pre-wrap">{m.content}</p>
                  ) : (
                    <TypedText
                      text={m.content}
                      typing={i === typingIdx}
                      onDone={finishTyping}
                      onProgress={() => follow(false)}
                    />
                  )}
                </motion.div>
              ))}
              <AnimatePresence>
                {busy && (
                  <motion.div
                    key="typing"
                    className="chat-bubble typing-bubble"
                    role="status"
                    aria-label={a.t("assistantTyping")}
                    initial={reduced ? false : { opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0, transition: { duration: reduced ? 0 : 0.15 } }}
                    transition={{ duration: 0.15 }}
                  >
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                  </motion.div>
                )}
              </AnimatePresence>
              {error && (
                <div role="alert" className="notice">
                  {error}
                </div>
              )}
            </div>
            {newBelow && (
              <button type="button" className="chat-new-below" onClick={() => scrollToBottom()}>
                <ArrowDown size={14} />
                {a.t("newMessages")}
              </button>
            )}
          </div>
          <div className="chat-footer">
            {(a.chatData["is_complete"] || fullFailed) && !typing && (
              <div className="flex flex-wrap gap-2">
                {a.chatData["is_complete"] && (
                  <Button size="sm" disabled={busy} onClick={full}>
                    {a.t("fullResults")}
                    <ArrowRight />
                  </Button>
                )}
                {fullFailed && (
                  <Button size="sm" variant="outline" disabled={busy} onClick={fillInForm}>
                    {a.t("fillInForm")}
                  </Button>
                )}
              </div>
            )}
            {showChips && (
              <div className="chat-chips" key={chips.join("|")}>
                {chips.map((s, i) => (
                  <motion.button
                    type="button"
                    key={s}
                    className="chat-chip"
                    onClick={() => send(s)}
                    {...(reduced
                      ? { initial: false as const }
                      : {
                          initial: { opacity: 0 },
                          animate: { opacity: 1 },
                          transition: { duration: 0.15, delay: i * 0.035 },
                        })}
                  >
                    {s}
                  </motion.button>
                ))}
              </div>
            )}
            {!canSendChat(a.plan, a.sent) && (
              <p className="text-xs text-muted-foreground">{a.t("chatLimit")}</p>
            )}
            <form
              className="chat-composer"
              onSubmit={(e) => {
                e.preventDefault();
                send(text);
              }}
            >
              <textarea
                ref={inputRef}
                className="chat-input"
                rows={1}
                placeholder={a.t("chatPlaceholder")}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={onKeyDown}
                aria-label={a.t("chatPlaceholder")}
                aria-describedby="chat-enter-hint"
              />
              <span id="chat-enter-hint" className="sr-only">
                {a.t("enterHint")}
              </span>
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
        </div>
        <aside className="chat-rail">
          <button
            type="button"
            className="chat-rail-toggle"
            aria-expanded={railOpen}
            onClick={() => setRailOpen((v) => !v)}
          >
            <span>
              {a.t("progress")} · {Math.round(progress * 100)}%
            </span>
            <ChevronDown size={16} className={railOpen ? "rotate-180" : ""} />
          </button>
          <div className={`chat-rail-body ${railOpen ? "" : "collapsed"}`}>
            <div className="rail-section">
              <h3>{a.t("progress")}</h3>
              <div
                className="progress-track"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(progress * 100)}
              >
                <div className="progress-fill" style={{ transform: `scaleX(${progress})` }} />
              </div>
              <p className="mt-2 text-xs">{Math.round(progress * 100)}%</p>
            </div>
            <div className="rail-section">
              <h3>{a.t("known")}</h3>
              {known.map(([k, v]) => (
                <div key={k} className="my-3 text-xs">
                  <div className="flex items-center gap-2">
                    <Check size={13} className="text-primary" />
                    {fieldLabel(a.language, k)}
                  </div>
                  <p className="ml-5 break-words">
                    {typeof v === "number"
                      ? money(v)
                      : typeof v === "object"
                        ? JSON.stringify(v)
                        : String(v)}
                  </p>
                </div>
              ))}
            </div>
            <div className="rail-section">
              <h3>{a.t("needed")}</h3>
              {missing.map((k) => (
                <p key={k}>{fieldLabel(a.language, k)}</p>
              ))}
            </div>
            {liveTaxes?.net_tax_owed_or_refund !== undefined && (
              <div className="rail-pro live-estimate">
                <h3>{a.t("chatLive")}</h3>
                {liveStatus && <p className="text-xs text-muted-foreground">{liveStatus}</p>}
                <p className="text-sm text-muted-foreground">
                  {a.t(liveTaxes.is_refund ? "refund" : "owe")}
                </p>
                <strong className="text-2xl">{money(liveTaxes.net_tax_owed_or_refund)}</strong>
              </div>
            )}
          </div>
        </aside>
      </div>
    </>
  );
}
