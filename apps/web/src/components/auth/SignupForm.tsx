"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getAuthRedirectUrl,
  getSupabaseBrowserClient,
  isSupabaseConfigured,
} from "@/lib/supabase/client";

export function SignupForm(): React.JSX.Element {
  const router = useRouter();
  const [fullName, setFullName] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [confirmPassword, setConfirmPassword] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [verificationSentTo, setVerificationSentTo] = useState<string | null>(
    null
  );

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    setVerificationSentTo(null);

    const trimmedName = fullName.trim();
    const trimmedEmail = email.trim();

    if (trimmedName.length < 2) {
      setErrorMessage("Please enter your full name (at least 2 characters).");
      return;
    }
    if (!trimmedEmail || !trimmedEmail.includes("@")) {
      setErrorMessage("Please enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setErrorMessage("Password must be at least 8 characters long.");
      return;
    }
    if (password !== confirmPassword) {
      setErrorMessage("Passwords do not match.");
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
      const { data, error } = await supabase.auth.signUp({
        email: trimmedEmail,
        password,
        options: {
          data: {
            full_name: trimmedName,
          },
          emailRedirectTo: getAuthRedirectUrl("/dashboard"),
        },
      });

      if (error) {
        setErrorMessage(error.message);
        return;
      }

      if (data.session) {
        router.push("/dashboard");
      } else {
        setVerificationSentTo(trimmedEmail);
      }
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Unable to complete sign up."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (verificationSentTo) {
    return (
      <div
        role="status"
        className="space-y-4 rounded-xl border border-[#36C6D3]/40 bg-[#0B1020]/90 p-5 text-sm"
      >
        <div className="font-mono text-xs font-semibold uppercase tracking-wider text-[#36C6D3]">
          Verify Your Email Address
        </div>
        <p className="leading-relaxed text-[#F5F7FC]">
          We sent a verification link to{" "}
          <strong className="text-[#36C6D3]">{verificationSentTo}</strong>.
          Please open that link to confirm your email and activate your Svario
          account.
        </p>
        <Link
          href="/login"
          className="inline-block rounded-xl border border-[#7657F6]/60 bg-[#7657F6]/20 px-4 py-2 text-xs font-semibold text-[#F5F7FC] hover:bg-[#7657F6]/35"
        >
          Proceed to Sign In →
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
          htmlFor="signup-full-name"
          className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
        >
          Full Name
        </label>
        <input
          id="signup-full-name"
          name="fullName"
          type="text"
          autoComplete="name"
          required
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="Dr. Priya Nair"
          className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC] placeholder-[#A7B0C4]/50 focus:border-[#7657F6] focus:outline-none"
        />
      </div>

      <div>
        <label
          htmlFor="signup-email"
          className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
        >
          Work Email
        </label>
        <input
          id="signup-email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="priya@organization.com"
          className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC] placeholder-[#A7B0C4]/50 focus:border-[#7657F6] focus:outline-none"
        />
      </div>

      <div>
        <label
          htmlFor="signup-password"
          className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
        >
          Password (min. 8 characters)
        </label>
        <input
          id="signup-password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC] placeholder-[#A7B0C4]/50 focus:border-[#7657F6] focus:outline-none"
        />
      </div>

      <div>
        <label
          htmlFor="signup-confirm-password"
          className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
        >
          Confirm Password
        </label>
        <input
          id="signup-confirm-password"
          name="confirmPassword"
          type="password"
          autoComplete="new-password"
          required
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          placeholder="••••••••"
          className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC] placeholder-[#A7B0C4]/50 focus:border-[#7657F6] focus:outline-none"
        />
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full rounded-xl bg-[#7657F6] px-4 py-2.5 text-sm font-semibold text-[#F5F7FC] shadow-[0_0_24px_rgba(118,87,246,0.35)] transition hover:bg-[#7657F6]/90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isSubmitting ? "Creating account..." : "Create Svario Account"}
      </button>

      <div className="border-t border-[#A7B0C4]/15 pt-4 text-center text-xs text-[#A7B0C4]">
        Already have an account?{" "}
        <Link
          href="/login"
          className="font-semibold text-[#36C6D3] hover:underline"
        >
          Sign in
        </Link>
      </div>
    </form>
  );
}
