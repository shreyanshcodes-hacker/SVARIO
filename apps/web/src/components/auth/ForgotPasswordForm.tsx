"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  getAuthRedirectUrl,
  getSupabaseBrowserClient,
  isSupabaseConfigured,
} from "@/lib/supabase/client";

export function ForgotPasswordForm(): React.JSX.Element {
  const [email, setEmail] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [recoverySent, setRecoverySent] = useState<boolean>(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !trimmedEmail.includes("@")) {
      setErrorMessage("Please enter a valid email address.");
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
      const { error } = await supabase.auth.resetPasswordForEmail(trimmedEmail, {
        redirectTo: getAuthRedirectUrl("/reset-password"),
      });

      if (error) {
        setErrorMessage(error.message);
        return;
      }

      setRecoverySent(true);
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error
          ? err.message
          : "Unable to request password recovery."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (recoverySent) {
    return (
      <div
        role="status"
        className="space-y-4 rounded-xl border border-[#36C6D3]/40 bg-[#0B1020]/90 p-5 text-sm"
      >
        <div className="font-mono text-xs font-semibold uppercase tracking-wider text-[#36C6D3]">
          Recovery Link Dispatched
        </div>
        <p className="leading-relaxed text-[#F5F7FC]">
          If an account exists for <strong className="text-[#36C6D3]">{email.trim()}</strong>,
          a password reset link has been sent. Follow the link in your email to
          set a new password.
        </p>
        <Link
          href="/login"
          className="inline-block rounded-xl border border-[#7657F6]/60 bg-[#7657F6]/20 px-4 py-2 text-xs font-semibold text-[#F5F7FC]"
        >
          ← Back to Sign In
        </Link>
      </div>
    );
  }

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
          htmlFor="forgot-email"
          className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
        >
          Account Email Address
        </label>
        <input
          id="forgot-email"
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

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full rounded-xl bg-[#7657F6] px-4 py-2.5 text-sm font-semibold text-[#F5F7FC] shadow-[0_0_24px_rgba(118,87,246,0.35)] transition hover:bg-[#7657F6]/90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isSubmitting ? "Sending recovery link..." : "Send Password Reset Link"}
      </button>

      <div className="border-t border-[#A7B0C4]/15 pt-4 text-center text-xs text-[#A7B0C4]">
        Remembered your password?{" "}
        <Link
          href="/login"
          className="font-semibold text-[#36C6D3] hover:underline"
        >
          Back to sign in
        </Link>
      </div>
    </form>
  );
}
