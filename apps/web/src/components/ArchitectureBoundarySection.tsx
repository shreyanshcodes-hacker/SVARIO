import React from "react";
import { SHARED_PLATFORM_SUBSYSTEMS } from "@/config/brand";

export function ArchitectureBoundarySection(): React.JSX.Element {
  return (
    <section
      aria-labelledby="shared-architecture-heading"
      className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/70 p-6 sm:p-8"
    >
      <div className="flex flex-col justify-between gap-4 border-b border-[#A7B0C4]/15 pb-6 md:flex-row md:items-end">
        <div>
          <span className="font-mono text-xs font-semibold uppercase tracking-widest text-[#36C6D3]">
            Multi-Industry Architecture Boundaries
          </span>
          <h2
            id="shared-architecture-heading"
            className="mt-1 text-xl font-bold tracking-tight text-[#F5F7FC] sm:text-2xl"
          >
            Shared Core Infrastructure × Domain Modules
          </h2>
        </div>
        <p className="max-w-xl text-xs leading-relaxed text-[#A7B0C4] sm:text-sm">
          Each industry vertical (Salons, Clinics, Hospitals) is isolated in its
          own domain module and communicates exclusively through typed contracts
          with Svario&apos;s four shared infrastructure subsystems.
        </p>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {SHARED_PLATFORM_SUBSYSTEMS.map((subsystem) => (
          <div
            key={subsystem.id}
            className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/80 p-4"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-xs font-semibold uppercase tracking-wider text-[#7657F6]">
                {subsystem.id}
              </span>
              <span className="rounded bg-[#171D33] px-2 py-0.5 font-mono text-[10px] text-[#36C6D3]">
                Contract Ready
              </span>
            </div>
            <h3 className="mt-2 text-sm font-semibold text-[#F5F7FC]">
              {subsystem.name}
            </h3>
            <p className="mt-1.5 text-xs leading-relaxed text-[#A7B0C4]">
              {subsystem.description}
            </p>
            <div className="mt-3 border-t border-[#A7B0C4]/10 pt-2.5 font-mono text-[10px] text-[#A7B0C4]">
              Target: {subsystem.plannedStack}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
