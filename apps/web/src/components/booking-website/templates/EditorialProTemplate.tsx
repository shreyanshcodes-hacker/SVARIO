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
 * Template 07 — Editorial Pro
 * Magazine-inspired masthead, asymmetric 2/3 + 1/3 spread, pull-quote bio,
 * lookbook service directory, and colophon footer.
 */
export function EditorialProTemplate({ data, onBookClick }: TemplateComponentProps): React.JSX.Element {
  const radius = getButtonRadiusClass(data.button_style);
  const categories = groupServicesByCategory(data.services);
  const fullAddress = formatFullAddress(data);
  const igHref = safeExternalHref(data.social_instagram, "instagram");
  const fbHref = safeExternalHref(data.social_facebook, "facebook");
  const waHref = safeExternalHref(data.social_whatsapp, "whatsapp");

  return (
    <div
      data-testid="template-editorial_pro"
      className="min-h-full bg-[#FBFBF9] text-[#161616]"
      style={{ fontFamily: getFontFamilyStack(data.font_family) }}
    >
      {/* Magazine Masthead */}
      <header className="border-b border-[#161616]">
        <div className="mx-auto max-w-6xl px-6 py-3">
          <div className="flex items-center justify-between border-b border-[#161616]/15 pb-2 text-[10px] tracking-[0.22em] uppercase text-[#5E5E5E]">
            <span>{data.business.city || "SALON EDITION"}</span>
            <span>ESTABLISHED FOR MODERN BEAUTY</span>
            <button
              type="button"
              onClick={() => onBookClick?.()}
              className="font-semibold text-[#161616] underline underline-offset-4"
            >
              BOOK NOW
            </button>
          </div>
          <div className="flex flex-col items-center justify-center py-5 text-center">
            <div className="flex items-center gap-3">
              {data.logo_url && (
                <img
                  src={data.logo_url}
                  alt={`${data.business.display_name} logo`}
                  className="h-10 w-10 rounded-full object-cover"
                />
              )}
              <h1 className="font-serif text-3xl font-normal tracking-[0.1em] uppercase sm:text-5xl">
                {data.business.display_name}
              </h1>
            </div>
          </div>
        </div>
      </header>

      {/* Asymmetric Editorial Spread */}
      <section className="mx-auto grid max-w-6xl gap-8 border-b border-[#161616]/20 px-6 py-12 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <div className="overflow-hidden bg-[#EAE8E1]">
            {data.cover_image_url ? (
              <img
                src={data.cover_image_url}
                alt={`${data.business.display_name} editorial`}
                className="h-[340px] w-full object-cover sm:h-[460px]"
              />
            ) : (
              <div className="flex h-[320px] flex-col justify-between bg-gradient-to-tr from-[#232220] via-[#3A3733] to-[#5E5951] p-10 text-[#FBFBF9] sm:h-[440px]">
                <span className="text-[11px] tracking-[0.28em] uppercase text-[#D8D3C8]">
                  LOOKBOOK // FEATURED SALON
                </span>
                <p className="max-w-md font-serif text-3xl italic leading-snug sm:text-4xl">
                  &ldquo;{data.headline || "Where editorial artistry meets everyday wearability."}&rdquo;
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col justify-between border-t border-[#161616]/20 pt-6 lg:col-span-4 lg:border-t-0 lg:border-l lg:pl-8 lg:pt-0">
          <div className="space-y-4">
            <p className="text-[10px] font-semibold tracking-[0.26em] uppercase text-[#6F6A61]">
              EDITOR&apos;S NOTE
            </p>
            <h2 className="font-serif text-2xl leading-snug">
              {data.headline || `The Art of Hair & Skin at ${data.business.display_name}`}
            </h2>
            <p className="text-sm leading-relaxed text-[#4F4D49]">
              {data.tagline ||
                data.business.description ||
                "Precision silhouettes, dimensional color, and bespoke skin treatments curated by seasoned stylists."}
            </p>
          </div>
          <div className="mt-8 space-y-3 border-t border-[#161616]/15 pt-5">
            <button
              type="button"
              onClick={() => onBookClick?.()}
              className={`${radius} w-full bg-[#161616] px-6 py-3.5 text-xs font-semibold tracking-[0.2em] uppercase text-white transition hover:bg-[#333]`}
            >
              Reserve Sitting
            </button>
            {data.business.phone && (
              <p className="text-center text-[11px] tracking-[0.14em] uppercase text-[#5E5E5E]">
                Direct Desk · {data.business.phone}
              </p>
            )}
          </div>
        </div>
      </section>

      {/* Lookbook Service Directory */}
      {data.show_services && (
        <section id="services" className="mx-auto max-w-6xl border-b border-[#161616]/20 px-6 py-16">
          <div className="mb-10 grid gap-4 md:grid-cols-12">
            <div className="md:col-span-4">
              <p className="text-[10px] tracking-[0.26em] uppercase text-[#6F6A61]">DIRECTORY</p>
              <h2 className="mt-1 font-serif text-3xl">The Service Index</h2>
            </div>
            <p className="text-sm leading-relaxed text-[#5E5E5E] md:col-span-8">
              Each service is tailored to texture, tone, and lifestyle. Select any treatment below to request your appointment.
            </p>
          </div>

          <div className="space-y-12">
            {categories.length === 0 ? (
              <p className="font-serif italic text-[#5E5E5E]">
                Bespoke treatments quoted upon consultation.
              </p>
            ) : (
              categories.map((group) => (
                <div key={group.category} className="grid gap-6 border-t border-[#161616]/15 pt-6 md:grid-cols-12">
                  <div className="md:col-span-4">
                    <h3 className="font-serif text-xl italic text-[#161616]">{group.category}</h3>
                  </div>
                  <div className="divide-y divide-[#161616]/10 md:col-span-8">
                    {group.items.map((svc) => (
                      <div key={svc.id} className="flex flex-wrap items-baseline justify-between gap-4 py-4 first:pt-0">
                        <div className="max-w-md">
                          <h4 className="text-sm font-semibold uppercase tracking-[0.08em]">{svc.name}</h4>
                          {svc.description && (
                            <p className="mt-1 text-xs text-[#5E5E5E]">{svc.description}</p>
                          )}
                          <p className="mt-1 text-[11px] text-[#807C75]">{svc.duration_minutes} minutes</p>
                        </div>
                        <div className="flex items-center gap-4">
                          <span className="font-serif text-lg">{formatServicePrice(svc.price, svc.currency)}</span>
                          <button
                            type="button"
                            onClick={() => onBookClick?.(svc)}
                            className="text-xs font-semibold tracking-[0.14em] uppercase underline underline-offset-4 hover:opacity-70"
                          >
                            Book
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

      {/* Colophon: Hours, Receptionist & Location */}
      <footer className="mx-auto max-w-6xl px-6 py-12 text-xs text-[#4F4D49]">
        <div className="grid gap-8 md:grid-cols-3">
          <div className="space-y-2">
            <p className="text-[10px] font-semibold tracking-[0.24em] uppercase text-[#161616]">Address</p>
            <p>{fullAddress || data.business.display_name}</p>
            {data.business.phone && <p>{data.business.phone}</p>}
            {data.business.email && <p>{data.business.email}</p>}
          </div>
          {data.show_hours && (
            <div className="space-y-1.5">
              <p className="text-[10px] font-semibold tracking-[0.24em] uppercase text-[#161616]">Hours</p>
              {data.hours.map((h) => (
                <div key={h.weekday} className="flex justify-between">
                  <span>{formatWeekdayName(h.weekday)}</span>
                  <span>{formatHourRange(h)}</span>
                </div>
              ))}
            </div>
          )}
          <div className="space-y-2">
            <p className="text-[10px] font-semibold tracking-[0.24em] uppercase text-[#161616]">Connect</p>
            {data.receptionist.enabled && (
              <p className="italic">
                AI Concierge ({data.receptionist.assistant_name || "Svario"}): {data.receptionist.greeting}
              </p>
            )}
            <div className="flex gap-4 pt-1">
              {igHref && <a href={igHref} target="_blank" rel="noreferrer" className="underline">Instagram</a>}
              {fbHref && <a href={fbHref} target="_blank" rel="noreferrer" className="underline">Facebook</a>}
              {waHref && <a href={waHref} target="_blank" rel="noreferrer" className="underline">WhatsApp</a>}
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
