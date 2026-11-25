import React from "react";
import Link from "next/link";
import { IndustryCard } from "@/components/IndustryCard";
import { PricingSection } from "@/components/PricingSection";
import { SvarioBrandLogo } from "@/components/SvarioBrandLogo";
import { SVARIO_BRAND, SVARIO_INDUSTRIES } from "@/config/brand";

export default function LandingPage(): React.JSX.Element {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0B1020] text-[#F5F7FC]">
      {/* Subtle ambient background glow */}
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
          <Link href="/" className="inline-block">
            <SvarioBrandLogo />
          </Link>
          <nav
            aria-label="Primary Navigation"
            className="flex flex-wrap items-center gap-2.5"
          >
            <Link
              href="/about"
              className="rounded-xl px-3.5 py-1.5 text-xs font-semibold text-[#A7B0C4] transition hover:text-[#F5F7FC]"
            >
              About
            </Link>
            <a
              href="#pricing"
              className="rounded-xl px-3.5 py-1.5 text-xs font-semibold text-[#A7B0C4] transition hover:text-[#F5F7FC]"
            >
              Pricing
            </a>
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
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 mx-auto max-w-7xl space-y-20 px-6 py-12 sm:py-16">
        {/* Hero / Product Overview */}
        <section className="max-w-4xl space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#36C6D3]/35 bg-[#171D33]/80 px-3.5 py-1 font-mono text-xs text-[#36C6D3]">
            <span>AI VOICE RECEPTIONIST FOR SALONS</span>
          </div>

          <h1 className="text-4xl font-extrabold tracking-tight text-[#F5F7FC] sm:text-5xl lg:text-6xl">
            {SVARIO_BRAND.tagline}
          </h1>

          <p className="max-w-3xl text-base leading-relaxed text-[#A7B0C4] sm:text-lg">
            {SVARIO_BRAND.description}
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Link
              href="/signup"
              className="rounded-xl bg-[#7657F6] px-6 py-3 text-sm font-semibold text-[#F5F7FC] shadow-[0_0_24px_rgba(118,87,246,0.35)] transition hover:bg-[#6546e6]"
            >
              Get Started
            </Link>
            <a
              href="#pricing"
              className="rounded-xl border border-[#A7B0C4]/25 bg-[#171D33]/85 px-6 py-3 text-sm font-semibold text-[#F5F7FC] transition hover:border-[#36C6D3]/60"
            >
              View Pricing
            </a>
          </div>
        </section>

        {/* Pricing Section */}
        <PricingSection />

        {/* Industry Modules */}
        <section aria-labelledby="industries-heading" className="space-y-6">
          <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
            <div>
              <span className="font-mono text-xs font-semibold uppercase tracking-widest text-[#7657F6]">
                Industries
              </span>
              <h2
                id="industries-heading"
                className="mt-1 text-2xl font-bold tracking-tight text-[#F5F7FC] sm:text-3xl"
              >
                Built for Appointment-Driven Businesses
              </h2>
            </div>
            <p className="text-xs text-[#A7B0C4]">
              Salons are available now. Clinics and Hospitals are coming soon.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            {SVARIO_INDUSTRIES.map((industry) => (
              <IndustryCard key={industry.id} industry={industry} />
            ))}
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="relative z-10 mt-20 border-t border-[#A7B0C4]/15 bg-[#0B1020]/90 py-10">
        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-6 px-6 text-xs text-[#A7B0C4] sm:flex-row sm:items-center">
          <SvarioBrandLogo compact />
          <div className="flex flex-wrap items-center gap-5">
            <Link href="/about" className="transition hover:text-[#F5F7FC]">
              About
            </Link>
            <a href="#pricing" className="transition hover:text-[#F5F7FC]">
              Pricing
            </a>
            <Link href="/login" className="transition hover:text-[#F5F7FC]">
              Sign In
            </Link>
            <Link href="/signup" className="transition hover:text-[#F5F7FC]">
              Get Started
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
