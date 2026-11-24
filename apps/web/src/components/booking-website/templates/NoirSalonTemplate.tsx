"use client";

import React from "react";
import {
  formatFullAddress,
  formatHourRange,
  formatServicePrice,
  formatShortWeekday,
  getButtonRadiusClass,
  getFontFamilyStack,
  safeExternalHref,
  type TemplateComponentProps,
} from "../template-utils";

/**
 * Template 04 — Noir Salon
 * Dark contemporary charcoal & obsidian studio with architectural grid lines,
 * bold uppercase grotesk typography, structured service matrix, and stark CTA bar.
 */
export function NoirSalonTemplate({ data, onBookClick }: TemplateComponentProps): React.JSX.Element {
  const radius = getButtonRadiusClass(data.button_style);
  const fullAddress = formatFullAddress(data);
  const igHref = safeExternalHref(data.social_instagram, "instagram");
  const fbHref = safeExternalHref(data.social_facebook, "facebook");
  const waHref = safeExternalHref(data.social_whatsapp, "whatsapp");

  return (
    <div
      data-testid="template-noir_salon"
      className="min-h-full bg-[#111214] text-[#F2F2F2]"
      style={{ fontFamily: getFontFamilyStack(data.font_family) }}
    >
      {/* Architectural Top Bar */}
      <header className="border-b border-white/15">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            {data.logo_url && (
              <img
                src={data.logo_url}
                alt={`${data.business.display_name} logo`}
                className="h-8 w-8 object-cover grayscale"
              />
            )}
            <span className="text-sm font-bold tracking-[0.24em] uppercase">
              {data.business.display_name}
            </span>
          </div>
          <div className="flex items-center gap-6">
            <span className="hidden font-mono text-[11px] uppercase text-zinc-400 md:inline">
              {data.business.city || "STUDIO"} / {data.business.timezone}
            </span>
            <button
              type="button"
              onClick={() => onBookClick?.()}
              className={`${radius} bg-white px-4 py-2 text-xs font-bold tracking-[0.14em] uppercase text-[#111214] transition hover:bg-zinc-200`}
            >
              Book Slot
            </button>
          </div>
        </div>
      </header>

      {/* Asymmetric Architectural Hero Grid */}
      <section className="mx-auto grid max-w-6xl border-b border-white/15 lg:grid-cols-12">
        <div className="flex flex-col justify-between border-b border-white/15 p-8 lg:col-span-7 lg:border-r lg:border-b-0 lg:p-12">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.22em] text-zinc-400">
              CONTEMPORARY HAIR & GROOMING
            </p>
            <h1 className="mt-5 text-4xl font-black uppercase leading-[1.03] tracking-tight sm:text-6xl">
              {data.headline || data.business.display_name}
            </h1>
          </div>
          <div className="mt-10 space-y-6">
            <p className="max-w-lg text-sm leading-relaxed text-zinc-300">
              {data.tagline ||
                data.business.description ||
                "Precision cuts, modern color architecture, and sharp styling built for today."}
            </p>
            <div className="flex flex-wrap items-center gap-4">
              <button
                type="button"
                onClick={() => onBookClick?.()}
                className={`${radius} bg-white px-7 py-3.5 text-xs font-bold tracking-[0.18em] uppercase text-[#111214] transition hover:bg-zinc-200`}
              >
                Book Appointment →
              </button>
              {data.business.phone && (
                <a
                  href={`tel:${data.business.phone}`}
                  className="font-mono text-xs text-zinc-400 hover:text-white"
                >
                  TEL {data.business.phone}
                </a>
              )}
            </div>
          </div>
        </div>

        <div className="relative bg-[#18191C] lg:col-span-5">
          {data.cover_image_url ? (
            <img
              src={data.cover_image_url}
              alt={`${data.business.display_name} studio`}
              className="h-[320px] w-full object-cover contrast-110 lg:h-full lg:min-h-[420px]"
            />
          ) : (
            <div className="flex h-[300px] flex-col justify-between p-8 lg:h-full lg:min-h-[420px]">
              <span className="font-mono text-xs text-zinc-500">NOIR // 04</span>
              <div>
                <p className="text-3xl font-black uppercase tracking-tight text-white/90">
                  Sharp. Modern. Unapologetic.
                </p>
                <p className="mt-2 font-mono text-xs text-zinc-400">
                  {fullAddress || data.business.display_name}
                </p>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Structured Service Matrix */}
      {data.show_services && (
        <section id="services" className="mx-auto max-w-6xl border-b border-white/15 px-6 py-16">
          <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.22em] text-zinc-500">01 / MENU</p>
              <h2 className="mt-1 text-3xl font-black uppercase tracking-tight">Service Matrix</h2>
            </div>
            <span className="font-mono text-xs text-zinc-400">
              {data.services.length} ACTIVE SERVICES
            </span>
          </div>

          <div className="divide-y divide-white/15 border-y border-white/15">
            {data.services.length === 0 ? (
              <div className="py-8 font-mono text-xs text-zinc-400">
                MENU AVAILABLE ON REQUEST — CALL OR BOOK ONLINE.
              </div>
            ) : (
              data.services.map((svc) => (
                <div
                  key={svc.id}
                  className="grid items-center gap-3 py-5 sm:grid-cols-12"
                >
                  <div className="sm:col-span-5">
                    <h3 className="text-base font-bold uppercase tracking-wide text-white">{svc.name}</h3>
                    {svc.description && (
                      <p className="mt-1 text-xs text-zinc-400">{svc.description}</p>
                    )}
                  </div>
                  <div className="font-mono text-xs uppercase text-zinc-500 sm:col-span-2">
                    {svc.category || "STUDIO"}
                  </div>
                  <div className="font-mono text-xs text-zinc-400 sm:col-span-2">
                    {svc.duration_minutes} MIN
                  </div>
                  <div className="flex items-center justify-between gap-3 sm:col-span-3 sm:justify-end">
                    <span className="font-mono text-sm font-bold text-white">
                      {formatServicePrice(svc.price, svc.currency)}
                    </span>
                    <button
                      type="button"
                      onClick={() => onBookClick?.(svc)}
                      className={`${radius} border border-white/30 px-3.5 py-1.5 text-[11px] font-bold uppercase tracking-wider text-white transition hover:bg-white hover:text-[#111214]`}
                    >
                      Book
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      )}

      {/* Horizontal Hours & Studio Strip */}
      <section className="mx-auto max-w-6xl px-6 py-14">
        <div className="grid gap-8 md:grid-cols-12">
          <div className="space-y-3 md:col-span-5">
            <p className="font-mono text-xs uppercase tracking-[0.22em] text-zinc-500">02 / STUDIO</p>
            <h2 className="text-2xl font-black uppercase">{data.business.display_name}</h2>
            {fullAddress && <p className="text-xs text-zinc-400">{fullAddress}</p>}
            {data.receptionist.enabled && (
              <p className="border-l-2 border-white pl-3 text-xs text-zinc-300">
                AI Concierge ({data.receptionist.assistant_name || "Svario"}): {data.receptionist.greeting}
              </p>
            )}
          </div>
          {data.show_hours && (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 md:col-span-7">
              {data.hours.map((h) => (
                <div key={h.weekday} className="border border-white/15 bg-[#18191C] p-3">
                  <p className="font-mono text-[10px] uppercase text-zinc-500">
                    {formatShortWeekday(h.weekday)}
                  </p>
                  <p className="mt-1 font-mono text-xs text-white">{formatHourRange(h)}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <footer className="border-t border-white/15 bg-[#0B0C0D] px-6 py-6">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 font-mono text-[11px] uppercase text-zinc-500">
          <span>© {data.business.display_name}</span>
          <div className="flex gap-5">
            {igHref && <a href={igHref} target="_blank" rel="noreferrer" className="hover:text-white">IG</a>}
            {fbHref && <a href={fbHref} target="_blank" rel="noreferrer" className="hover:text-white">FB</a>}
            {waHref && <a href={waHref} target="_blank" rel="noreferrer" className="hover:text-white">WA</a>}
          </div>
        </div>
      </footer>
    </div>
  );
}
