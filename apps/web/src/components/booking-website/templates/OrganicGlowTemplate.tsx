"use client";

import React from "react";
import { MobileNavMenu } from "../MobileNavMenu";
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
      <header className="px-3 pt-4 sm:px-6 sm:pt-5">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 rounded-3xl border border-[#DCE2D4] bg-[#FCFBF7] px-4 py-3.5 shadow-sm sm:gap-4 sm:px-6 sm:py-4">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            {data.logo_url ? (
              <img
                src={data.logo_url}
                alt={`${data.business.display_name} logo`}
                className="h-9 w-9 shrink-0 rounded-2xl object-cover sm:h-10 sm:w-10"
              />
            ) : (
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-[#E3ECDC] text-base text-[#3D5A45] sm:h-10 sm:w-10 sm:text-lg">
                🌿
              </div>
            )}
            <div className="min-w-0">
              <p className="break-words text-sm font-semibold text-[#243228] sm:text-base">{data.business.display_name}</p>
              <p className="truncate text-[10px] text-[#5C7061] sm:text-[11px]">Holistic Salon & Skin Rituals</p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2 sm:gap-5 text-xs font-medium text-[#4D6152]">
            {data.show_services && <a href="#rituals" className="hidden md:inline hover:text-[#243228]">Rituals</a>}
            {data.show_hours && <a href="#sanctuary" className="hidden md:inline hover:text-[#243228]">Sanctuary</a>}
            <button
              type="button"
              onClick={() => onBookClick?.()}
              className={`${radius} min-h-[40px] bg-[#3D5A45] px-3.5 py-2 text-xs font-semibold text-[#F9F8F3] transition hover:bg-[#2F4736] sm:px-5 sm:py-2.5`}
            >
              Book a Ritual
            </button>
            <MobileNavMenu
              breakpoint="md"
              links={[
                ...(data.show_services ? [{ href: "#rituals", label: "Rituals" }] : []),
                ...(data.show_hours ? [{ href: "#sanctuary", label: "Sanctuary" }] : []),
              ]}
              buttonClassName="rounded-2xl border border-[#DCE2D4] bg-[#F5F3EC] text-[#3D5A45]"
              panelClassName="border-[#DCE2D4] bg-[#FCFBF7] text-[#243228]"
              linkClassName="text-[#4D6152] hover:bg-[#E9EFE3] hover:text-[#243228]"
            />
          </div>
        </div>
      </header>

      {/* Organic Curved Wellness Hero */}
      <section className="mx-auto max-w-6xl px-3 py-8 sm:px-6 sm:py-12">
        <div className="grid items-center gap-6 rounded-[28px] bg-[#E9EFE3] p-5 sm:gap-8 sm:rounded-[36px] sm:p-8 lg:grid-cols-12 lg:p-12">
          <div className="min-w-0 space-y-5 lg:col-span-6">
            <span className="inline-flex items-center gap-2 rounded-full bg-[#FCFBF7] px-3.5 py-1 text-xs font-medium text-[#3D5A45]">
              <span>●</span> Mindful Beauty · Botanical Care
            </span>
            <h1 className="break-words font-serif text-3xl leading-[1.15] text-[#1F2D23] sm:text-4xl lg:text-5xl">
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
                className={`${radius} flex min-h-[44px] w-full items-center justify-center bg-[#3D5A45] px-6 py-3 text-xs font-semibold text-[#FCFBF7] shadow-sm hover:bg-[#2F4736] sm:w-auto`}
              >
                Schedule Your Visit
              </button>
              <a
                href="#rituals"
                className={`${radius} flex min-h-[44px] w-full items-center justify-center border border-[#B9C8B2] bg-[#FCFBF7] px-5 py-3 text-xs font-semibold text-[#3D5A45] sm:w-auto`}
              >
                View Treatments
              </a>
            </div>
          </div>

          <div className="min-w-0 lg:col-span-6">
            <div className="overflow-hidden rounded-[24px] border-4 border-[#FCFBF7] bg-[#DCE6D5] shadow-md sm:rounded-[28px]">
              {data.cover_image_url ? (
                <img
                  src={data.cover_image_url}
                  alt={`${data.business.display_name} sanctuary`}
                  className="h-[240px] w-full object-cover sm:h-[300px] lg:h-[380px]"
                />
              ) : (
                <div className="flex h-[240px] flex-col items-center justify-center bg-gradient-to-br from-[#DCE7D5] to-[#C6D8BE] p-6 text-center sm:h-[300px] sm:p-8 lg:h-[380px]">
                  <span className="text-4xl">🍃</span>
                  <p className="mt-3 break-words font-serif text-xl text-[#243228] sm:text-2xl">{data.business.display_name}</p>
                  <p className="mt-1 text-xs text-[#4C5F51]">Calm · Botanical · Unhurried</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Rituals Section */}
      {data.show_services && (
        <section id="rituals" className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-12">
          <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#5B7761]">
                Wellness Menu
              </p>
              <h2 className="mt-1 font-serif text-2xl text-[#1F2D23] sm:text-3xl">Botanical Treatments</h2>
            </div>
            <span className="rounded-full bg-[#E9EFE3] px-3.5 py-1 text-xs text-[#3D5A45]">
              {data.services.length} curated services
            </span>
          </div>

          <div className="space-y-10">
            {categories.length === 0 ? (
              <div className="rounded-3xl border border-[#DCE2D4] bg-[#FCFBF7] p-6 text-center text-sm text-[#4C5F51] sm:p-8">
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
                        className="flex min-w-0 flex-col justify-between rounded-3xl border border-[#DFE5D8] bg-[#FCFBF7] p-5 transition hover:border-[#8BA68D] sm:p-6"
                      >
                        <div>
                          <div className="flex items-start justify-between gap-3">
                            <h4 className="min-w-0 flex-1 break-words font-serif text-lg text-[#1F2D23] sm:text-xl">{svc.name}</h4>
                            <span className="shrink-0 rounded-full bg-[#E9EFE3] px-3 py-1 text-xs font-semibold text-[#2E4635]">
                              {formatServicePrice(svc.price, svc.currency)}
                            </span>
                          </div>
                          {svc.description && (
                            <p className="mt-2 break-words text-xs leading-relaxed text-[#5C7061]">{svc.description}</p>
                          )}
                        </div>
                        <div className="mt-5 flex items-center justify-between gap-3 border-t border-[#ECEFE7] pt-3">
                          <span className="text-xs text-[#7D6652]">⏱ {svc.duration_minutes} mins</span>
                          <button
                            type="button"
                            onClick={() => onBookClick?.(svc)}
                            className={`${radius} min-h-[40px] shrink-0 bg-[#3D5A45]/10 px-4 py-1.5 text-xs font-semibold text-[#3D5A45] transition hover:bg-[#3D5A45] hover:text-white`}
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
      <section id="sanctuary" className="mx-auto max-w-6xl px-3 py-10 sm:px-6 sm:py-12">
        <div className="grid gap-6 rounded-[28px] border border-[#DCE2D4] bg-[#FCFBF7] p-5 sm:rounded-[32px] sm:p-8 md:grid-cols-2">
          <div className="min-w-0 space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#5B7761]">Our Sanctuary</p>
            <h2 className="break-words font-serif text-2xl text-[#1F2D23]">{data.business.display_name}</h2>
            <p className="text-sm leading-relaxed text-[#4C5F51]">
              {data.business.description || "A serene retreat for holistic hair, skin, and self-care."}
            </p>
            {fullAddress && <p className="break-words text-xs font-medium text-[#3D5A45]">📍 {fullAddress}</p>}
            {data.receptionist.enabled && (
              <div className="mt-3 rounded-2xl bg-[#E9EFE3] p-4 text-xs text-[#2F4736]">
                <p className="font-semibold">
                  AI Receptionist · {data.receptionist.assistant_name || "Svario"}
                </p>
                <p className="mt-1 break-words">{data.receptionist.greeting}</p>
              </div>
            )}
          </div>
          {data.show_hours && (
            <div className="min-w-0 rounded-2xl bg-[#F5F3EC] p-4 text-xs sm:p-5">
              <p className="mb-3 font-semibold uppercase tracking-wider text-[#3D5A45]">Sanctuary Hours</p>
              <div className="space-y-2">
                {data.hours.map((h) => (
                  <div key={h.weekday} className="flex justify-between gap-3">
                    <span className="text-[#5C7061]">{formatWeekdayName(h.weekday)}</span>
                    <span className="shrink-0 font-medium text-[#243228]">{formatHourRange(h)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      <footer className="mt-6 border-t border-[#DCE2D4] bg-[#E9EFE3] px-4 py-8 text-center text-xs text-[#4C5F51] sm:px-6">
        <p className="break-words font-serif text-base text-[#1F2D23]">{data.business.display_name}</p>
        <div className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-2">
          {data.business.phone && <span>{data.business.phone}</span>}
          {data.business.email && <span className="break-all sm:break-words">{data.business.email}</span>}
          {igHref && <a href={igHref} target="_blank" rel="noreferrer" className="py-1 underline">Instagram</a>}
          {fbHref && <a href={fbHref} target="_blank" rel="noreferrer" className="py-1 underline">Facebook</a>}
          {waHref && <a href={waHref} target="_blank" rel="noreferrer" className="py-1 underline">WhatsApp</a>}
        </div>
      </footer>
    </div>
  );
}
