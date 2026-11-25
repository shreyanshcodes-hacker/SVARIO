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
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3.5 sm:gap-4 sm:px-6 sm:py-4">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            {data.logo_url ? (
              <img
                src={data.logo_url}
                alt={`${data.business.display_name} logo`}
                className="h-9 w-9 shrink-0 rounded-xl border-2 border-[#12131F] object-cover sm:h-10 sm:w-10"
              />
            ) : (
              <div
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border-2 border-[#12131F] text-xs font-black text-white sm:h-10 sm:w-10 sm:text-sm"
                style={{ backgroundColor: popPrimary }}
              >
                {data.business.display_name.slice(0, 2).toUpperCase()}
              </div>
            )}
            <span className="break-words text-base font-extrabold tracking-tight sm:text-lg">{data.business.display_name}</span>
          </div>

          <button
            type="button"
            onClick={() => onBookClick?.()}
            className={`${radius} min-h-[40px] shrink-0 border-2 border-[#12131F] px-3.5 py-2 text-xs font-extrabold uppercase tracking-wider text-white shadow-[3px_3px_0px_#12131F] transition hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none sm:px-5`}
            style={{ backgroundColor: popPrimary }}
          >
            Book Now ⚡
          </button>
        </div>
      </header>

      {/* Bold Dynamic Hero */}
      <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-12 lg:py-16">
        <div className="grid items-center gap-8 sm:gap-10 lg:grid-cols-12">
          <div className="min-w-0 space-y-5 sm:space-y-6 lg:col-span-7">
            <div className="inline-flex items-center gap-2 rounded-full border-2 border-[#12131F] bg-[#FEF08A] px-3.5 py-1 text-[11px] font-extrabold uppercase tracking-wider text-[#12131F] sm:text-xs">
              ★ Fresh Cuts · Bold Color · Zero Wait
            </div>
            <h1 className="break-words text-3xl font-black leading-[1.05] tracking-tight text-[#12131F] sm:text-5xl lg:text-6xl">
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
                className={`${radius} flex min-h-[44px] w-full items-center justify-center border-2 border-[#12131F] px-7 py-3.5 text-xs font-extrabold uppercase tracking-wider text-white shadow-[4px_4px_0px_#12131F] transition hover:brightness-110 sm:w-auto`}
                style={{ backgroundColor: popPrimary }}
              >
                Grab Your Slot
              </button>
              {data.show_services && (
                <a
                  href="#services"
                  className={`${radius} flex min-h-[44px] w-full items-center justify-center border-2 border-[#12131F] bg-white px-6 py-3.5 text-xs font-extrabold uppercase tracking-wider text-[#12131F] shadow-[4px_4px_0px_#12131F] sm:w-auto`}
                >
                  See Prices
                </a>
              )}
            </div>
          </div>

          <div className="min-w-0 lg:col-span-5">
            <div
              className="overflow-hidden rounded-3xl border-2 border-[#12131F] bg-white p-2 shadow-[5px_5px_0px_#12131F] sm:shadow-[8px_8px_0px_#12131F]"
              style={{ backgroundColor: popSecondary }}
            >
              {data.cover_image_url ? (
                <img
                  src={data.cover_image_url}
                  alt={`${data.business.display_name} vibe`}
                  className="h-[240px] w-full rounded-2xl border-2 border-[#12131F] object-cover sm:h-[300px] lg:h-[360px]"
                />
              ) : (
                <div
                  className="flex h-[240px] flex-col justify-between rounded-2xl border-2 border-[#12131F] p-5 text-white sm:h-[300px] sm:p-6 lg:h-[360px]"
                  style={{
                    background: `linear-gradient(135deg, ${popPrimary}, ${popSecondary})`,
                  }}
                >
                  <span className="inline-block w-fit rounded-full bg-black/30 px-3 py-1 text-[11px] font-bold uppercase">
                    {data.business.city || "CITY STUDIO"}
                  </span>
                  <div>
                    <p className="break-words text-2xl font-black leading-tight sm:text-3xl">{data.business.display_name}</p>
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
        <section id="services" className="border-y-2 border-[#12131F] bg-white py-12 sm:py-16">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mb-8 flex flex-wrap items-center justify-between gap-4 sm:mb-10">
              <h2 className="text-2xl font-black tracking-tight sm:text-3xl lg:text-4xl">The Style Menu</h2>
              <span className="rounded-full border-2 border-[#12131F] bg-[#E0F2FE] px-4 py-1 text-xs font-extrabold uppercase">
                {data.services.length} Services Live
              </span>
            </div>

            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {data.services.length === 0 ? (
                <div className="col-span-full rounded-2xl border-2 border-[#12131F] bg-[#FAFAFF] p-6 text-center text-sm font-semibold sm:p-8">
                  Tap &ldquo;Book Now&rdquo; to check our latest studio services and drop-in specials.
                </div>
              ) : (
                data.services.map((svc) => (
                  <div
                    key={svc.id}
                    className="flex min-w-0 flex-col justify-between rounded-2xl border-2 border-[#12131F] bg-[#FAFAFF] p-5 shadow-[4px_4px_0px_#12131F] transition hover:-translate-y-0.5"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="max-w-[65%] truncate rounded-md border border-[#12131F] bg-[#FEF08A] px-2 py-0.5 text-[10px] font-extrabold uppercase">
                          {svc.category || "Style"}
                        </span>
                        <span className="shrink-0 text-lg font-black" style={{ color: popPrimary }}>
                          {formatServicePrice(svc.price, svc.currency)}
                        </span>
                      </div>
                      <h3 className="mt-3 break-words text-lg font-extrabold text-[#12131F]">{svc.name}</h3>
                      {svc.description && (
                        <p className="mt-1.5 break-words text-xs text-[#474B66]">{svc.description}</p>
                      )}
                    </div>
                    <div className="mt-5 flex items-center justify-between gap-3 border-t border-[#12131F]/15 pt-3">
                      <span className="text-xs font-bold text-[#474B66]">{svc.duration_minutes}m</span>
                      <button
                        type="button"
                        onClick={() => onBookClick?.(svc)}
                        className={`${radius} min-h-[40px] shrink-0 border-2 border-[#12131F] bg-white px-3.5 py-1.5 text-xs font-extrabold uppercase hover:bg-[#12131F] hover:text-white`}
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
      <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
        <div className="grid gap-6 md:grid-cols-12">
          <div className="min-w-0 rounded-3xl border-2 border-[#12131F] bg-[#12131F] p-5 text-white sm:p-7 md:col-span-5">
            <p className="text-xs font-bold uppercase tracking-widest text-[#FEF08A]">Find Us</p>
            <h2 className="mt-2 break-words text-2xl font-black">{data.business.display_name}</h2>
            {fullAddress && <p className="mt-2 break-words text-xs text-zinc-300">{fullAddress}</p>}
            {data.business.phone && <p className="mt-2 text-xs font-bold text-[#38BDF8]">{data.business.phone}</p>}
            {data.receptionist.enabled && (
              <p className="mt-4 break-words rounded-xl bg-white/10 p-3 text-xs text-zinc-200">
                🤖 {data.receptionist.assistant_name || "AI Receptionist"}: {data.receptionist.greeting}
              </p>
            )}
          </div>
          {data.show_hours && (
            <div className="min-w-0 rounded-3xl border-2 border-[#12131F] bg-white p-5 sm:p-7 md:col-span-7">
              <p className="text-xs font-extrabold uppercase tracking-wider text-[#474B66]">Studio Hours</p>
              <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-3 sm:gap-3">
                {data.hours.map((h) => (
                  <div key={h.weekday} className="min-w-0 rounded-xl border border-[#12131F]/15 bg-[#FAFAFF] p-2.5 sm:p-3">
                    <p className="text-[11px] font-extrabold uppercase">{formatShortWeekday(h.weekday)}</p>
                    <p className="mt-1 break-words text-xs font-semibold text-[#474B66]">{formatHourRange(h)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      <footer className="border-t-2 border-[#12131F] bg-[#FEF08A] px-4 pt-6 pb-2 text-center text-xs font-bold text-[#12131F] sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-center gap-3">
          <span className="break-words">{data.business.display_name}</span>
          {(igHref || fbHref || waHref) && (
            <div className="flex flex-wrap justify-center gap-4">
              {igHref && <a href={igHref} target="_blank" rel="noreferrer" className="py-1 underline">Instagram</a>}
              {fbHref && <a href={fbHref} target="_blank" rel="noreferrer" className="py-1 underline">Facebook</a>}
              {waHref && <a href={waHref} target="_blank" rel="noreferrer" className="py-1 underline">WhatsApp</a>}
            </div>
          )}
        </div>
      </footer>
    </div>
  );
}
