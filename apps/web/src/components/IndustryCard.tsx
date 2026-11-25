import React from "react";
import Link from "next/link";
import type { IndustryCardItem } from "@/types/platform";

interface IndustryCardProps {
  industry: IndustryCardItem;
}

export function IndustryCard({ industry }: IndustryCardProps): React.JSX.Element {
  const isAvailable = industry.availability === "available";

  return (
    <article
      aria-label={`${industry.name} Industry`}
      className={`group relative flex flex-col justify-between rounded-2xl border p-6 transition duration-200 ${
        isAvailable
          ? "border-[#7657F6]/55 bg-[#171D33]/95 shadow-[0_14px_34px_rgba(118,87,246,0.18)] hover:border-[#7657F6]"
          : "border-[#A7B0C4]/20 bg-[#171D33]/65 shadow-[0_14px_34px_rgba(11,16,32,0.45)]"
      }`}
    >
      <div>
        <div className="mb-4 flex items-center justify-between gap-2">
          <span className="font-mono text-[11px] font-semibold uppercase tracking-widest text-[#36C6D3]">
            {industry.categoryLabel}
          </span>
          {isAvailable ? (
            <span className="rounded-full border border-[#36C6D3]/45 bg-[#36C6D3]/15 px-2.5 py-0.5 text-[11px] font-semibold text-[#36C6D3]">
              Available Now
            </span>
          ) : (
            <span className="rounded-full border border-[#7657F6]/40 bg-[#7657F6]/15 px-2.5 py-0.5 text-[11px] font-semibold text-[#C4B5FD]">
              Coming Soon
            </span>
          )}
        </div>

        <h3 className="text-2xl font-bold tracking-tight text-[#F5F7FC]">
          {industry.name}
        </h3>
        <p className="mt-1 text-sm font-medium text-[#7657F6]">
          {industry.headline}
        </p>

        <p className="mt-3 text-sm leading-relaxed text-[#A7B0C4]">
          {industry.description}
        </p>

        {isAvailable && (
          <>
            <div className="mt-5 rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/70 p-3.5">
              <div className="font-mono text-[10px] uppercase tracking-wider text-[#A7B0C4]">
                Voice Experience
              </div>
              <div className="mt-1 text-xs font-medium text-[#F5F7FC]">
                {industry.voicePersona}
              </div>
            </div>

            {industry.plannedHighlights.length > 0 && (
              <div className="mt-5">
                <h4 className="font-mono text-[11px] font-semibold uppercase tracking-wider text-[#A7B0C4]">
                  Key Capabilities
                </h4>
                <ul className="mt-2.5 space-y-2">
                  {industry.plannedHighlights.map((item) => (
                    <li
                      key={item}
                      className="flex items-start gap-2 text-xs leading-relaxed text-[#F5F7FC]/90"
                    >
                      <span
                        aria-hidden="true"
                        className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#36C6D3]"
                      />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>

      <div className="mt-6 border-t border-[#A7B0C4]/15 pt-4">
        {isAvailable ? (
          <Link
            href="/signup"
            className="flex w-full items-center justify-center rounded-xl bg-[#7657F6] px-4 py-2.5 text-xs font-semibold text-[#F5F7FC] shadow-[0_0_18px_rgba(118,87,246,0.3)] transition hover:bg-[#6546e6]"
          >
            Get Started
          </Link>
        ) : (
          <div
            aria-label={`${industry.name} coming soon`}
            className="flex w-full items-center justify-center rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020]/60 px-4 py-2.5 text-xs font-semibold text-[#A7B0C4]"
          >
            Coming Soon
          </div>
        )}
      </div>
    </article>
  );
}
