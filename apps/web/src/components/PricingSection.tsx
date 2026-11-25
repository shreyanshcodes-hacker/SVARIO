import React from "react";
import Link from "next/link";

const STARTER_VERIFIED_FEATURES: readonly string[] = [
  "AI Voice Receptionist",
  "24/7 Call Handling",
  "Automatic Appointment Booking",
  "Salon Service and Pricing Information",
  "Live Appointment Availability",
  "Appointment Rescheduling",
  "Appointment Cancellation",
  "Customer Information Capture",
  "Public Salon Website",
  "AI Receptionist on Salon Website",
  "Salon Owner Dashboard",
  "Appointment Management",
];

export function PricingSection(): React.JSX.Element {
  return (
    <section
      id="pricing"
      aria-labelledby="pricing-heading"
      className="scroll-mt-24 space-y-10"
    >
      <div className="mx-auto max-w-2xl text-center">
        <span className="inline-flex items-center rounded-full border border-[#7657F6]/35 bg-[#7657F6]/10 px-3 py-1 font-mono text-xs font-semibold uppercase tracking-widest text-[#36C6D3]">
          Pricing
        </span>
        <h2
          id="pricing-heading"
          className="mt-3 text-3xl font-extrabold tracking-tight text-[#F5F7FC] sm:text-4xl"
        >
          Simple, Transparent Pricing
        </h2>
        <p className="mt-3 text-base leading-relaxed text-[#A7B0C4]">
          Everything your salon needs to manage customer calls and appointments.
        </p>
      </div>

      <div className="mx-auto grid max-w-5xl items-stretch gap-6 md:grid-cols-2">
        {/* PLAN 1: STARTER */}
        <article
          aria-label="Starter Plan"
          className="relative flex flex-col justify-between rounded-2xl border border-[#7657F6]/55 bg-[#171D33]/95 p-7 shadow-[0_18px_48px_rgba(118,87,246,0.16)] sm:p-8"
        >
          <div>
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-xl font-bold text-[#F5F7FC]">Starter</h3>
              <span className="rounded-full border border-[#36C6D3]/45 bg-[#36C6D3]/15 px-3 py-1 text-xs font-semibold text-[#36C6D3]">
                Available Now
              </span>
            </div>

            <div className="mt-6 flex items-baseline gap-2 border-b border-[#A7B0C4]/15 pb-6">
              <span className="text-4xl font-extrabold tracking-tight text-[#F5F7FC] sm:text-5xl">
                ₹3,999
              </span>
              <span className="text-sm font-medium text-[#A7B0C4]">
                Per month
              </span>
            </div>

            <ul className="mt-6 grid grid-cols-1 gap-3 text-sm text-[#F5F7FC]/95 sm:grid-cols-2 md:grid-cols-1 lg:grid-cols-2">
              {STARTER_VERIFIED_FEATURES.map((feature) => (
                <li key={feature} className="flex items-start gap-2.5">
                  <span
                    aria-hidden="true"
                    className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#36C6D3]/15 text-xs font-bold text-[#36C6D3]"
                  >
                    ✓
                  </span>
                  <span className="leading-snug">{feature}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-8 pt-4">
            <Link
              href="/signup"
              className="flex w-full items-center justify-center rounded-xl bg-[#7657F6] px-5 py-3 text-sm font-semibold text-[#F5F7FC] shadow-[0_0_24px_rgba(118,87,246,0.35)] transition hover:bg-[#6546e6]"
            >
              Get Started
            </Link>
          </div>
        </article>

        {/* PLAN 2: PRO — COMING SOON */}
        <article
          aria-label="Pro Plan"
          className="relative flex flex-col justify-between rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/65 p-7 sm:p-8"
        >
          <div>
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-xl font-bold text-[#F5F7FC]">Pro</h3>
              <span className="rounded-full border border-[#7657F6]/40 bg-[#7657F6]/15 px-3 py-1 text-xs font-semibold text-[#C4B5FD]">
                Coming Soon
              </span>
            </div>

            <div className="mt-6 flex items-baseline gap-2 border-b border-[#A7B0C4]/15 pb-6">
              <span className="text-3xl font-bold tracking-tight text-[#F5F7FC]/90 sm:text-4xl">
                Coming Soon
              </span>
            </div>

            <div className="mt-8 rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/55 p-6 text-center">
              <p className="text-sm font-medium text-[#F5F7FC]">
                Pro plan is coming soon.
              </p>
              <p className="mt-2 text-xs leading-relaxed text-[#A7B0C4]">
                Start with the Starter plan today to launch your salon&apos;s AI
                voice receptionist and public booking website.
              </p>
            </div>
          </div>

          <div className="mt-8 pt-4">
            <div
              aria-label="Pro plan coming soon"
              className="flex w-full items-center justify-center rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020]/60 px-5 py-3 text-sm font-semibold text-[#A7B0C4]"
            >
              Coming Soon
            </div>
          </div>
        </article>
      </div>
    </section>
  );
}
