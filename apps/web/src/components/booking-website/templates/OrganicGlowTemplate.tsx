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
 * Template 05 — Organic Glow
 * Earthy sage green, warm cream, and terracotta botanical wellness spa layout
 * with soft organic cards, calm ritual groupings, and sanctuary visit card.
 */
export function OrganicGlowTemplate({ data, onBookClick }: TemplateComponentProps): React.JSX.Element {
  const radius = getButtonRadiusClass(data.button_style);
  const categories = groupServicesByCategory(data.services);
  const fullAddress = formatFullAddress(data);
  const igHref = safeExternalHref(data.social_instagram, "instagram");
  const fbHref = safeExternalHref(data.social_facebook, "facebook");
  const waHref = safeExternalHref(data.social_whatsapp, "whatsapp");

  return (
    <div
      data-testid="template-organic_glow"
      className="min-h-full bg-[#F5F3EC] text-[#243228]"
      style={{ fontFamily: getFontFamilyStack(data.font_family) }}
    >
      {/* Botanical Pill Header */}
      <header className="px-4 pt-5 sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 rounded-3xl border border-[#DCE2D4] bg-[#FCFBF7] px-6 py-4 shadow-sm">
          <div className="flex items-center gap-3">
            {data.logo_url ? (
              <img
                src={data.logo_url}
                alt={`${data.business.display_name} logo`}
                className="h-10 w-10 rounded-2xl object-cover"
              />
            ) : (
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#E3ECDC] text-lg text-[#3D5A45]">
                🌿
              </div>
            )}
            <div>
              <p className="text-base font-semibold text-[#243228]">{data.business.display_name}</p>
              <p className="text-[11px] text-[#5C7061]">Holistic Salon & Skin Rituals</p>
            </div>
          </div>

          <div className="flex items-center gap-5 text-xs font-medium text-[#4D6152]">
            {data.show_services && <a href="#rituals" className="hidden md:inline hover:text-[#243228]">Rituals</a>}
            {data.show_hours && <a href="#sanctuary" className="hidden md:inline hover:text-[#243228]">Sanctuary</a>}
            <button
              type="button"
              onClick={() => onBookClick?.()}
              className={`${radius} bg-[#3D5A45] px-5 py-2.5 text-xs font-semibold text-[#F9F8F3] transition hover:bg-[#2F4736]`}
            >
              Book a Ritual
            </button>
          </div>
        </div>
      </header>

      {/* Organic Curved Wellness Hero */}
      <section className="mx-auto max-w-6xl px-6 py-12">
        <div className="grid items-center gap-8 rounded-[36px] bg-[#E9EFE3] p-8 sm:p-12 lg:grid-cols-12">
          <div className="space-y-5 lg:col-span-6">
            <span className="inline-flex items-center gap-2 rounded-full bg-[#FCFBF7] px-3.5 py-1 text-xs font-medium text-[#3D5A45]">
              <span>●</span> Mindful Beauty · Botanical Care
            </span>
            <h1 className="font-serif text-4xl leading-[1.15] text-[#1F2D23] sm:text-5xl">
              {data.headline || `Restore Your Natural Radiance`}
            </h1>
            <p className="text-sm leading-relaxed text-[#4C5F51]">
              {data.tagline ||
                data.business.description ||
                "Gentle, nature-inspired hair and skincare rituals designed to nourish body and mind."}
            </p>
            <div className="flex flex-wrap gap-3 pt-2">
              <button
                type="button"
                onClick={() => onBookClick?.()}
                className={`${radius} bg-[#3D5A45] px-6 py-3 text-xs font-semibold text-[#FCFBF7] shadow-sm hover:bg-[#2F4736]`}
              >
                Schedule Your Visit
              </button>
              <a
                href="#rituals"
                className={`${radius} border border-[#B9C8B2] bg-[#FCFBF7] px-5 py-3 text-xs font-semibold text-[#3D5A45]`}
              >
                View Treatments
              </a>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="overflow-hidden rounded-[28px] border-4 border-[#FCFBF7] bg-[#DCE6D5] shadow-md">
              {data.cover_image_url ? (
                <img
                  src={data.cover_image_url}
                  alt={`${data.business.display_name} sanctuary`}
                  className="h-[300px] w-full object-cover sm:h-[380px]"
                />
              ) : (
                <div className="flex h-[300px] flex-col items-center justify-center bg-gradient-to-br from-[#DCE7D5] to-[#C6D8BE] p-8 text-center sm:h-[380px]">
                  <span className="text-4xl">🍃</span>
                  <p className="mt-3 font-serif text-2xl text-[#243228]">{data.business.display_name}</p>
                  <p className="mt-1 text-xs text-[#4C5F51]">Calm · Botanical · Unhurried</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Rituals Section */}
      {data.show_services && (
        <section id="rituals" className="mx-auto max-w-6xl px-6 py-12">
          <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#5B7761]">
                Wellness Menu
              </p>
              <h2 className="mt-1 font-serif text-3xl text-[#1F2D23]">Botanical Treatments</h2>
            </div>
            <span className="rounded-full bg-[#E9EFE3] px-3.5 py-1 text-xs text-[#3D5A45]">
              {data.services.length} curated services
            </span>
          </div>

          <div className="space-y-10">
            {categories.length === 0 ? (
              <div className="rounded-3xl border border-[#DCE2D4] bg-[#FCFBF7] p-8 text-center text-sm text-[#4C5F51]">
                Contact us to discover our seasonal organic treatments.
              </div>
            ) : (
              categories.map((group) => (
                <div key={group.category} className="space-y-4">
                  <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7D6652]">
                    {group.category}
                  </h3>
                  <div className="grid gap-4 md:grid-cols-2">
                    {group.items.map((svc) => (
                      <div
                        key={svc.id}
                        className="flex flex-col justify-between rounded-3xl border border-[#DFE5D8] bg-[#FCFBF7] p-6 transition hover:border-[#8BA68D]"
                      >
                        <div>
                          <div className="flex items-start justify-between gap-3">
                            <h4 className="font-serif text-xl text-[#1F2D23]">{svc.name}</h4>
                            <span className="rounded-full bg-[#E9EFE3] px-3 py-1 text-xs font-semibold text-[#2E4635]">
                              {formatServicePrice(svc.price, svc.currency)}
                            </span>
                          </div>
                          {svc.description && (
                            <p className="mt-2 text-xs leading-relaxed text-[#5C7061]">{svc.description}</p>
                          )}
                        </div>
                        <div className="mt-5 flex items-center justify-between border-t border-[#ECEFE7] pt-3">
                          <span className="text-xs text-[#7D6652]">⏱ {svc.duration_minutes} mins</span>
                          <button
                            type="button"
                            onClick={() => onBookClick?.(svc)}
                            className={`${radius} bg-[#3D5A45]/10 px-4 py-1.5 text-xs font-semibold text-[#3D5A45] transition hover:bg-[#3D5A45] hover:text-white`}
                          >
                            Book Ritual
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      )}

      {/* Sanctuary Location & Hours */}
      <section id="sanctuary" className="mx-auto max-w-6xl px-6 py-12">
        <div className="grid gap-6 rounded-[32px] border border-[#DCE2D4] bg-[#FCFBF7] p-8 md:grid-cols-2">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#5B7761]">Our Sanctuary</p>
            <h2 className="font-serif text-2xl text-[#1F2D23]">{data.business.display_name}</h2>
            <p className="text-sm leading-relaxed text-[#4C5F51]">
              {data.business.description || "A serene retreat for holistic hair, skin, and self-care."}
            </p>
            {fullAddress && <p className="text-xs font-medium text-[#3D5A45]">📍 {fullAddress}</p>}
            {data.receptionist.enabled && (
              <div className="mt-3 rounded-2xl bg-[#E9EFE3] p-4 text-xs text-[#2F4736]">
                <p className="font-semibold">
                  AI Receptionist · {data.receptionist.assistant_name || "Svario"}
                </p>
                <p className="mt-1">{data.receptionist.greeting}</p>
              </div>
            )}
          </div>
          {data.show_hours && (
            <div className="rounded-2xl bg-[#F5F3EC] p-5 text-xs">
              <p className="mb-3 font-semibold uppercase tracking-wider text-[#3D5A45]">Sanctuary Hours</p>
              <div className="space-y-2">
                {data.hours.map((h) => (
                  <div key={h.weekday} className="flex justify-between">
                    <span className="text-[#5C7061]">{formatWeekdayName(h.weekday)}</span>
                    <span className="font-medium text-[#243228]">{formatHourRange(h)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      <footer className="mt-6 border-t border-[#DCE2D4] bg-[#E9EFE3] py-8 text-center text-xs text-[#4C5F51]">
        <p className="font-serif text-base text-[#1F2D23]">{data.business.display_name}</p>
        <div className="mt-2 flex flex-wrap justify-center gap-4">
          {data.business.phone && <span>{data.business.phone}</span>}
          {data.business.email && <span>{data.business.email}</span>}
          {igHref && <a href={igHref} target="_blank" rel="noreferrer" className="underline">Instagram</a>}
          {fbHref && <a href={fbHref} target="_blank" rel="noreferrer" className="underline">Facebook</a>}
          {waHref && <a href={waHref} target="_blank" rel="noreferrer" className="underline">WhatsApp</a>}
        </div>
      </footer>
    </div>
  );
}
