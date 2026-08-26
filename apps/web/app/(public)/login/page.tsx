"use client";

import React, { Suspense, useState, useEffect } from "react";
import { signIn, useSession } from "next-auth/react";
import { useSearchParams, useRouter } from "next/navigation";
import { ShieldCheck, ArrowRight, Lock } from "lucide-react";

function LoginForm() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { data: session, status } = useSession();
  const error = searchParams.get("error");
  const [isPending, setIsPending] = useState(false);

  useEffect(() => {
    if (status === "authenticated" && session) {
      router.replace("/dashboard/overview");
    }
  }, [status, session, router]);

  const handleSignIn = async () => {
    setIsPending(true);
    try {
      const res = await signIn("discord", { callbackUrl: "/dashboard/overview", redirect: false });
      if (res?.url) {
        window.location.href = res.url;
      }
    } finally {
      setIsPending(false);
    }
  };

  return (
    <div className="relative w-full max-w-sm rounded-base border-2 border-border bg-[#121216] p-6 sm:p-8 shadow-heavy">
      {/* Top Tag */}
      <div className="absolute -top-3 left-4 bg-orange text-black font-mono font-black text-[10px] uppercase px-2 py-0.5 border-2 border-black shadow-[2px_2px_0px_#000]">
        AUTHENTICATION // DESK 01
      </div>

      <div className="flex flex-col items-center gap-5">
        {/* Logo */}
        <div className="size-14 rounded-base border-2 border-border bg-black flex items-center justify-center shadow-light">
          <img
            src="https://gobitsnbytes.org/logo"
            alt="bits&bytes logo"
            className="w-7 h-auto select-none"
          />
        </div>

        <div className="text-center space-y-1">
          <h1 className="text-xl font-heading font-black uppercase tracking-tight text-white">
            Motherboard Cockpit
          </h1>
          <p className="text-xs text-zinc-300 font-base leading-relaxed">
            Sign in with your verified Discord account to access the internal operations platform.
          </p>
        </div>

        {/* Error state */}
        {error && (
          <div className="w-full rounded-base border-2 border-red-500 bg-red-950/80 px-3.5 py-2.5 text-center text-xs font-bold text-red-200">
            Authentication failed. Please verify your Discord credentials.
          </div>
        )}

        {/* Discord sign-in button */}
        <button
          type="button"
          onClick={handleSignIn}
          disabled={isPending}
          className="inline-flex w-full items-center justify-center gap-2.5 rounded-base border-2 border-black bg-[#5865F2] hover:bg-[#4752C4] px-6 py-3.5 text-xs font-heading font-black uppercase tracking-wider text-white shadow-[4px_4px_0px_#000] transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-50 disabled:pointer-events-none"
        >
          <svg
            className="size-5 shrink-0"
            viewBox="0 0 24 24"
            fill="currentColor"
            aria-hidden="true"
          >
            <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.095 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.095 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
          </svg>
          <span>{isPending ? "Connecting…" : "Continue with Discord"}</span>
        </button>

        {/* Footer note */}
        <div className="border-t-2 border-border pt-3 w-full text-center">
          <p className="text-[10px] text-zinc-400 font-mono uppercase tracking-widest">
            Invite-Based Access &bull; GOBITSNBYTES FOUNDATION
          </p>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main className="flex min-h-screen w-full items-center justify-center bg-[#0a0a0c] px-4 blueprint-dot-grid">
      <Suspense>
        <LoginForm />
      </Suspense>
    </main>
  );
}

