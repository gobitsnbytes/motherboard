"use client";

import React, { FormEvent, useState } from "react";
import { KeyRound, LoaderCircle, Mail } from "lucide-react";
import { Button, Input, Label } from "@bnb/ui";
import { api, type Session } from "./api";

type Mode = "password" | "code";

/**
 * Password sign in is always offered, including on a new device where the
 * mailbox cannot be read yet. A code is only useful once a credential is
 * already stored, so that tab is secondary.
 */
export default function Login({ onSignedIn }: { onSignedIn: (session: Session) => void }) {
  const [mode, setMode] = useState<Mode>("password");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [email, setEmail] = useState("");
  const [codeSent, setCodeSent] = useState(false);

  async function run(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign in failed");
    } finally {
      setBusy(false);
    }
  }

  function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    void run(async () => {
      onSignedIn(
        await api<Session>("/login", {
          method: "POST",
          body: JSON.stringify({
            email: values.get("email"),
            password: values.get("password"),
          }),
        }),
      );
    });
  }

  function requestCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void run(async () => {
      await api(`/otp/request`, { method: "POST", body: JSON.stringify({ email }) });
      setCodeSent(true);
      setNotice("If that mailbox can use a code, one is on its way.");
    });
  }

  function submitCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    void run(async () => {
      onSignedIn(
        await api<Session>("/otp/verify", {
          method: "POST",
          body: JSON.stringify({ email, code: values.get("code") }),
        }),
      );
    });
  }

  return (
    <section className="flex min-h-[calc(100dvh-9rem)] items-center justify-center rounded-base border-2 border-border bg-background px-5 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex size-12 items-center justify-center rounded-base border-2 border-border bg-primary text-primary-foreground shadow-shadow">
          <Mail className="size-6" aria-hidden="true" />
        </div>
        <h1 className="font-heading text-3xl font-black tracking-tight">Mailroom</h1>
        <p className="mt-2 text-muted-foreground">Open your bits&amp;bytes inbox.</p>

        <div className="mt-7 flex gap-1 border-b border-border" role="tablist">
          {(["password", "code"] as Mode[]).map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={mode === value}
              onClick={() => {
                setMode(value);
                setError("");
                setNotice("");
              }}
              className={`min-h-11 px-3 text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                mode === value
                  ? "border-b-2 border-primary font-medium text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {value === "password" ? "Mailbox password" : "Sign-in code"}
            </button>
          ))}
        </div>

        {mode === "password" ? (
          <form onSubmit={submitPassword} className="mt-6">
            <div className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="mailroom-email">Email</Label>
                <Input
                  id="mailroom-email"
                  name="email"
                  type="email"
                  autoComplete="username"
                  placeholder="you@gobitsnbytes.org"
                  required
                  className="h-11"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="mailroom-password">Mailbox password</Label>
                <Input
                  id="mailroom-password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  className="h-11"
                />
              </div>
            </div>
            {error && <p role="alert" className="mt-4 text-sm text-destructive">{error}</p>}
            <Button type="submit" disabled={busy} className="mt-6 h-11 w-full gap-2">
              {busy ? <LoaderCircle className="size-4 animate-spin" /> : <Mail className="size-4" />}
              {busy ? "Opening inbox..." : "Open inbox"}
            </Button>
            <p className="mt-4 text-xs leading-5 text-muted-foreground">
              Your mailbox password stays encrypted on the Motherboard server. Messages are
              never copied out of the mail server.
            </p>
          </form>
        ) : (
          <div className="mt-6">
            <p className="mb-5 rounded-lg border border-border px-4 py-3 text-sm leading-6 text-muted-foreground">
              Codes only work on a mailbox you have already opened once with its
              password. Until then, use the{" "}
              <button
                type="button"
                onClick={() => setMode("password")}
                className="underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                mailbox password
              </button>{" "}
              tab.
            </p>
            <form onSubmit={requestCode} className="space-y-2">
              <Label htmlFor="mailroom-code-email">Email</Label>
              <div className="flex gap-2">
                <Input
                  id="mailroom-code-email"
                  type="email"
                  autoComplete="username"
                  placeholder="you@gobitsnbytes.org"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  className="h-11"
                />
                <Button type="submit" variant="neutral" disabled={busy || !email} className="h-11 shrink-0">
                  {codeSent ? "Resend" : "Send code"}
                </Button>
              </div>
            </form>

            {codeSent && (
              <form onSubmit={submitCode} className="mt-5 space-y-2">
                <Label htmlFor="mailroom-code">Six digit code</Label>
                <Input
                  id="mailroom-code"
                  name="code"
                  inputMode="numeric"
                  pattern="\d{6}"
                  autoComplete="one-time-code"
                  required
                  className="h-11 tracking-[0.4em]"
                />
                <Button type="submit" disabled={busy} className="mt-4 h-11 w-full gap-2">
                  {busy ? <LoaderCircle className="size-4 animate-spin" /> : <KeyRound className="size-4" />}
                  Verify code
                </Button>
              </form>
            )}

            {notice && <p className="mt-4 text-sm text-muted-foreground">{notice}</p>}
            {error && <p role="alert" className="mt-4 text-sm text-destructive">{error}</p>}
          </div>
        )}
      </div>
    </section>
  );
}
