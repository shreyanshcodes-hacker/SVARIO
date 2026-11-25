import React from "react";

interface SkeletonBlockProps {
  className?: string;
}

export function SkeletonBlock({ className = "h-4 w-full" }: SkeletonBlockProps) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-lg bg-[#A7B0C4]/15 ${className}`}
    />
  );
}

interface InlineSpinnerProps {
  className?: string;
  label?: string;
}

export function InlineSpinner({
  className = "h-3.5 w-3.5",
  label,
}: InlineSpinnerProps) {
  return (
    <span className="inline-flex items-center gap-2">
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        fill="none"
        className={`animate-spin text-current ${className}`}
      >
        <circle
          cx="12"
          cy="12"
          r="9"
          stroke="currentColor"
          strokeOpacity="0.25"
          strokeWidth="3"
        />
        <path
          d="M21 12a9 9 0 0 0-9-9"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
      {label ? <span>{label}</span> : null}
    </span>
  );
}

interface WorkspaceSkeletonProps {
  label?: string;
  cards?: number;
}

export function DashboardWorkspaceSkeleton({
  label = "Loading workspace...",
  cards = 3,
}: WorkspaceSkeletonProps) {
  return (
    <div
      role="status"
      aria-label={label}
      className="space-y-6 rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/80 p-6 sm:p-8"
    >
      <span className="sr-only">{label}</span>
      <div className="flex flex-col justify-between gap-4 border-b border-[#A7B0C4]/15 pb-6 sm:flex-row sm:items-center">
        <div className="space-y-2">
          <SkeletonBlock className="h-3 w-32 bg-[#36C6D3]/20" />
          <SkeletonBlock className="h-7 w-56" />
        </div>
        <div className="flex gap-3">
          <SkeletonBlock className="h-8 w-36 rounded-xl" />
          <SkeletonBlock className="h-8 w-32 rounded-xl bg-[#7657F6]/25" />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: cards }).map((_, idx) => (
          <div
            key={idx}
            className="space-y-3 rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/80 p-5"
          >
            <SkeletonBlock className="h-3 w-28 bg-[#36C6D3]/20" />
            <SkeletonBlock className="h-5 w-40" />
            <SkeletonBlock className="h-3 w-full" />
            <SkeletonBlock className="h-3 w-4/5" />
          </div>
        ))}
      </div>
    </div>
  );
}

interface SectionSkeletonProps {
  label?: string;
  rows?: number;
}

export function SectionContentSkeleton({
  label = "Loading section...",
  rows = 4,
}: SectionSkeletonProps) {
  return (
    <div
      role="status"
      aria-label={label}
      className="space-y-4 rounded-2xl border border-[#A7B0C4]/15 bg-[#171D33]/60 p-6"
    >
      <span className="sr-only">{label}</span>
      <div className="flex items-center justify-between gap-4">
        <SkeletonBlock className="h-5 w-48" />
        <SkeletonBlock className="h-8 w-28 rounded-xl" />
      </div>
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, idx) => (
          <div
            key={idx}
            className="flex items-center justify-between gap-4 rounded-xl border border-[#A7B0C4]/10 bg-[#0B1020]/60 p-4"
          >
            <div className="w-full space-y-2">
              <SkeletonBlock className="h-4 w-1/3" />
              <SkeletonBlock className="h-3 w-1/2" />
            </div>
            <SkeletonBlock className="h-7 w-20 shrink-0 rounded-lg" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function BookingStudioSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading Booking Website Studio configuration..."
      className="grid gap-6 lg:grid-cols-[240px_1fr]"
    >
      <span className="sr-only">
        Loading Booking Website Studio configuration...
      </span>
      <div className="space-y-2 rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-3">
        <SkeletonBlock className="mb-3 h-4 w-32" />
        {Array.from({ length: 6 }).map((_, idx) => (
          <SkeletonBlock key={idx} className="h-9 w-full rounded-xl" />
        ))}
      </div>
      <SectionContentSkeleton
        label="Loading studio controls..."
        rows={5}
      />
    </div>
  );
}
