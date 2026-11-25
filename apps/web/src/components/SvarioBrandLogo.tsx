import React from "react";
import { SVARIO_BRAND } from "@/config/brand";

export interface SvarioBrandLogoProps {
  /** Compact mode hides the tagline (ideal for footers or tight headers). */
  compact?: boolean;
  /** Surface theme hint to ensure crisp contrast on dark or light backgrounds. */
  variant?: "dark" | "light";
  className?: string;
}

export function SvarioBrandLogo({
  compact = false,
  variant = "dark",
  className = "",
}: SvarioBrandLogoProps): React.JSX.Element {
  const isLight = variant === "light";

  return (
    <div className={`inline-flex items-center gap-3 select-none ${className}`}>
      <div
        className={`relative flex shrink-0 items-center justify-center overflow-hidden rounded-xl border ${
          compact ? "h-9 w-9" : "h-11 w-11"
        } ${
          isLight
            ? "border-[#171D33]/15 bg-[#0B1020] shadow-sm"
            : "border-[#7657F6]/40 bg-[#0B1020] shadow-[0_0_20px_rgba(118,87,246,0.22)]"
        }`}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/svario-logo.jpg"
          alt="Svario logo"
          className="h-full w-full object-contain p-1"
        />
      </div>

      <div className="flex flex-col leading-tight">
        <span
          className={`font-bold tracking-[0.2em] ${
            compact ? "text-base" : "text-lg"
          } ${isLight ? "text-[#0B1020]" : "text-[#F5F7FC]"}`}
        >
          {SVARIO_BRAND.name}
        </span>
        {!compact && (
          <span
            className={`text-xs ${
              isLight ? "text-[#475569]" : "text-[#A7B0C4]"
            }`}
          >
            {SVARIO_BRAND.tagline}
          </span>
        )}
      </div>
    </div>
  );
}
