"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getSupabaseBrowserClient,
  isSupabaseConfigured,
} from "@/lib/supabase/client";

export function LoginForm(): React.JSX.Element {
  const router = useRouter();
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !trimmedEmail.includes("@")) {
      setErrorMessage("Please enter a valid work email address.");
      return;
    }
    if (password.length < 8) {
      setErrorMessage("Password must be at least 8 characters.");
      return;
    }

    if (!isSupabaseConfigured()) {
      setErrorMessage(
        "Supabase Auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in apps/web/.env.local."
      );
      return;
    }

    setIsSubmitting(true);
    try {
      const supabase = getSupabaseBrowserClient();
      const { data, error } = await supabase.auth.signInWithPassword({
        email: trimmedEmail,
        password,
      });

      if (error) {
        setErrorMessage(error.message);
        return;
      }

      if (data.session) {
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Unable to complete login."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={(e) => void handleSubmit(e)} noValidate className="space-y-4">
      {errorMessage && (
        <div
          role="alert"
          className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-xs text-rose-200"
        >
          {errorMessage}
        </div>
      )}

      <div>
        <label
          htmlFor="login-email"
          className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
        >
          Email Address
        </label>
        <input
          id="login-email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@organization.com"
          className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC] placeholder-[#A7B0C4]/50 focus:border-[#7657F6] focus:outline-none"
        />
      </div>

      <div>
        <div className="flex items-center justify-between">
          <label
            htmlFor="login-password"
            className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
          >
            Password
          </label>
          <Link
            href="/forgot-password"
            className="text-xs font-medium text-[#36C6D3] hover:underline"
          >
            Forgot password?
          </Link>
        </div>
        <input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC] placeholder-[#A7B0C4]/50 focus:border-[#7657F6] focus:outline-none"
        />
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full rounded-xl bg-[#7657F6] px-4 py-2.5 text-sm font-semibold text-[#F5F7FC] shadow-[0_0_24px_rgba(118,87,246,0.35)] transition hover:bg-[#7657F6]/90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isSubmitting ? "Signing in..." : "Sign In to Svario"}
      </button>

      <div className="border-t border-[#A7B0C4]/15 pt-4 text-center text-xs text-[#A7B0C4]">
        Don&apos;t have an account yet?{" "}
        <Link
          href="/signup"
          className="font-semibold text-[#36C6D3] hover:underline"
        >
          Create an account
        </Link>
      </div>
    </form>
  );
}
