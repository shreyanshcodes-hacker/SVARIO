"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getSupabaseBrowserClient,
  isSupabaseConfigured,
} from "@/lib/supabase/client";

export function ResetPasswordForm(): React.JSX.Element {
  const router = useRouter();
  const [password, setPassword] = useState<string>("");
  const [confirmPassword, setConfirmPassword] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [resetComplete, setResetComplete] = useState<boolean>(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    if (password.length < 8) {
      setErrorMessage("New password must be at least 8 characters long.");
      return;
    }
    if (password !== confirmPassword) {
      setErrorMessage("New password and confirmation do not match.");
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
      const { error } = await supabase.auth.updateUser({
        password,
      });

      if (error) {
        setErrorMessage(error.message);
        return;
      }

      setResetComplete(true);
      router.push("/dashboard");
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to update password."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (resetComplete) {
    return (
      <div
        role="status"
        className="space-y-3 rounded-xl border border-[#36C6D3]/40 bg-[#0B1020]/90 p-5 text-sm text-[#F5F7FC]"
      >
        <div className="font-mono text-xs font-semibold uppercase tracking-wider text-[#36C6D3]">
          Password Updated
        </div>
        <p>Your password has been updated. Redirecting to your dashboard...</p>
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
          htmlFor="reset-password"
          className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
        >
          New Password
        </label>
        <input
          id="reset-password"
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
          htmlFor="reset-confirm-password"
          className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
        >
          Confirm New Password
        </label>
        <input
          id="reset-confirm-password"
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
        {isSubmitting ? "Updating password..." : "Update Password"}
      </button>

      <div className="border-t border-[#A7B0C4]/15 pt-4 text-center text-xs text-[#A7B0C4]">
        <Link
          href="/login"
          className="font-semibold text-[#36C6D3] hover:underline"
        >
          Return to Sign In
        </Link>
      </div>
    </form>
  );
}
