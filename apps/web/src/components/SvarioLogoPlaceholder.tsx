import React from "react";
import { SVARIO_BRAND } from "@/config/brand";

export function SvarioLogoPlaceholder(): React.JSX.Element {
  return (
    <div className="inline-flex items-center gap-3.5 select-none">
      {/* Stage 0 Logo Placeholder Box — Deliberately non-finalized geometric frame */}
      <div
        aria-label="Svario logo placeholder"
        className="relative flex h-11 w-11 items-center justify-center rounded-xl border border-dashed border-[#7657F6]/70 bg-[#171D33]/90 shadow-[0_0_24px_rgba(118,87,246,0.22)]"
      >
        <span className="font-mono text-xs font-semibold tracking-tighter text-[#36C6D3]">
          [S]
        </span>
        <span
          className="absolute -bottom-1 -right-1 rounded bg-[#0B1020] px-1 py-0.5 font-mono text-[9px] uppercase tracking-wider text-[#A7B0C4] ring-1 ring-[#7657F6]/40"
          title="Logo Placeholder — Stage 0 Foundation"
        >
          PH
        </span>
      </div>

      <div className="flex flex-col">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold tracking-[0.22em] text-[#F5F7FC]">
            {SVARIO_BRAND.name}
          </span>
          <span className="rounded-md border border-[#A7B0C4]/25 bg-[#171D33]/80 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-[#A7B0C4]">
            Logo Placeholder
          </span>
        </div>
        <span className="text-xs text-[#A7B0C4]">{SVARIO_BRAND.tagline}</span>
      </div>
    </div>
  );
}
