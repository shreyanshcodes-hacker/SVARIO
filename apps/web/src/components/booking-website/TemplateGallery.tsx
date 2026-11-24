"use client";

import React from "react";
import type { BookingWebsiteTemplateId } from "@/types/website";
import { TEMPLATE_CATALOG, type TemplateMetadata } from "./template-registry";

export interface TemplateGalleryProps {
  selectedTemplateId: BookingWebsiteTemplateId;
  salonName: string;
  isOwnerOrAdmin: boolean;
  onSelectTemplate: (templateId: BookingWebsiteTemplateId) => void;
  onPreviewTemplate: (templateId: BookingWebsiteTemplateId) => void;
}

function MiniTemplateThumbnail({
  meta,
  salonName,
}: {
  meta: TemplateMetadata;
  salonName: string;
}): React.JSX.Element {
  const [bg, accent, ink] = meta.swatches;

  return (
    <div
      className="relative h-40 w-full overflow-hidden rounded-xl border border-white/10 p-3 select-none"
      style={{ backgroundColor: bg, color: ink }}
    >
      {/* Top nav wireframe */}
      <div className="flex items-center justify-between border-b pb-1.5" style={{ borderColor: `${ink}22` }}>
        <span className="truncate text-[9px] font-bold tracking-wider uppercase">{salonName}</span>
        <span
          className="rounded px-1.5 py-0.5 text-[7px] font-bold uppercase"
          style={{ backgroundColor: accent, color: bg }}
        >
          Book
        </span>
      </div>

      {/* Distinct structural mini-layout per template */}
      {meta.layoutStyle === "split_editorial" && (
        <div className="mt-3 grid grid-cols-12 gap-2">
          <div className="col-span-7 space-y-1.5">
            <div className="h-1.5 w-10 rounded" style={{ backgroundColor: accent }} />
            <div className="h-2.5 w-full rounded" style={{ backgroundColor: `${ink}CC` }} />
            <div className="h-2 w-4/5 rounded" style={{ backgroundColor: `${ink}55` }} />
            <div className="mt-2 h-4 w-16 rounded" style={{ backgroundColor: accent }} />
          </div>
          <div
            className="col-span-5 h-20 border p-1"
            style={{ borderColor: accent, backgroundColor: `${accent}22` }}
          />
        </div>
      )}

      {meta.layoutStyle === "centered_minimal" && (
        <div className="mt-3 flex flex-col items-center space-y-1.5 text-center">
          <div className="h-1.5 w-12 rounded" style={{ backgroundColor: `${ink}44` }} />
          <div className="h-2.5 w-32 rounded" style={{ backgroundColor: `${ink}CC` }} />
          <div className="h-12 w-full rounded-lg border" style={{ borderColor: accent, backgroundColor: accent }} />
        </div>
      )}

      {meta.layoutStyle === "arched_cards" && (
        <div className="mt-2.5 grid grid-cols-12 items-center gap-2">
          <div className="col-span-7 space-y-1.5">
            <div className="h-2 w-14 rounded-full" style={{ backgroundColor: `${accent}44` }} />
            <div className="h-2.5 w-full rounded" style={{ backgroundColor: `${ink}CC` }} />
            <div className="h-4 w-16 rounded-full" style={{ backgroundColor: accent }} />
          </div>
          <div
            className="col-span-5 h-20 rounded-t-full rounded-b-lg border-2 border-white"
            style={{ backgroundColor: `${accent}55` }}
          />
        </div>
      )}

      {meta.layoutStyle === "grid_matrix" && (
        <div className="mt-2 grid grid-cols-12 border" style={{ borderColor: `${ink}33` }}>
          <div className="col-span-7 space-y-1.5 border-r p-2" style={{ borderColor: `${ink}33` }}>
            <div className="h-3 w-full bg-white/90" />
            <div className="h-2 w-3/4 bg-white/40" />
            <div className="h-3.5 w-14 bg-white" />
          </div>
          <div className="col-span-5 bg-white/10 p-2" />
        </div>
      )}

      {meta.layoutStyle === "organic_curves" && (
        <div className="mt-2.5 rounded-2xl p-2.5" style={{ backgroundColor: ink === "#E9EFE3" ? "#E9EFE3" : "#E9EFE3" }}>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1.5">
              <div className="h-2 w-12 rounded-full" style={{ backgroundColor: accent }} />
              <div className="h-2.5 w-full rounded bg-[#243228]/80" />
              <div className="h-3.5 w-14 rounded-full" style={{ backgroundColor: accent }} />
            </div>
            <div className="h-16 rounded-2xl bg-[#3D5A45]/25" />
          </div>
        </div>
      )}

      {meta.layoutStyle === "bold_pop" && (
        <div className="mt-2.5 grid grid-cols-12 items-center gap-2">
          <div className="col-span-7 space-y-1.5">
            <div className="h-2.5 w-16 rounded-full border border-black" style={{ backgroundColor: ink }} />
            <div className="h-3 w-full rounded bg-[#12131F]" />
            <div
              className="h-4 w-16 rounded border border-black shadow-[2px_2px_0px_#000]"
              style={{ backgroundColor: accent }}
            />
          </div>
          <div
            className="col-span-5 h-20 rounded-xl border-2 border-black shadow-[3px_3px_0px_#000]"
            style={{ backgroundColor: accent }}
          />
        </div>
      )}

      {meta.layoutStyle === "magazine_masthead" && (
        <div className="mt-2 space-y-2">
          <div className="border-b border-black/30 pb-1 text-center font-serif text-[10px] tracking-widest uppercase">
            {salonName}
          </div>
          <div className="grid grid-cols-12 gap-2">
            <div className="col-span-8 h-16 bg-zinc-800" />
            <div className="col-span-4 space-y-1 border-l border-black/20 pl-1.5">
              <div className="h-2 w-full bg-black/80" />
              <div className="h-1.5 w-4/5 bg-black/40" />
              <div className="h-3 w-full bg-black" />
            </div>
          </div>
        </div>
      )}

      {meta.layoutStyle === "classic_sidebar" && (
        <div className="mt-2 grid grid-cols-12 gap-2">
          <div className="col-span-8 space-y-1.5">
            <div className="h-10 w-full rounded bg-slate-200" />
            <div className="h-2.5 w-full rounded bg-slate-300" />
            <div className="h-2.5 w-4/5 rounded bg-slate-200" />
          </div>
          <div className="col-span-4 space-y-1.5 rounded border border-slate-200 p-1.5">
            <div className="h-3 w-full rounded" style={{ backgroundColor: accent }} />
            <div className="h-1.5 w-full rounded bg-slate-300" />
            <div className="h-1.5 w-3/4 rounded bg-slate-200" />
          </div>
        </div>
      )}

      {/* Template code badge */}
      <span className="absolute right-2 bottom-2 rounded bg-black/65 px-1.5 py-0.5 font-mono text-[9px] text-white">
        T{meta.code}
      </span>
    </div>
  );
}

export function TemplateGallery({
  selectedTemplateId,
  salonName,
  isOwnerOrAdmin,
  onSelectTemplate,
  onPreviewTemplate,
}: TemplateGalleryProps): React.JSX.Element {
  return (
    <section
      data-testid="template-gallery"
      className="space-y-5 rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#F5F7FC]">Website Templates (8 Designs)</h2>
          <p className="mt-1 text-xs text-[#A7B0C4]">
            Choose a layout for your salon website. Switching templates preserves your business profile,
            logo, cover image, services, slug, and AI receptionist settings.
          </p>
        </div>
        <span className="rounded-full border border-[#36C6D3]/40 bg-[#36C6D3]/10 px-3 py-1 font-mono text-[11px] text-[#36C6D3]">
          Active: {selectedTemplateId}
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {TEMPLATE_CATALOG.map((meta) => {
          const isSelected = meta.id === selectedTemplateId;
          return (
            <div
              key={meta.id}
              data-testid={`template-card-${meta.id}`}
              className={`flex flex-col justify-between rounded-2xl border p-3.5 transition ${
                isSelected
                  ? "border-[#7657F6] bg-[#7657F6]/10 ring-1 ring-[#7657F6]/50"
                  : "border-white/10 bg-[#0B1020]/70 hover:border-white/25"
              }`}
            >
              <div>
                <MiniTemplateThumbnail meta={meta} salonName={salonName || "Your Salon"} />

                <div className="mt-3 flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-bold text-[#F5F7FC]">{meta.name}</h3>
                    <p className="text-[11px] text-[#36C6D3]">{meta.vibe}</p>
                  </div>
                  {isSelected && (
                    <span
                      data-testid={`template-selected-badge-${meta.id}`}
                      className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-300"
                    >
                      Selected
                    </span>
                  )}
                </div>

                <p className="mt-2 text-xs leading-relaxed text-[#A7B0C4]">{meta.description}</p>
              </div>

              <div className="mt-4 flex items-center gap-2 pt-2">
                <button
                  type="button"
                  data-testid={`preview-template-${meta.id}`}
                  onClick={() => onPreviewTemplate(meta.id)}
                  className="flex-1 rounded-xl border border-white/15 bg-[#171D33] px-3 py-2 text-xs font-semibold text-[#F5F7FC] transition hover:border-[#36C6D3]/60"
                >
                  Preview
                </button>
                <button
                  type="button"
                  data-testid={`select-template-${meta.id}`}
                  disabled={!isOwnerOrAdmin || isSelected}
                  onClick={() => onSelectTemplate(meta.id)}
                  className="flex-1 rounded-xl bg-[#7657F6] px-3 py-2 text-xs font-semibold text-white transition hover:bg-[#6546e6] disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {isSelected ? "Active" : "Select"}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
