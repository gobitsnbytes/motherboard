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
    <div className="relative w-full max-w-sm border-2 border-[#17130f] bg-white p-6 text-[#17130f] shadow-[5px_5px_0_#97192c] sm:p-8">
      {/* Top Tag */}
      <div className="absolute -top-3 left-4 border-2 border-[#17130f] bg-orange px-2 py-0.5 font-mono text-[10px] font-bold text-black shadow-[2px_2px_0_#17130f]">
        Member sign-in
      </div>

      <div className="flex flex-col items-center gap-5">
        {/* Logo */}
        <div className="flex size-14 items-center justify-center border-2 border-[#17130f] bg-[#17130f] shadow-[3px_3px_0_#fc920d]">
          <img
            src="https://gobitsnbytes.org/logo"
            alt="bits&bytes™ logo"
            className="w-7 h-auto select-none"
          />
        </div>

        <div className="text-center space-y-1">
          <h1 className="font-heading text-2xl font-black tracking-tight">
            Motherboard
          </h1>
          <p className="text-sm font-base leading-6 text-stone-600">
            Sign in with your verified Discord account to access the internal operations platform.
          </p>
        </div>

        {/* Error state */}
        {error && (
          <div className="w-full border-2 border-red-800 bg-red-50 px-3.5 py-2.5 text-center text-xs font-bold text-red-900">
            Authentication failed. Please verify your Discord credentials.
          </div>
        )}

        {/* Discord sign-in button */}
        <button
          type="button"
          onClick={handleSignIn}
          disabled={isPending}
          className="inline-flex min-h-12 w-full items-center justify-center gap-2.5 border-2 border-[#17130f] bg-[#5865F2] px-6 text-sm font-semibold text-white shadow-[4px_4px_0_#17130f] transition-transform active:translate-x-[2px] active:translate-y-[2px] active:shadow-none disabled:pointer-events-none disabled:opacity-50"
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
        <div className="w-full border-t-2 border-stone-200 pt-3 text-center">
          <p className="font-mono text-[10px] tracking-wide text-stone-500">
            Invite-based access · GOBITSNBYTES FOUNDATION
          </p>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main className="flex min-h-screen w-full items-center justify-center bg-[#ebe8e1] px-4">
      <Suspense>
        <LoginForm />
      </Suspense>
    </main>
  );
}
