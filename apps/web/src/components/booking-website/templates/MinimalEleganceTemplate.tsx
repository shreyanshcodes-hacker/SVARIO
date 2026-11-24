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
 * Template 02 — Minimal Elegance
 * White, cream, and warm beige Nordic-minimalist layout with centered header,
 * generous whitespace, numbered vertical service index, and understated hairline dividers.
 */
export function MinimalEleganceTemplate({ data, onBookClick }: TemplateComponentProps): React.JSX.Element {
  const radius = getButtonRadiusClass(data.button_style);
  const categories = groupServicesByCategory(data.services);
  const fullAddress = formatFullAddress(data);
  const igHref = safeExternalHref(data.social_instagram, "instagram");
  const fbHref = safeExternalHref(data.social_facebook, "facebook");
  const waHref = safeExternalHref(data.social_whatsapp, "whatsapp");

  return (
    <div
      data-testid="template-minimal_elegance"
      className="min-h-full bg-[#FAF8F4] text-[#22201C]"
      style={{ fontFamily: getFontFamilyStack(data.font_family) }}
    >
      {/* Centered Minimal Header */}
      <header className="border-b border-[#E7E1D6] bg-[#FAF8F4]/95">
        <div className="mx-auto flex max-w-5xl flex-col items-center gap-4 px-6 py-7 text-center">
          <div className="flex items-center gap-3">
            {data.logo_url && (
              <img
                src={data.logo_url}
                alt={`${data.business.display_name} logo`}
                className="h-9 w-9 rounded-full border border-[#DDD5C7] object-cover"
              />
            )}
            <span className="text-xl font-light tracking-[0.22em] uppercase text-[#1F1D1A]">
              {data.business.display_name}
            </span>
          </div>
          <nav aria-label="Salon navigation" className="flex flex-wrap items-center justify-center gap-7 text-xs tracking-[0.14em] uppercase text-[#6E685D]">
            {data.show_services && <a href="#services" className="hover:text-[#1F1D1A]">Services</a>}
            <a href="#about" className="hover:text-[#1F1D1A]">Philosophy</a>
            {data.show_hours && <a href="#hours" className="hover:text-[#1F1D1A]">Hours</a>}
            <button
              type="button"
              onClick={() => onBookClick?.()}
              className="border-b border-[#22201C] pb-0.5 font-medium text-[#22201C]"
            >
              Book Now
            </button>
          </nav>
        </div>
      </header>

      {/* Airy Centered Hero + Wide Architectural Frame */}
      <section className="mx-auto max-w-4xl px-6 py-16 text-center">
        <p className="text-[11px] tracking-[0.26em] uppercase text-[#8A8275]">
          {data.business.city ? `${data.business.city} · ` : ""}Modern Salon Studio
        </p>
        <h1 className="mx-auto mt-4 max-w-2xl text-4xl font-light leading-[1.18] tracking-tight text-[#1E1C19] sm:text-5xl">
          {data.headline || `Quiet Luxury, Effortless Beauty.`}
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-sm leading-relaxed text-[#6E685D]">
          {data.tagline ||
            data.business.description ||
            "Thoughtful hair and skin rituals in a calm, sunlit space designed around your rhythm."}
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <button
            type="button"
            onClick={() => onBookClick?.()}
            className={`${radius} bg-[#22201C] px-7 py-3 text-xs font-medium tracking-[0.16em] uppercase text-[#FAF8F4] transition hover:bg-[#3A362E]`}
          >
            Schedule Appointment
          </button>
          {data.show_services && (
            <a
              href="#services"
              className={`${radius} border border-[#D4CBB9] px-6 py-3 text-xs font-medium tracking-[0.14em] uppercase text-[#4B463E] hover:border-[#22201C]`}
            >
              Explore Menu
            </a>
          )}
        </div>

        <div className="mt-12 overflow-hidden rounded-2xl border border-[#E7E1D6] bg-[#F1ECE3]">
          {data.cover_image_url ? (
            <img
              src={data.cover_image_url}
              alt={`${data.business.display_name} interior`}
              className="h-[280px] w-full object-cover sm:h-[400px]"
            />
          ) : (
            <div className="flex h-[240px] flex-col items-center justify-center bg-gradient-to-b from-[#F3EFE6] to-[#EAE3D5] px-6 sm:h-[320px]">
              <p className="text-xs tracking-[0.28em] uppercase text-[#8A8275]">Simplicity & Care</p>
              <p className="mt-2 text-2xl font-light text-[#2A2722]">{data.business.display_name}</p>
            </div>
          )}
        </div>
      </section>

      {/* Numbered Minimal Vertical Service Index */}
      {data.show_services && (
        <section id="services" className="border-t border-[#E7E1D6] bg-white py-16">
          <div className="mx-auto max-w-4xl px-6">
            <div className="mb-10 text-center">
              <p className="text-[11px] tracking-[0.25em] uppercase text-[#8A8275]">Menu</p>
              <h2 className="mt-2 text-3xl font-light text-[#1E1C19]">Services & Pricing</h2>
            </div>

            {categories.length === 0 ? (
              <p className="text-center text-sm text-[#6E685D]">
                Service menu coming soon. Reach out directly to schedule your visit.
              </p>
            ) : (
              <div className="space-y-12">
                {categories.map((group) => (
                  <div key={group.category}>
                    <h3 className="mb-4 text-xs font-medium tracking-[0.2em] uppercase text-[#8A8275]">
                      {group.category}
                    </h3>
                    <div className="divide-y divide-[#ECE7DD] border-y border-[#ECE7DD]">
                      {group.items.map((svc, idx) => (
                        <div
                          key={svc.id}
                          className="flex flex-col gap-3 py-5 sm:flex-row sm:items-center sm:justify-between"
                        >
                          <div className="flex items-start gap-4">
                            <span className="mt-0.5 font-mono text-xs text-[#A39A8B]">
                              {String(idx + 1).padStart(2, "0")}
                            </span>
                            <div>
                              <h4 className="text-base font-medium text-[#1E1C19]">{svc.name}</h4>
                              {svc.description && (
                                <p className="mt-1 text-xs text-[#6E685D]">{svc.description}</p>
                              )}
                              <p className="mt-1 text-[11px] text-[#9A9284]">{svc.duration_minutes} minutes</p>
                            </div>
                          </div>
                          <div className="flex items-center justify-between gap-5 sm:justify-end">
                            <span className="text-sm font-medium text-[#1E1C19]">
                              {formatServicePrice(svc.price, svc.currency)}
                            </span>
                            <button
                              type="button"
                              onClick={() => onBookClick?.(svc)}
                              className={`${radius} border border-[#D4CBB9] px-4 py-1.5 text-xs text-[#22201C] transition hover:bg-[#22201C] hover:text-white`}
                            >
                              Select
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

      {/* Calm Two-Column Philosophy & Hours */}
      <section id="about" className="border-t border-[#E7E1D6] bg-[#FAF8F4] py-16">
        <div className="mx-auto grid max-w-4xl gap-12 px-6 md:grid-cols-2">
          <div className="space-y-4">
            <p className="text-[11px] tracking-[0.22em] uppercase text-[#8A8275]">Our Space</p>
            <h2 className="text-2xl font-light text-[#1E1C19]">{data.business.display_name}</h2>
            <p className="text-sm leading-relaxed text-[#6E685D]">
              {data.business.description ||
                "Clean formulations, unhurried appointments, and personalized care tailored to your natural beauty."}
            </p>
            {fullAddress && <p className="text-xs text-[#59544A]">{fullAddress}</p>}
            {data.receptionist.enabled && (
              <div className="rounded-xl border border-[#E4DDD0] bg-white p-4 text-xs text-[#59544A]">
                <p className="font-medium text-[#1E1C19]">
                  AI Assistant · {data.receptionist.assistant_name || "Salon Receptionist"}
                </p>
                <p className="mt-1">{data.receptionist.greeting || "Available anytime to help you book."}</p>
              </div>
            )}
          </div>

          {data.show_hours && (
            <div id="hours" className="space-y-3">
              <p className="text-[11px] tracking-[0.22em] uppercase text-[#8A8275]">Hours</p>
              <div className="divide-y divide-[#E7E1D6] border-y border-[#E7E1D6]">
                {data.hours.map((h) => (
                  <div key={h.weekday} className="flex justify-between py-2.5 text-xs">
                    <span className="text-[#59544A]">{formatWeekdayName(h.weekday)}</span>
                    <span className="text-[#1E1C19]">{formatHourRange(h)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      <footer className="border-t border-[#E7E1D6] bg-[#F4EFE6] py-8 text-center text-xs text-[#6E685D]">
        <p className="tracking-[0.16em] uppercase text-[#1E1C19]">{data.business.display_name}</p>
        <p className="mt-1.5">
          {[data.business.phone, data.business.email].filter(Boolean).join(" · ") || "Online Booking via Svario"}
        </p>
        {(igHref || fbHref || waHref) && (
          <div className="mt-3 flex justify-center gap-5">
            {igHref && <a href={igHref} target="_blank" rel="noreferrer" className="underline">Instagram</a>}
            {fbHref && <a href={fbHref} target="_blank" rel="noreferrer" className="underline">Facebook</a>}
            {waHref && <a href={waHref} target="_blank" rel="noreferrer" className="underline">WhatsApp</a>}
          </div>
        )}
      </footer>
    </div>
  );
}
