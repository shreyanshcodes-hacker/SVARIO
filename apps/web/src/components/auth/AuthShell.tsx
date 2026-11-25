import React from "react";
import Link from "next/link";
import { SvarioBrandLogo } from "@/components/SvarioBrandLogo";
import { isSupabaseConfigured } from "@/lib/supabase/client";

interface AuthShellProps {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}

export function AuthShell({
  title,
  subtitle,
  children,
}: AuthShellProps): React.JSX.Element {
  const configured = isSupabaseConfigured();

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0B1020] text-[#F5F7FC]">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 left-1/2 h-96 w-[48rem] -translate-x-1/2 rounded-full bg-[#7657F6]/15 blur-3xl"
      />

      <header className="relative z-10 border-b border-[#A7B0C4]/15 bg-[#0B1020]/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
          <Link href="/" className="inline-block">
            <SvarioBrandLogo />
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/"
              className="rounded-lg border border-[#A7B0C4]/25 bg-[#171D33]/80 px-3 py-1.5 text-xs font-medium text-[#F5F7FC] transition hover:border-[#7657F6]/60"
            >
              ← Home
            </Link>
          </div>
        </div>
      </header>

      <main className="relative z-10 mx-auto flex max-w-md flex-col justify-center px-6 py-12 sm:py-16">
        {!configured && (
          <div
            role="note"
            className="mb-6 rounded-xl border border-amber-400/40 bg-amber-500/10 p-4 text-xs leading-relaxed text-amber-200"
          >
            <strong className="block font-semibold text-amber-300">
              Supabase Environment Placeholders Detected
            </strong>
            Configure{" "}
            <code className="font-mono">NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
            <code className="font-mono">NEXT_PUBLIC_SUPABASE_ANON_KEY</code> in{" "}
            <code className="font-mono">apps/web/.env.local</code> to connect to
            a live Supabase Auth project.
          </div>
        )}

        <div className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-6 shadow-[0_18px_48px_rgba(11,16,32,0.65)] sm:p-8">
          <div className="mb-6 space-y-1.5">
            <span className="font-mono text-[11px] font-semibold uppercase tracking-widest text-[#36C6D3]">
              SVARIO ACCOUNT
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-[#F5F7FC]">
              {title}
            </h1>
            <p className="text-sm text-[#A7B0C4]">{subtitle}</p>
          </div>

          {children}
        </div>
      </main>
    </div>
  );
}
