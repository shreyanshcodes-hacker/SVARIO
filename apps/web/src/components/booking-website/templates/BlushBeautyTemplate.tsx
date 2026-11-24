"use client";

import React, { useState } from "react";
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
 * Template 03 — Blush Beauty
 * Blush pink, rose, and warm ivory palette with arched image-led hero,
 * interactive category pills, and soft elevated treatment cards.
 */
export function BlushBeautyTemplate({ data, onBookClick }: TemplateComponentProps): React.JSX.Element {
  const radius = getButtonRadiusClass(data.button_style);
  const categories = groupServicesByCategory(data.services);
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const fullAddress = formatFullAddress(data);
  const roseAccent = "#C96B84";

  const visibleServices =
    selectedCategory === "All"
      ? data.services
      : data.services.filter((s) => (s.category || "Signature Services") === selectedCategory);

  const igHref = safeExternalHref(data.social_instagram, "instagram");
  const fbHref = safeExternalHref(data.social_facebook, "facebook");
  const waHref = safeExternalHref(data.social_whatsapp, "whatsapp");

  return (
    <div
      data-testid="template-blush_beauty"
      className="min-h-full bg-[#FFF7F9] text-[#3B2630]"
      style={{ fontFamily: getFontFamilyStack(data.font_family) }}
    >
      {/* Soft Rose Floating Header */}
      <header className="sticky top-0 z-10 border-b border-[#F3D8E0] bg-[#FFF7F9]/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
          <div className="flex items-center gap-3">
            {data.logo_url ? (
              <img
                src={data.logo_url}
                alt={`${data.business.display_name} logo`}
                className="h-10 w-10 rounded-full border-2 border-[#EAB8C7] object-cover"
              />
            ) : (
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#F7DCE4] font-serif text-lg text-[#9D3F59]">
                {data.business.display_name.slice(0, 1).toUpperCase()}
              </div>
            )}
            <span className="font-serif text-xl font-semibold text-[#3B2630]">
              {data.business.display_name}
            </span>
          </div>

          <div className="flex items-center gap-5 text-xs font-medium text-[#7D5665]">
            {data.show_services && <a href="#services" className="hidden sm:inline hover:text-[#9D3F59]">Treatments</a>}
            {data.show_hours && <a href="#hours" className="hidden sm:inline hover:text-[#9D3F59]">Visit Us</a>}
            <button
              type="button"
              onClick={() => onBookClick?.()}
              className={`${radius} bg-[#C96B84] px-5 py-2.5 text-xs font-semibold text-white shadow-sm transition hover:bg-[#B2566F]`}
              style={{ backgroundColor: roseAccent }}
            >
              Book Now
            </button>
          </div>
        </div>
      </header>

      {/* Arched Image-Led Hero */}
      <section className="mx-auto grid max-w-6xl items-center gap-10 px-6 py-12 lg:grid-cols-12 lg:py-16">
        <div className="order-2 space-y-5 lg:order-1 lg:col-span-6">
          <span className="inline-block rounded-full bg-[#FBE5EC] px-4 py-1.5 text-xs font-medium text-[#9D3F59]">
            ✿ Beauty & Self-Care Sanctuary
          </span>
          <h1 className="font-serif text-4xl font-semibold leading-tight text-[#3B2630] sm:text-5xl">
            {data.headline || `Glow Softly at ${data.business.display_name}`}
          </h1>
          <p className="max-w-lg text-sm leading-relaxed text-[#7D5665]">
            {data.tagline ||
              data.business.description ||
              "Radiant hair, luminous skin, and pampering nail rituals crafted with gentle care."}
          </p>
          <div className="flex flex-wrap gap-3 pt-2">
            <button
              type="button"
              onClick={() => onBookClick?.()}
              className={`${radius} bg-[#C96B84] px-7 py-3.5 text-xs font-semibold text-white shadow-md shadow-[#C96B84]/25 transition hover:brightness-105`}
            >
              Reserve Your Appointment
            </button>
            {data.business.phone && (
              <a
                href={`tel:${data.business.phone}`}
                className={`${radius} border border-[#EAB8C7] bg-white px-5 py-3.5 text-xs font-semibold text-[#9D3F59]`}
              >
                Call {data.business.phone}
              </a>
            )}
          </div>
        </div>

        <div className="order-1 flex justify-center lg:order-2 lg:col-span-6">
          <div className="w-full max-w-md overflow-hidden rounded-t-[180px] rounded-b-3xl border-4 border-white bg-[#FBE5EC] shadow-xl shadow-[#C96B84]/15">
            {data.cover_image_url ? (
              <img
                src={data.cover_image_url}
                alt={`${data.business.display_name} showcase`}
                className="h-[340px] w-full object-cover sm:h-[420px]"
              />
            ) : (
              <div className="flex h-[340px] flex-col items-center justify-center bg-gradient-to-b from-[#FCE4EC] via-[#F9D5E2] to-[#F4C2D3] p-8 text-center sm:h-[420px]">
                <span className="text-4xl text-[#9D3F59]">❀</span>
                <p className="mt-4 font-serif text-2xl text-[#3B2630]">{data.business.display_name}</p>
                <p className="mt-2 text-xs text-[#7D5665]">Curated Salon & Skincare</p>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Filterable Rose Service Cards */}
      {data.show_services && (
        <section id="services" className="bg-white py-16">
          <div className="mx-auto max-w-6xl px-6">
            <div className="text-center">
              <p className="text-xs font-semibold tracking-[0.18em] uppercase text-[#C96B84]">
                Treatment Menu
              </p>
              <h2 className="mt-2 font-serif text-3xl font-semibold text-[#3B2630]">
                Pamper Yourself
              </h2>
            </div>

            {categories.length > 1 && (
              <div className="mt-7 flex flex-wrap justify-center gap-2">
                {["All", ...categories.map((c) => c.category)].map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setSelectedCategory(cat)}
                    className={`rounded-full px-4 py-1.5 text-xs font-medium transition ${
                      selectedCategory === cat
                        ? "bg-[#C96B84] text-white shadow-sm"
                        : "bg-[#FFF2F6] text-[#7D5665] hover:bg-[#FBE5EC]"
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            )}

            <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {visibleServices.length === 0 ? (
                <div className="col-span-full rounded-2xl border border-[#F3D8E0] bg-[#FFF7F9] p-8 text-center text-sm text-[#7D5665]">
                  Ask our salon team about our full list of signature beauty services.
                </div>
              ) : (
                visibleServices.map((svc) => (
                  <div
                    key={svc.id}
                    className="flex flex-col justify-between rounded-3xl border border-[#F4DCE4] bg-[#FFF9FB] p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2">
                        <span className="rounded-full bg-[#FBE5EC] px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[#9D3F59]">
                          {svc.category || "Beauty"}
                        </span>
                        <span className="font-serif text-lg font-semibold text-[#9D3F59]">
                          {formatServicePrice(svc.price, svc.currency)}
                        </span>
                      </div>
                      <h3 className="mt-3 font-serif text-lg font-semibold text-[#3B2630]">{svc.name}</h3>
                      {svc.description && (
                        <p className="mt-1.5 text-xs leading-relaxed text-[#7D5665]">{svc.description}</p>
                      )}
                    </div>
                    <div className="mt-5 flex items-center justify-between border-t border-[#F4DCE4] pt-3">
                      <span className="text-xs text-[#8E6776]">{svc.duration_minutes} min</span>
                      <button
                        type="button"
                        onClick={() => onBookClick?.(svc)}
                        className={`${radius} bg-[#FBE5EC] px-3.5 py-1.5 text-xs font-semibold text-[#9D3F59] transition hover:bg-[#C96B84] hover:text-white`}
                      >
                        Book
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>
      )}

      {/* Hours & Concierge Banner */}
      <section id="hours" className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid gap-6 rounded-3xl border border-[#F3D8E0] bg-white p-8 shadow-sm md:grid-cols-2">
          <div className="space-y-3">
            <h2 className="font-serif text-2xl font-semibold text-[#3B2630]">Visit {data.business.display_name}</h2>
            <p className="text-sm text-[#7D5665]">
              {data.business.description || "We can't wait to welcome you for your next beauty appointment."}
            </p>
            {fullAddress && <p className="text-xs font-medium text-[#5E3E4B]">{fullAddress}</p>}
            {data.receptionist.enabled && (
              <div className="mt-4 rounded-2xl bg-[#FFF2F6] p-4 text-xs text-[#7D5665]">
                <p className="font-semibold text-[#9D3F59]">
                  AI Receptionist · {data.receptionist.assistant_name || "Svario"}
                </p>
                <p className="mt-1">{data.receptionist.greeting}</p>
              </div>
            )}
          </div>
          {data.show_hours && (
            <div className="space-y-2 text-xs">
              <p className="font-semibold uppercase tracking-wider text-[#C96B84]">Opening Hours</p>
              {data.hours.map((h) => (
                <div key={h.weekday} className="flex justify-between border-b border-[#F7E5EB] py-1.5">
                  <span className="text-[#7D5665]">{formatWeekdayName(h.weekday)}</span>
                  <span className="font-medium text-[#3B2630]">{formatHourRange(h)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <footer className="border-t border-[#F3D8E0] bg-[#FCEEF3] py-8 text-center text-xs text-[#7D5665]">
        <p className="font-serif text-base font-semibold text-[#3B2630]">{data.business.display_name}</p>
        <div className="mt-2 flex flex-wrap justify-center gap-4">
          {data.business.phone && <span>{data.business.phone}</span>}
          {data.business.email && <span>{data.business.email}</span>}
          {igHref && <a href={igHref} target="_blank" rel="noreferrer" className="font-medium text-[#9D3F59]">Instagram</a>}
          {fbHref && <a href={fbHref} target="_blank" rel="noreferrer" className="font-medium text-[#9D3F59]">Facebook</a>}
          {waHref && <a href={waHref} target="_blank" rel="noreferrer" className="font-medium text-[#9D3F59]">WhatsApp</a>}
        </div>
      </footer>
    </div>
  );
}
