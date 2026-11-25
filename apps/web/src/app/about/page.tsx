import React from "react";
import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";
import { SvarioBrandLogo } from "@/components/SvarioBrandLogo";

export const metadata: Metadata = {
  title: "About Us | SVARIO",
  description:
    "Meet Shreyansh Jaiswal, Founder & CEO of Svario. Developed with Shreyansh Codes.",
};

export default function AboutPage(): React.JSX.Element {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0B1020] text-[#F5F7FC]">
      {/* Subtle ambient background glow matching Svario identity */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 left-1/2 h-96 w-[50rem] -translate-x-1/2 rounded-full bg-[#7657F6]/15 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-96 right-0 h-80 w-80 rounded-full bg-[#36C6D3]/10 blur-3xl"
      />

      {/* Public Header */}
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
              href="/"
              className="rounded-xl px-3.5 py-1.5 text-xs font-semibold text-[#A7B0C4] transition hover:text-[#F5F7FC]"
            >
              Home
            </Link>
            <Link
              href="/#pricing"
              className="rounded-xl px-3.5 py-1.5 text-xs font-semibold text-[#A7B0C4] transition hover:text-[#F5F7FC]"
            >
              Pricing
            </Link>
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
      <main className="relative z-10 mx-auto max-w-5xl space-y-14 px-6 py-14 sm:py-20">
        {/* Page Heading */}
        <section className="max-w-3xl space-y-4">
          <span className="inline-flex items-center rounded-full border border-[#36C6D3]/35 bg-[#171D33]/80 px-3.5 py-1 font-mono text-xs font-semibold uppercase tracking-widest text-[#36C6D3]">
            About Svario
          </span>
          <h1 className="text-4xl font-extrabold tracking-tight text-[#F5F7FC] sm:text-5xl">
            Built to give businesses an intelligent voice.
          </h1>
          <p className="text-base leading-relaxed text-[#A7B0C4] sm:text-lg">
            Svario helps salons answer customer calls, share services and
            pricing, and book appointments effortlessly with an AI voice
            receptionist.
          </p>
        </section>

        {/* Founder Section */}
        <section
          aria-labelledby="founder-heading"
          className="overflow-hidden rounded-3xl border border-[#A7B0C4]/20 bg-[#171D33]/85 p-6 shadow-[0_24px_64px_rgba(11,16,32,0.7)] sm:p-10"
        >
          <div className="grid items-center gap-8 md:grid-cols-[260px_1fr] lg:grid-cols-[300px_1fr] lg:gap-12">
            {/* Founder Portrait */}
            <div className="mx-auto w-full max-w-[260px] md:max-w-none">
              <div className="relative aspect-square overflow-hidden rounded-2xl border border-[#7657F6]/45 bg-[#0B1020] shadow-[0_0_32px_rgba(118,87,246,0.22)]">
                <Image
                  src="/founder-shreyansh.png"
                  alt="Shreyansh Jaiswal — Founder & CEO, Svario"
                  width={480}
                  height={480}
                  priority
                  className="h-full w-full object-cover object-top"
                />
              </div>
            </div>

            {/* Founder Details */}
            <div className="space-y-5 text-center md:text-left">
              <div className="space-y-1.5">
                <span className="font-mono text-xs font-semibold uppercase tracking-widest text-[#7657F6]">
                  Leadership
                </span>
                <h2
                  id="founder-heading"
                  className="text-2xl font-bold tracking-tight text-[#F5F7FC] sm:text-3xl"
                >
                  Shreyansh Jaiswal
                </h2>
                <p className="text-sm font-medium text-[#36C6D3]">
                  Founder &amp; CEO, Svario
                </p>
              </div>

              <p className="text-base leading-relaxed text-[#A7B0C4]">
                Building intelligent digital products with a focus on AI,
                software development, and automation. Through Shreyansh Codes, I
                work on creating practical technology solutions, websites,
                applications, and AI-powered systems.
              </p>

              <div className="pt-2">
                <span className="inline-flex items-center gap-2 rounded-full border border-[#A7B0C4]/25 bg-[#0B1020]/70 px-4 py-1.5 text-xs font-medium text-[#F5F7FC]">
                  <span
                    aria-hidden="true"
                    className="h-2 w-2 rounded-full bg-[#36C6D3]"
                  />
                  Developed with Shreyansh Codes
                </span>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="relative z-10 mt-16 border-t border-[#A7B0C4]/15 bg-[#0B1020]/90 py-10">
        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-6 px-6 text-xs text-[#A7B0C4] sm:flex-row sm:items-center">
          <SvarioBrandLogo compact />
          <div className="flex flex-wrap items-center gap-5">
            <Link href="/" className="transition hover:text-[#F5F7FC]">
              Home
            </Link>
            <Link href="/#pricing" className="transition hover:text-[#F5F7FC]">
              Pricing
            </Link>
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
