import React from "react";
import type { IndustryCardItem } from "@/types/platform";

interface IndustryCardProps {
  industry: IndustryCardItem;
}

export function IndustryCard({ industry }: IndustryCardProps): React.JSX.Element {
  return (
    <article className="group relative flex flex-col justify-between rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-6 shadow-[0_14px_34px_rgba(11,16,32,0.5)] transition duration-200 hover:border-[#7657F6]/60 hover:shadow-[0_0_32px_rgba(118,87,246,0.2)]">
      <div>
        <div className="mb-4 flex items-center justify-between gap-2">
          <span className="font-mono text-[11px] font-semibold uppercase tracking-widest text-[#36C6D3]">
            {industry.categoryLabel}
          </span>
          <span className="rounded-full border border-[#A7B0C4]/25 bg-[#0B1020] px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-[#A7B0C4]">
            Informational • Stage 0
          </span>
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

        <div className="mt-5 rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/70 p-3.5">
          <div className="font-mono text-[10px] uppercase tracking-wider text-[#A7B0C4]">
            Target Voice Persona
          </div>
          <div className="mt-1 text-xs font-medium text-[#F5F7FC]">
            {industry.voicePersona}
          </div>
        </div>

        <div className="mt-5">
          <h4 className="font-mono text-[11px] font-semibold uppercase tracking-wider text-[#A7B0C4]">
            Planned Domain Workflows (Future Stages)
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
      </div>

      <div className="mt-6 border-t border-[#A7B0C4]/15 pt-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="font-mono text-[10px] uppercase tracking-wider text-[#A7B0C4]">
            Shared Platform Contracts
          </span>
          <div className="flex flex-wrap gap-1.5">
            {industry.sharedSubsystems.map((subsystem) => (
              <span
                key={subsystem}
                className="rounded-md border border-[#7657F6]/30 bg-[#0B1020] px-2 py-0.5 font-mono text-[10px] text-[#F5F7FC]"
              >
                {subsystem}
              </span>
            ))}
          </div>
        </div>
      </div>
    </article>
  );
}
