import React from "react";
import Link from "next/link";
import { ArchitectureBoundarySection } from "@/components/ArchitectureBoundarySection";
import { BackendStatusPanel } from "@/components/BackendStatusPanel";
import { IndustryCard } from "@/components/IndustryCard";
import { StageIndicatorBadge } from "@/components/StageIndicatorBadge";
import { SvarioLogoPlaceholder } from "@/components/SvarioLogoPlaceholder";
import { SVARIO_BRAND, SVARIO_INDUSTRIES } from "@/config/brand";

export default function FoundationPage(): React.JSX.Element {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0B1020] text-[#F5F7FC]">
      {/* Subtle futuristic ambient background glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 left-1/2 h-96 w-[52rem] -translate-x-1/2 rounded-full bg-[#7657F6]/15 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-96 right-0 h-80 w-80 rounded-full bg-[#36C6D3]/10 blur-3xl"
      />

      {/* Top Navigation / Brand Bar */}
      <header className="relative z-10 border-b border-[#A7B0C4]/15 bg-[#0B1020]/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-4 lg:flex-row lg:items-center lg:justify-between">
          <SvarioLogoPlaceholder />
          <div className="flex flex-wrap items-center gap-3">
            <StageIndicatorBadge />
            <nav aria-label="Authentication & Workspace Navigation" className="flex items-center gap-2">
              <Link
                href="/login"
                className="rounded-xl border border-[#A7B0C4]/25 bg-[#171D33]/90 px-3.5 py-1.5 text-xs font-semibold text-[#F5F7FC] transition hover:border-[#7657F6]/60"
              >
                Sign In
              </Link>
              <Link
                href="/signup"
                className="rounded-xl bg-[#7657F6] px-3.5 py-1.5 text-xs font-semibold text-[#F5F7FC] shadow-[0_0_16px_rgba(118,87,246,0.3)] transition hover:bg-[#7657F6]/90"
              >
                Get Started
              </Link>
              <Link
                href="/dashboard"
                className="rounded-xl border border-[#36C6D3]/45 bg-[#36C6D3]/10 px-3.5 py-1.5 text-xs font-semibold text-[#36C6D3] transition hover:bg-[#36C6D3]/20"
              >
                Dashboard
              </Link>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 mx-auto max-w-7xl space-y-12 px-6 py-12 sm:py-16">
        {/* Hero / Product Overview */}
        <section className="max-w-4xl space-y-6">
          <div className="inline-flex items-center gap-2 rounded-lg border border-[#36C6D3]/35 bg-[#171D33]/80 px-3 py-1 font-mono text-xs text-[#36C6D3]">
            <span>MULTI-INDUSTRY AI VOICE AGENT PLATFORM</span>
          </div>

          <h1 className="text-4xl font-extrabold tracking-tight text-[#F5F7FC] sm:text-5xl lg:text-6xl">
            {SVARIO_BRAND.tagline}
          </h1>

          <p className="max-w-3xl text-base leading-relaxed text-[#A7B0C4] sm:text-lg">
            {SVARIO_BRAND.description}
          </p>

          {/* Brand Color System Token Strip */}
          <div className="flex flex-wrap items-center gap-2.5 pt-2">
            <span className="font-mono text-xs uppercase tracking-wider text-[#A7B0C4]">
              Design Tokens:
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-md border border-[#A7B0C4]/25 bg-[#0B1020] px-2.5 py-1 font-mono text-xs text-[#F5F7FC]">
              <span className="h-2.5 w-2.5 rounded-full bg-[#0B1020] ring-1 ring-[#A7B0C4]/50" />
              Midnight Navy #0B1020
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-md border border-[#A7B0C4]/25 bg-[#171D33] px-2.5 py-1 font-mono text-xs text-[#F5F7FC]">
              <span className="h-2.5 w-2.5 rounded-full bg-[#171D33] ring-1 ring-[#A7B0C4]/50" />
              Deep Indigo #171D33
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-md border border-[#A7B0C4]/25 bg-[#171D33] px-2.5 py-1 font-mono text-xs text-[#F5F7FC]">
              <span className="h-2.5 w-2.5 rounded-full bg-[#7657F6]" />
              Electric Violet #7657F6
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-md border border-[#A7B0C4]/25 bg-[#171D33] px-2.5 py-1 font-mono text-xs text-[#F5F7FC]">
              <span className="h-2.5 w-2.5 rounded-full bg-[#36C6D3]" />
              Cyber Teal #36C6D3
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-md border border-[#A7B0C4]/25 bg-[#F5F7FC] px-2.5 py-1 font-mono text-xs text-[#0B1020]">
              <span className="h-2.5 w-2.5 rounded-full bg-[#F5F7FC] ring-1 ring-[#0B1020]/30" />
              Cloud White #F5F7FC
            </span>
          </div>
        </section>

        {/* Live Backend Connection Status */}
        <BackendStatusPanel />

        {/* Three Industry Cards */}
        <section aria-labelledby="industries-heading" className="space-y-6">
          <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
            <div>
              <span className="font-mono text-xs font-semibold uppercase tracking-widest text-[#7657F6]">
                Target Verticals
              </span>
              <h2
                id="industries-heading"
                className="mt-1 text-2xl font-bold tracking-tight text-[#F5F7FC] sm:text-3xl"
              >
                Three Core Industry Modules
              </h2>
            </div>
            <p className="font-mono text-xs text-[#A7B0C4]">
              Stage 1 Active: Multi-tenant auth & organization onboarding via{" "}
              <Link href="/dashboard" className="text-[#36C6D3] underline">
                /dashboard
              </Link>
              .
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            {SVARIO_INDUSTRIES.map((industry) => (
              <IndustryCard key={industry.id} industry={industry} />
            ))}
          </div>
        </section>

        {/* Shared Platform Architectural Boundaries */}
        <ArchitectureBoundarySection />
      </main>

      {/* Footer */}
      <footer className="relative z-10 mt-16 border-t border-[#A7B0C4]/15 bg-[#0B1020]/90 py-8">
        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-4 px-6 text-xs text-[#A7B0C4] sm:flex-row sm:items-center">
          <div>
            <strong className="font-semibold tracking-wider text-[#F5F7FC]">
              {SVARIO_BRAND.name}
            </strong>{" "}
            — {SVARIO_BRAND.tagline}
          </div>
          <div className="font-mono">
            Milestone: {SVARIO_BRAND.stageTitle} • Next.js + FastAPI Monorepo
          </div>
        </div>
      </footer>
    </div>
  );
}
