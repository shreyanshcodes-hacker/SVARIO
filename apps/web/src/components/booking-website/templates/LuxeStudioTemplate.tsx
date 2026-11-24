"use client";

import React from "react";
import {
  formatFullAddress,
  formatHourRange,
  formatServicePrice,
  formatWeekdayName,
  getButtonRadiusClass,
  getFontFamilyStack,
  groupServicesByCategory,
  safeExternalHref,
  type TemplateComponentProps,
} from "../template-utils";

/**
 * Template 01 — Luxe Studio
 * Luxury black, gold, and ivory aesthetic with editorial framed hero,
 * serif display typography, 2-column atelier price ledger, and concierge booking strip.
 */
export function LuxeStudioTemplate({ data, onBookClick }: TemplateComponentProps): React.JSX.Element {
  const radius = getButtonRadiusClass(data.button_style);
  const categories = groupServicesByCategory(data.services);
  const fullAddress = formatFullAddress(data);
  const gold = "#D4AF37";
  const accent = data.accent_color || gold;

  const igHref = safeExternalHref(data.social_instagram, "instagram");
  const fbHref = safeExternalHref(data.social_facebook, "facebook");
  const waHref = safeExternalHref(data.social_whatsapp, "whatsapp");

  return (
    <div
      data-testid="template-luxe_studio"
      className="min-h-full bg-[#09090B] text-[#F8F5EE]"
      style={{ fontFamily: getFontFamilyStack(data.font_family) }}
    >
      {/* Top Gold-Bordered Atelier Header */}
      <header className="border-b border-[#D4AF37]/25 bg-[#09090B]/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div className="flex items-center gap-3.5">
            {data.logo_url ? (
              <img
                src={data.logo_url}
                alt={`${data.business.display_name} logo`}
                className="h-11 w-11 rounded-full border border-[#D4AF37]/50 object-cover"
              />
            ) : (
              <div className="flex h-11 w-11 items-center justify-center rounded-full border border-[#D4AF37]/60 bg-[#141310] font-serif text-lg tracking-widest text-[#D4AF37]">
                {data.business.display_name.slice(0, 1).toUpperCase()}
              </div>
            )}
            <div>
              <p className="font-serif text-lg tracking-[0.14em] uppercase text-[#F8F5EE]">
                {data.business.display_name}
              </p>
              {data.business.city && (
                <p className="text-[11px] tracking-[0.22em] uppercase text-[#D4AF37]/80">
                  {data.business.city} Atelier
                </p>
              )}
            </div>
          </div>

          <nav aria-label="Salon navigation" className="hidden items-center gap-7 text-xs tracking-[0.18em] uppercase text-[#C9C2B2] md:flex">
            {data.show_services && <a href="#services" className="transition hover:text-[#D4AF37]">Menu</a>}
            <a href="#about" className="transition hover:text-[#D4AF37]">Atelier</a>
            {data.show_hours && <a href="#hours" className="transition hover:text-[#D4AF37]">Hours</a>}
          </nav>

          <button
            type="button"
            onClick={() => onBookClick?.()}
            className={`${radius} border border-[#D4AF37] bg-[#D4AF37] px-5 py-2.5 text-xs font-semibold tracking-[0.14em] uppercase text-[#09090B] transition hover:brightness-110`}
            style={{ backgroundColor: accent, borderColor: accent }}
          >
            Reserve Appointment
          </button>
        </div>
      </header>

      {/* Split Luxury Editorial Hero */}
      <section className="mx-auto grid max-w-6xl items-center gap-10 px-6 py-14 lg:grid-cols-12 lg:py-20">
        <div className="space-y-6 lg:col-span-6">
          <div className="inline-flex items-center gap-2 border-b border-[#D4AF37]/50 pb-1 text-[11px] tracking-[0.25em] uppercase text-[#D4AF37]">
            Private Salon Experience
          </div>
          <h1 className="font-serif text-4xl font-normal leading-[1.12] tracking-tight text-[#F8F5EE] sm:text-5xl">
            {data.headline || `Bespoke Hair & Beauty at ${data.business.display_name}`}
          </h1>
          <p className="max-w-lg text-sm leading-relaxed text-[#C9C2B2]">
            {data.tagline ||
              data.business.description ||
              "An intimate luxury studio dedicated to tailored artistry, luminous care, and unhurried elegance."}
          </p>
          <div className="flex flex-wrap items-center gap-4 pt-2">
            <button
              type="button"
              onClick={() => onBookClick?.()}
              className={`${radius} px-7 py-3.5 text-xs font-semibold tracking-[0.16em] uppercase text-[#09090B] shadow-lg transition hover:brightness-110`}
              style={{ backgroundColor: accent }}
            >
              Book Your Ritual
            </button>
            {data.business.phone && (
              <a
                href={`tel:${data.business.phone}`}
                className="text-xs tracking-[0.16em] uppercase text-[#D4AF37] underline underline-offset-4 hover:text-[#F8F5EE]"
              >
                Concierge: {data.business.phone}
              </a>
            )}
          </div>
        </div>

        <div className="lg:col-span-6">
          <div className="relative p-3 border border-[#D4AF37]/35 bg-[#12110E]">
            {data.cover_image_url ? (
              <img
                src={data.cover_image_url}
                alt={`${data.business.display_name} studio`}
                className="h-[320px] w-full object-cover sm:h-[420px]"
              />
            ) : (
              <div
                className="flex h-[320px] w-full flex-col items-center justify-center p-8 text-center sm:h-[420px]"
                style={{
                  background:
                    "radial-gradient(circle at 30% 20%, rgba(212,175,55,0.22), rgba(15,14,12,0.96) 70%)",
                }}
              >
                <span className="font-serif text-5xl text-[#D4AF37]/70">✦</span>
                <p className="mt-4 font-serif text-xl tracking-[0.12em] uppercase text-[#F8F5EE]">
                  {data.business.display_name}
                </p>
                <p className="mt-2 text-xs tracking-[0.2em] uppercase text-[#C9C2B2]">
                  Signature Craftsmanship
                </p>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Atelier Service Menu Ledger */}
      {data.show_services && (
        <section id="services" className="border-t border-[#D4AF37]/20 bg-[#0E0D0B] py-16">
          <div className="mx-auto max-w-6xl px-6">
            <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-[11px] tracking-[0.26em] uppercase text-[#D4AF37]">Curated Menu</p>
                <h2 className="mt-2 font-serif text-3xl text-[#F8F5EE]">Signature Treatments</h2>
              </div>
              <p className="text-xs text-[#A9A292]">All appointments include a personalized consultation.</p>
            </div>

            {categories.length === 0 ? (
              <div className="border border-[#D4AF37]/25 bg-[#141310] p-8 text-center text-sm text-[#C9C2B2]">
                Our bespoke service menu is being curated. Contact our concierge to reserve your treatment.
              </div>
            ) : (
              <div className="space-y-12">
                {categories.map((group) => (
                  <div key={group.category}>
                    <h3 className="mb-5 border-b border-[#D4AF37]/25 pb-2 text-xs font-semibold tracking-[0.22em] uppercase text-[#D4AF37]">
                      {group.category}
                    </h3>
                    <div className="grid gap-6 md:grid-cols-2">
                      {group.items.map((svc) => (
                        <div
                          key={svc.id}
                          className="group flex flex-col justify-between border border-[#D4AF37]/20 bg-[#13120F] p-5 transition hover:border-[#D4AF37]/60"
                        >
                          <div>
                            <div className="flex items-baseline justify-between gap-3">
                              <h4 className="font-serif text-lg text-[#F8F5EE]">{svc.name}</h4>
                              <span className="font-serif text-base text-[#D4AF37]">
                                {formatServicePrice(svc.price, svc.currency)}
                              </span>
                            </div>
                            {svc.description && (
                              <p className="mt-2 text-xs leading-relaxed text-[#A9A292]">{svc.description}</p>
                            )}
                          </div>
                          <div className="mt-4 flex items-center justify-between border-t border-white/5 pt-3">
                            <span className="text-[11px] tracking-[0.14em] uppercase text-[#A9A292]">
                              {svc.duration_minutes} mins
                            </span>
                            <button
                              type="button"
                              onClick={() => onBookClick?.(svc)}
                              className="text-xs font-semibold tracking-[0.14em] uppercase text-[#D4AF37] transition hover:text-[#F8F5EE]"
                            >
                              Reserve →
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      )}

      {/* About, Hours & AI Concierge */}
      <section id="about" className="border-t border-[#D4AF37]/20 py-16">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 lg:grid-cols-12">
          <div className="space-y-4 lg:col-span-7">
            <p className="text-[11px] tracking-[0.25em] uppercase text-[#D4AF37]">The Atelier</p>
            <h2 className="font-serif text-3xl text-[#F8F5EE]">Crafted Around You</h2>
            <p className="text-sm leading-relaxed text-[#C9C2B2]">
              {data.business.description ||
                `${data.business.display_name} pairs master stylists with serene luxury so every appointment feels restorative and effortless.`}
            </p>
            {data.receptionist.enabled && (
              <div className="mt-6 border border-[#D4AF37]/30 bg-[#141310] p-5">
                <p className="text-[11px] tracking-[0.2em] uppercase text-[#D4AF37]">
                  24/7 AI Salon Concierge · {data.receptionist.assistant_name || "Svario Concierge"}
                </p>
                <p className="mt-2 text-xs text-[#E4DEC9]">
                  {data.receptionist.greeting || "Ask about services, pricing, or reserve your appointment instantly."}
                </p>
                <button
                  type="button"
                  onClick={() => onBookClick?.()}
                  className={`${radius} mt-4 border border-[#D4AF37]/70 px-4 py-2 text-xs font-semibold tracking-[0.12em] uppercase text-[#D4AF37] hover:bg-[#D4AF37] hover:text-[#09090B]`}
                >
                  Request Instant Booking
                </button>
              </div>
            )}
          </div>

          {data.show_hours && (
            <div id="hours" className="border border-[#D4AF37]/25 bg-[#12110E] p-6 lg:col-span-5">
              <p className="text-[11px] tracking-[0.22em] uppercase text-[#D4AF37]">Salon Hours</p>
              <ul className="mt-4 space-y-2.5 text-xs">
                {data.hours.length === 0 ? (
                  <li className="text-[#A9A292]">By appointment — contact salon for hours.</li>
                ) : (
                  data.hours.map((h) => (
                    <li
                      key={h.weekday}
                      className="flex items-center justify-between border-b border-white/5 pb-2 last:border-b-0"
                    >
                      <span className="text-[#C9C2B2]">{formatWeekdayName(h.weekday)}</span>
                      <span className="font-mono text-[#F8F5EE]">{formatHourRange(h)}</span>
                    </li>
                  ))
                )}
              </ul>
              {fullAddress && (
                <p className="mt-5 border-t border-[#D4AF37]/20 pt-4 text-xs text-[#A9A292]">
                  {fullAddress}
                </p>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Luxury Footer */}
      <footer className="border-t border-[#D4AF37]/20 bg-[#070708] py-8 text-xs text-[#A9A292]">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6">
          <div>
            <p className="font-serif text-sm tracking-[0.14em] uppercase text-[#F8F5EE]">
              {data.business.display_name}
            </p>
            <p className="mt-1 text-[11px]">
              {[data.business.phone, data.business.email].filter(Boolean).join(" · ") || "Powered by Svario"}
            </p>
          </div>
          <div className="flex items-center gap-4">
            {igHref && <a href={igHref} target="_blank" rel="noreferrer" className="hover:text-[#D4AF37]">Instagram</a>}
            {fbHref && <a href={fbHref} target="_blank" rel="noreferrer" className="hover:text-[#D4AF37]">Facebook</a>}
            {waHref && <a href={waHref} target="_blank" rel="noreferrer" className="hover:text-[#D4AF37]">WhatsApp</a>}
          </div>
        </div>
      </footer>
    </div>
  );
}
