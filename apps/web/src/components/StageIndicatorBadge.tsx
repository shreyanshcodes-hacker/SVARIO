import React from "react";
import { SVARIO_BRAND } from "@/config/brand";

export function StageIndicatorBadge(): React.JSX.Element {
  return (
    <div
      role="status"
      aria-label="Current Development Stage"
      className="inline-flex flex-wrap items-center gap-2.5 rounded-full border border-[#7657F6]/45 bg-[#171D33]/90 px-4 py-1.5 text-xs font-medium text-[#F5F7FC] shadow-[0_0_20px_rgba(118,87,246,0.18)]"
    >
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#36C6D3] opacity-75" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-[#36C6D3]" />
      </span>
      <span className="font-mono font-semibold tracking-wider text-[#36C6D3]">
        {SVARIO_BRAND.stageTitle}
      </span>
      <span className="text-[#A7B0C4]">•</span>
      <span className="font-mono text-[11px] text-[#A7B0C4]">
        v{SVARIO_BRAND.version} Architecture Baseline
      </span>
    </div>
  );
}
