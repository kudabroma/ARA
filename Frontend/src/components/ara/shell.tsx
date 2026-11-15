import { Fragment, useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "@tanstack/react-router";
import {
  ArrowUpRight,
  Plus,
  MessageSquare,
  MessageSquareText,
  ChartNoAxesCombined,
  Files,
  Sparkles,
  LockKeyhole,
  ShieldCheck,
  ChevronDown,
  Sprout,
  CreditCard,
  Moon,
  Sun,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { useAra } from "./context";
import { analyzeAll } from "@/lib/ara/api";
const nav = [
  { key: "chat", icon: MessageSquare },
  { key: "new", icon: Plus },
  { key: "results", icon: ChartNoAxesCombined },
  { key: "documents", icon: Files },
] as const;
export function AraShell({ children }: { children: ReactNode }) {
  const a = useAra();
  const path = useLocation().pathname;
  const [languageRefreshFailed, setLanguageRefreshFailed] = useState(false);
  const activeId = a.active?.id;
  const activeLanguage = a.active?.language;
  // Only the active entry is re-requested when its language differs from the UI language.
  useEffect(() => {
    const entry = a.active;
    if (!entry || entry.language === a.language) return;

    let active = true;
    const language = a.language;
    const request = { ...entry.request, language };
    setLanguageRefreshFailed(false);
    analyzeAll(request)
      .then((response) => {
        if (!active) return;
        // Keep a Form 8843 generated from the Documents page if analyze-all did not return one.
        const form_8843 = response["form_8843"] ?? entry.response["form_8843"] ?? null;
        a.updateEntry(entry.id, { request, response: { ...response, form_8843 }, language });
      })
      .catch(() => {
        if (active) setLanguageRefreshFailed(true);
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [a.language, activeId, activeLanguage, a.updateEntry]);
  return (
    <>
      <header className="ara-header">
        <Link to="/" className="ara-logo" aria-label="ARATax home">
          <span className="logo-mark">
            <Sprout size={21} />
          </span>
          ARATax
          <span className="ml-3 hidden border-l border-border pl-4 text-xs font-normal text-muted-foreground md:block">
            {a.t("workspace")}
          </span>
        </Link>
        <div className="header-controls flex items-center gap-4">
          <select
            aria-label="Language"
            className="bg-transparent text-xs outline-none"
            value={a.language}
            onChange={(e) => a.setLanguage(e.target.value as "en" | "ru" | "es")}
          >
            <option value="en">EN</option>
            <option value="ru">RU</option>
            <option value="es">ES</option>
          </select>
          <button
            type="button"
            className="theme-toggle"
            onClick={() => a.setTheme(a.theme === "dark" ? "light" : "dark")}
            aria-label={a.t(a.theme === "dark" ? "themeToLight" : "themeToDark")}
            title={a.t(a.theme === "dark" ? "themeToLight" : "themeToDark")}
          >
            {a.theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <div
            className="glass flex items-center gap-1 rounded-full px-2 py-1"
            role="group"
            aria-label={a.t("demoMode")}
          >
            <span className="mr-1 text-[10px] text-muted-foreground">{a.t("demoMode")}</span>
            <button
              type="button"
              aria-pressed={a.plan === "pro"}
              className={`rounded-full px-2 py-1 text-[10px] transition-colors ${
                a.plan === "pro" ? "bg-primary text-primary-foreground" : "text-muted-foreground"
              }`}
              onClick={() => a.setPlan("pro")}
            >
              {a.t("demoPro")}
            </button>
            <button
              type="button"
              aria-pressed={a.plan === "free"}
              className={`rounded-full px-2 py-1 text-[10px] transition-colors ${
                a.plan === "free" ? "bg-primary text-primary-foreground" : "text-muted-foreground"
              }`}
              onClick={() => a.setPlan("free")}
            >
              {a.t("demoFree")}
            </button>
          </div>
          <span className="rounded-md bg-muted px-2 py-1 text-[10px] text-muted-foreground">
            {a.t(a.plan)}
          </span>
          {a.plan === "free" && (
            <Button asChild size="sm" variant="outline" className="header-upgrade">
              <Link to="/pricing">
                <Sparkles />
                {a.t("upgrade")}
              </Link>
            </Button>
          )}
        </div>
      </header>
      <div className="ara-layout">
        <aside className="ara-sidebar">
          <p className="sidebar-label">{a.t("workspace")}</p>
          <nav>
            {nav.map(({ key, icon: Icon }) => {
              const isActive = path === "/" && a.section === key;
              // The chat is the main feature: always highlighted as an "AI" item, solid when open.
              if (key === "chat")
                return (
                  <Fragment key={key}>
                    <Button
                      variant="ghost"
                      asChild
                      className={`nav-item nav-ai ${isActive ? "active" : ""}`}
                    >
                      <Link
                        to="/"
                        activeProps={{ className: "" }}
                        onClick={() => a.setSection(key)}
                        aria-label={a.t("aiChat")}
                        title={a.t("aiChat")}
                        aria-current={isActive ? "page" : undefined}
                      >
                        <span className="nav-ai-icon" aria-hidden="true">
                          <MessageSquareText size={17} />
                          <Sparkles size={9} className="nav-ai-spark" />
                        </span>
                        <span>{a.t(key)}</span>
                        <span className="nav-ai-badge" aria-hidden="true">
                          AI
                        </span>
                      </Link>
                    </Button>
                    <div className="nav-divider" aria-hidden="true" />
                  </Fragment>
                );
              return (
                <Button
                  key={key}
                  variant="ghost"
                  asChild
                  className={`nav-item ${isActive ? "active" : ""}`}
                >
                  <Link
                    to="/"
                    activeProps={{ className: "" }}
                    onClick={() => a.setSection(key)}
                    aria-current={isActive ? "page" : undefined}
                  >
                    <Icon size={17} />
                    <span>{a.t(key)}</span>
                    {key === "documents" && a.plan === "free" && (
                      <LockKeyhole className="nav-lock ml-auto size-3 opacity-50" />
                    )}
                  </Link>
                </Button>
              );
            })}
            <Button
              asChild
              variant="ghost"
              className={`nav-item ${path === "/pricing" ? "active" : ""}`}
            >
              <Link to="/pricing">
                <CreditCard size={17} />
                {a.t("pricing")}
                <ArrowUpRight className="nav-lock ml-auto size-3" />
              </Link>
            </Button>
          </nav>
          <div className="sidebar-bottom mt-auto">
            <div className="mt-5 flex items-center justify-between px-3 text-[10px] text-muted-foreground">
              <span>ARATax © 2026</span>
              <span>v1.0</span>
            </div>
          </div>
        </aside>
        <main className="ara-main">
          {languageRefreshFailed && (
            <div role="alert" className="notice mb-4">
              {a.t("languageRefreshFailed")}
            </div>
          )}
          {children}
          <footer className="ara-footer">
            <ShieldCheck size={12} className="shrink-0" />
            {a.t("disclaimer")}
          </footer>
        </main>
      </div>
      <Dialog open={a.lock} onOpenChange={a.setLock}>
        <DialogContent className="glass max-w-sm">
          <div className="section-icon">
            <LockKeyhole size={20} />
          </div>
          <DialogTitle>{a.t("locked")}</DialogTitle>
          <DialogDescription>{a.t("lockedHint")}</DialogDescription>
          <p className="text-3xl font-semibold">
            $12<span className="text-sm font-normal text-muted-foreground">{a.t("month")}</span>
          </p>
          <Button asChild onClick={() => a.setLock(false)}>
            <Link to="/pricing">
              {a.t("upgrade")}
              <ArrowUpRight />
            </Link>
          </Button>
        </DialogContent>
      </Dialog>
    </>
  );
}
