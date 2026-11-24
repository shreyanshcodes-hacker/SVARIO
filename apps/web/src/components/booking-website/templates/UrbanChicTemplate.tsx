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
 * Template 06 — Urban Chic
 * Vibrant contemporary studio with oversized bold typography, energetic color accents,
 * offset hero card, and punchy 3-column service cards.
 */
export function UrbanChicTemplate({ data, onBookClick }: TemplateComponentProps): React.JSX.Element {
  const radius = getButtonRadiusClass(data.button_style);
  const fullAddress = formatFullAddress(data);
  const popPrimary = data.primary_color || "#6D28D9";
  const popSecondary = data.secondary_color || "#06B6D4";
  const igHref = safeExternalHref(data.social_instagram, "instagram");
  const fbHref = safeExternalHref(data.social_facebook, "facebook");
  const waHref = safeExternalHref(data.social_whatsapp, "whatsapp");

  return (
    <div
      data-testid="template-urban_chic"
      className="min-h-full bg-[#FAFAFF] text-[#12131F]"
      style={{ fontFamily: getFontFamilyStack(data.font_family) }}
    >
      {/* Energetic Top Header */}
      <header className="border-b-2 border-[#12131F] bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
          <div className="flex items-center gap-3">
            {data.logo_url ? (
              <img
                src={data.logo_url}
                alt={`${data.business.display_name} logo`}
                className="h-10 w-10 rounded-xl border-2 border-[#12131F] object-cover"
              />
            ) : (
              <div
                className="flex h-10 w-10 items-center justify-center rounded-xl border-2 border-[#12131F] text-sm font-black text-white"
                style={{ backgroundColor: popPrimary }}
              >
                {data.business.display_name.slice(0, 2).toUpperCase()}
              </div>
            )}
            <span className="text-lg font-extrabold tracking-tight">{data.business.display_name}</span>
          </div>

          <button
            type="button"
            onClick={() => onBookClick?.()}
            className={`${radius} border-2 border-[#12131F] px-5 py-2 text-xs font-extrabold uppercase tracking-wider text-white shadow-[3px_3px_0px_#12131F] transition hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none`}
            style={{ backgroundColor: popPrimary }}
          >
            Book Now ⚡
          </button>
        </div>
      </header>

      {/* Bold Dynamic Hero */}
      <section className="mx-auto max-w-6xl px-6 py-12 lg:py-16">
        <div className="grid items-center gap-10 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-7">
            <div className="inline-flex items-center gap-2 rounded-full border-2 border-[#12131F] bg-[#FEF08A] px-3.5 py-1 text-xs font-extrabold uppercase tracking-wider text-[#12131F]">
              ★ Fresh Cuts · Bold Color · Zero Wait
            </div>
            <h1 className="text-4xl font-black leading-[1.05] tracking-tight text-[#12131F] sm:text-6xl">
              {data.headline || `Stand Out at ${data.business.display_name}`}
            </h1>
            <p className="max-w-xl text-sm font-medium leading-relaxed text-[#474B66]">
              {data.tagline ||
                data.business.description ||
                "Vibrant styling, trend-forward color, and instant booking built for busy city schedules."}
            </p>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => onBookClick?.()}
                className={`${radius} border-2 border-[#12131F] px-7 py-3.5 text-xs font-extrabold uppercase tracking-wider text-white shadow-[4px_4px_0px_#12131F] transition hover:brightness-110`}
                style={{ backgroundColor: popPrimary }}
              >
                Grab Your Slot
              </button>
              {data.show_services && (
                <a
                  href="#services"
                  className={`${radius} border-2 border-[#12131F] bg-white px-6 py-3.5 text-xs font-extrabold uppercase tracking-wider text-[#12131F] shadow-[4px_4px_0px_#12131F]`}
                >
                  See Prices
                </a>
              )}
            </div>
          </div>

          <div className="lg:col-span-5">
            <div
              className="overflow-hidden rounded-3xl border-2 border-[#12131F] bg-white p-2 shadow-[8px_8px_0px_#12131F]"
              style={{ backgroundColor: popSecondary }}
            >
              {data.cover_image_url ? (
                <img
                  src={data.cover_image_url}
                  alt={`${data.business.display_name} vibe`}
                  className="h-[300px] w-full rounded-2xl border-2 border-[#12131F] object-cover sm:h-[360px]"
                />
              ) : (
                <div
                  className="flex h-[300px] flex-col justify-between rounded-2xl border-2 border-[#12131F] p-6 text-white sm:h-[360px]"
                  style={{
                    background: `linear-gradient(135deg, ${popPrimary}, ${popSecondary})`,
                  }}
                >
                  <span className="inline-block w-fit rounded-full bg-black/30 px-3 py-1 text-[11px] font-bold uppercase">
                    {data.business.city || "CITY STUDIO"}
                  </span>
                  <div>
                    <p className="text-3xl font-black leading-tight">{data.business.display_name}</p>
                    <p className="mt-1 text-xs text-white/90">Instant Online & AI Voice Booking</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Snappy 3-Column Service Grid */}
      {data.show_services && (
        <section id="services" className="border-y-2 border-[#12131F] bg-white py-16">
          <div className="mx-auto max-w-6xl px-6">
            <div className="mb-10 flex flex-wrap items-center justify-between gap-4">
              <h2 className="text-3xl font-black tracking-tight sm:text-4xl">The Style Menu</h2>
              <span className="rounded-full border-2 border-[#12131F] bg-[#E0F2FE] px-4 py-1 text-xs font-extrabold uppercase">
                {data.services.length} Services Live
              </span>
            </div>

            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {data.services.length === 0 ? (
                <div className="col-span-full rounded-2xl border-2 border-[#12131F] bg-[#FAFAFF] p-8 text-center text-sm font-semibold">
                  Tap &ldquo;Book Now&rdquo; to check our latest studio services and drop-in specials.
                </div>
              ) : (
                data.services.map((svc) => (
                  <div
                    key={svc.id}
                    className="flex flex-col justify-between rounded-2xl border-2 border-[#12131F] bg-[#FAFAFF] p-5 shadow-[4px_4px_0px_#12131F] transition hover:-translate-y-0.5"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="rounded-md border border-[#12131F] bg-[#FEF08A] px-2 py-0.5 text-[10px] font-extrabold uppercase">
                          {svc.category || "Style"}
                        </span>
                        <span className="text-lg font-black" style={{ color: popPrimary }}>
                          {formatServicePrice(svc.price, svc.currency)}
                        </span>
                      </div>
                      <h3 className="mt-3 text-lg font-extrabold text-[#12131F]">{svc.name}</h3>
                      {svc.description && (
                        <p className="mt-1.5 text-xs text-[#474B66]">{svc.description}</p>
                      )}
                    </div>
                    <div className="mt-5 flex items-center justify-between border-t border-[#12131F]/15 pt-3">
                      <span className="text-xs font-bold text-[#474B66]">{svc.duration_minutes}m</span>
                      <button
                        type="button"
                        onClick={() => onBookClick?.(svc)}
                        className={`${radius} border-2 border-[#12131F] bg-white px-3.5 py-1.5 text-xs font-extrabold uppercase hover:bg-[#12131F] hover:text-white`}
                      >
                        Book →
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>
      )}

      {/* Hours & Location Strip */}
      <section className="mx-auto max-w-6xl px-6 py-14">
        <div className="grid gap-6 md:grid-cols-12">
          <div className="rounded-3xl border-2 border-[#12131F] bg-[#12131F] p-7 text-white md:col-span-5">
            <p className="text-xs font-bold uppercase tracking-widest text-[#FEF08A]">Find Us</p>
            <h2 className="mt-2 text-2xl font-black">{data.business.display_name}</h2>
            {fullAddress && <p className="mt-2 text-xs text-zinc-300">{fullAddress}</p>}
            {data.business.phone && <p className="mt-2 text-xs font-bold text-[#38BDF8]">{data.business.phone}</p>}
            {data.receptionist.enabled && (
              <p className="mt-4 rounded-xl bg-white/10 p-3 text-xs text-zinc-200">
                🤖 {data.receptionist.assistant_name || "AI Receptionist"}: {data.receptionist.greeting}
              </p>
            )}
          </div>
          {data.show_hours && (
            <div className="rounded-3xl border-2 border-[#12131F] bg-white p-7 md:col-span-7">
              <p className="text-xs font-extrabold uppercase tracking-wider text-[#474B66]">Studio Hours</p>
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                {data.hours.map((h) => (
                  <div key={h.weekday} className="rounded-xl border border-[#12131F]/15 bg-[#FAFAFF] p-3">
                    <p className="text-[11px] font-extrabold uppercase">{formatShortWeekday(h.weekday)}</p>
                    <p className="mt-1 text-xs font-semibold text-[#474B66]">{formatHourRange(h)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      <footer className="border-t-2 border-[#12131F] bg-[#FEF08A] px-6 py-6 text-xs font-bold text-[#12131F]">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
          <span>{data.business.display_name} · Powered by Svario</span>
          <div className="flex gap-4">
            {igHref && <a href={igHref} target="_blank" rel="noreferrer" className="underline">Instagram</a>}
            {fbHref && <a href={fbHref} target="_blank" rel="noreferrer" className="underline">Facebook</a>}
            {waHref && <a href={waHref} target="_blank" rel="noreferrer" className="underline">WhatsApp</a>}
          </div>
        </div>
      </footer>
    </div>
  );
}
