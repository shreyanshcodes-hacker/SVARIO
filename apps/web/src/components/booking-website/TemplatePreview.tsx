"use client";

import React, { useState } from "react";
import type { BookingWebsiteTemplateId, PublicBookingWebsiteData } from "@/types/website";
import { PublicBookingWebsiteRenderer } from "./PublicBookingWebsiteRenderer";
import { resolveTemplateEntry } from "./template-registry";

export interface TemplatePreviewProps {
  data: PublicBookingWebsiteData;
  isOpen: boolean;
  isOwnerOrAdmin: boolean;
  onClose: () => void;
  onApplyTemplate?: (templateId: BookingWebsiteTemplateId) => void;
  isCurrentlySelected?: boolean;
}

type ViewportMode = "desktop" | "tablet" | "mobile";

export function TemplatePreview({
  data,
  isOpen,
  isOwnerOrAdmin,
  onClose,
  onApplyTemplate,
  isCurrentlySelected = false,
}: TemplatePreviewProps): React.JSX.Element | null {
  const [viewport, setViewport] = useState<ViewportMode>("desktop");

  if (!isOpen) return null;

  const entry = resolveTemplateEntry(data.template_id);
  const frameWidthClass =
    viewport === "mobile"
      ? "max-w-[390px]"
      : viewport === "tablet"
      ? "max-w-[768px]"
      : "max-w-full";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Full-page preview: ${entry.name}`}
      data-testid="template-full-preview-modal"
      className="fixed inset-0 z-50 flex flex-col bg-[#060913]/95 backdrop-blur-md"
    >
      {/* Top Preview Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/15 bg-[#0B1020] px-5 py-3 text-xs text-[#F5F7FC]">
        <div className="flex items-center gap-3">
          <span className="rounded-lg bg-[#7657F6]/20 px-2.5 py-1 font-mono text-[11px] text-[#C4B5FD]">
            Template {entry.code}: {entry.name}
          </span>
          <span className="hidden font-mono text-[11px] text-[#A7B0C4] sm:inline">
            svario.ai/s/{data.slug}
          </span>
        </div>

        <div className="flex items-center gap-1 rounded-xl border border-white/10 bg-[#171D33] p-1">
          {(["desktop", "tablet", "mobile"] as ViewportMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setViewport(mode)}
              className={`rounded-lg px-3 py-1 text-[11px] font-semibold capitalize transition ${
                viewport === mode
                  ? "bg-[#7657F6] text-white"
                  : "text-[#A7B0C4] hover:text-white"
              }`}
            >
              {mode}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          {onApplyTemplate && (
            <button
              type="button"
              disabled={!isOwnerOrAdmin || isCurrentlySelected}
              onClick={() => {
                onApplyTemplate(entry.id);
                onClose();
              }}
              className="rounded-xl bg-[#7657F6] px-4 py-1.5 text-xs font-semibold text-white hover:bg-[#6546e6] disabled:opacity-45"
            >
              {isCurrentlySelected ? "Currently Selected" : "Select This Template"}
            </button>
          )}
          <button
            type="button"
            data-testid="close-template-preview-button"
            onClick={onClose}
            className="rounded-xl border border-white/20 px-3.5 py-1.5 text-xs font-semibold text-[#F5F7FC] hover:bg-white/10"
          >
            Close Preview
          </button>
        </div>
      </div>

      {/* Scrollable Rendered Preview Frame */}
      <div className="flex-1 overflow-auto p-4 sm:p-6">
        <div
          className={`mx-auto min-h-full overflow-hidden rounded-2xl border border-white/15 bg-white shadow-2xl transition-all duration-200 ${frameWidthClass}`}
        >
          <PublicBookingWebsiteRenderer data={data} isPreview={true} />
        </div>
      </div>
    </div>
  );
}
