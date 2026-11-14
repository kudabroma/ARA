import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { Check, ArrowRight, ArrowLeft, Sparkles, CreditCard, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAra } from "./context";
import {
  isFutureExpiry,
  isLuhnValid,
  isValidCvc,
  isValidEmail,
} from "@/lib/ara/checkout-validation";
export function Plans() {
  const a = useAra();
  return (
    <div className="pricing-container">
      <Button asChild variant="ghost" size="sm" className="mb-6">
        <Link to="/">
          <ArrowLeft />
          {a.t("back")}
        </Link>
      </Button>
      <h1 className="page-heading">{a.t("pricingTitle")}</h1>
      <p className="page-subtitle">{a.t("pricingSubtitle")}</p>
      <div className="plan-grid">
        <section className="glass plan-card">
          <h2>{a.t("free")}</h2>
          <p className="plan-price">
            $0<span> {a.t("month")}</span>
          </p>
          <ul className="plan-list">
            {(["free1", "free2", "free3"] as const).map((k) => (
              <li key={k}>
                <Check />
                {a.t(k)}
              </li>
            ))}
          </ul>
          <Button asChild variant="outline" className="w-full">
            <Link to="/">{a.t("continueFree")}</Link>
          </Button>
        </section>
        <section className="glass plan-card pro-plan">
          <span className="absolute right-5 top-5 rounded-full bg-accent px-3 py-1 text-[10px] font-medium text-accent-foreground">
            {a.t("popular")}
          </span>
          <h2 className="flex items-center gap-2">
            <Sparkles size={19} className="text-primary" />
            Pro
          </h2>
          <p className="plan-price">
            $12<span> {a.t("month")}</span>
          </p>
          <ul className="plan-list">
            {(["pro1", "pro2", "pro3", "pro4", "pro5", "pro6"] as const).map((k) => (
              <li key={k}>
                <Check />
                {a.t(k)}
              </li>
            ))}
          </ul>
          <Button asChild className="w-full">
            <Link to="/checkout">
              {a.t("upgrade")}
              <ArrowRight />
            </Link>
          </Button>
        </section>
      </div>
      <p className="mt-7 text-center text-xs text-muted-foreground">{a.t("formSaved")}</p>
    </div>
  );
}
export function Checkout() {
  const a = useAra();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: "",
    name: "",
    cardNumber: "",
    expiry: "",
    cvc: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const update = (key: keyof typeof form, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    if (
      !isValidEmail(form.email) ||
      !form.name.trim() ||
      !isLuhnValid(form.cardNumber) ||
      !isFutureExpiry(form.expiry) ||
      !isValidCvc(form.cvc)
    ) {
      setError(a.t("checkoutInvalid"));
      return;
    }

    setBusy(true);
    try {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      setForm({ email: "", name: "", cardNumber: "", expiry: "", cvc: "" });
      a.setPlan("pro");
      await navigate({ to: "/success" });
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Button asChild variant="ghost" size="sm">
        <Link to="/pricing">
          <ArrowLeft />
          {a.t("pricing")}
        </Link>
      </Button>
      <div className="glass payment-card">
        <div className="section-icon">
          <CreditCard size={20} />
        </div>
        <h1 className="mt-5 text-2xl font-semibold">{a.t("checkoutTitle")}</h1>
        <div className="my-6 flex justify-between border-y border-border py-5">
          <span>ARATax Pro</span>
          <span className="font-semibold">
            $12 <span className="text-xs font-normal text-muted-foreground">{a.t("month")}</span>
          </span>
        </div>
        <div className="notice mb-5">
          Test mode: use 4242 4242 4242 4242, any future date, any CVC. No real charge, nothing is
          stored.
        </div>
        <form className="space-y-4" onSubmit={submit}>
          <label className="field">
            {a.t("checkoutEmail")}
            <input
              type="email"
              autoComplete="email"
              required
              value={form.email}
              onChange={(event) => update("email", event.target.value)}
            />
          </label>
          <label className="field">
            {a.t("checkoutName")}
            <input
              autoComplete="cc-name"
              required
              value={form.name}
              onChange={(event) => update("name", event.target.value)}
            />
          </label>
          <label className="field">
            {a.t("checkoutCardNumber")}
            <input
              type="text"
              inputMode="numeric"
              autoComplete="cc-number"
              required
              value={form.cardNumber}
              onChange={(event) => update("cardNumber", event.target.value)}
            />
          </label>
          <div className="field-grid">
            <label className="field">
              {a.t("checkoutExpiry")}
              <input
                type="text"
                inputMode="numeric"
                autoComplete="cc-exp"
                placeholder="MM/YY"
                maxLength={7}
                required
                value={form.expiry}
                onChange={(event) => update("expiry", event.target.value)}
              />
            </label>
            <label className="field">
              {a.t("checkoutCvc")}
              <input
                type="password"
                inputMode="numeric"
                autoComplete="cc-csc"
                maxLength={4}
                required
                value={form.cvc}
                onChange={(event) => update("cvc", event.target.value)}
              />
            </label>
          </div>
          {error && (
            <div className="notice" role="alert">
              {error}
            </div>
          )}
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? a.t("checkoutProcessing") : a.t("upgrade")}
          </Button>
        </form>
        <Button asChild variant="ghost" className="mt-3 w-full">
          <Link to="/">
            {a.t("back")}
            <ArrowRight />
          </Link>
        </Button>
      </div>
    </>
  );
}
export function PaymentSuccess() {
  const a = useAra();
  return (
    <div className="empty-view">
      <span className="empty-icon">
        <ShieldCheck size={30} />
      </span>
      <h1 className="page-heading">{a.t("welcomePro")}</h1>
      <p>{a.t("successHint")}</p>
      <Button asChild>
        <Link to="/" onClick={() => a.setSection(a.result ? "results" : "new")}>
          {a.t("backToCalculation")}
          <ArrowRight />
        </Link>
      </Button>
    </div>
  );
}
