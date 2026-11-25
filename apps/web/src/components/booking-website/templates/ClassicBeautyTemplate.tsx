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
 * Template 08 — Classic Beauty
 * Clean, timeless, trustworthy salon layout with top utility bar,
 * balanced framed hero, and a 2-column menu paired with a sticky booking/hours sidebar.
 */
export function ClassicBeautyTemplate({ data, onBookClick }: TemplateComponentProps): React.JSX.Element {
  const radius = getButtonRadiusClass(data.button_style);
  const categories = groupServicesByCategory(data.services);
  const fullAddress = formatFullAddress(data);
  const navy = "#1E293B";
  const brandBtn = data.primary_color || "#1E293B";
  const igHref = safeExternalHref(data.social_instagram, "instagram");
  const fbHref = safeExternalHref(data.social_facebook, "facebook");
  const waHref = safeExternalHref(data.social_whatsapp, "whatsapp");

  return (
    <div
      data-testid="template-classic_beauty"
      className="min-h-full bg-[#FFFFFF] text-[#1E293B]"
      style={{ fontFamily: getFontFamilyStack(data.font_family) }}
    >
      {/* Classic Top Utility Bar */}
      <div className="bg-[#1E293B] px-4 py-2 text-[11px] text-slate-200 sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2">
          <span className="break-words">{fullAddress || `${data.business.display_name} · Official Booking Portal`}</span>
          <div className="flex flex-wrap items-center gap-4">
            {data.business.phone && <span>Call: {data.business.phone}</span>}
            {data.business.email && <span className="hidden sm:inline">{data.business.email}</span>}
          </div>
        </div>
      </div>

      {/* Balanced Main Navigation */}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3.5 sm:gap-4 sm:px-6 sm:py-4">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            {data.logo_url ? (
              <img
                src={data.logo_url}
                alt={`${data.business.display_name} logo`}
                className="h-10 w-10 shrink-0 rounded-lg border border-slate-200 object-cover sm:h-11 sm:w-11"
              />
            ) : (
              <div
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-base font-bold text-white sm:h-11 sm:w-11"
                style={{ backgroundColor: navy }}
              >
                {data.business.display_name.slice(0, 1).toUpperCase()}
              </div>
            )}
            <div className="min-w-0">
              <p className="break-words text-base font-bold text-[#1E293B] sm:text-lg">{data.business.display_name}</p>
              <p className="truncate text-[11px] text-slate-500 sm:text-xs">Hair · Skin · Beauty Studio</p>
            </div>
          </div>

          <nav aria-label="Salon navigation" className="hidden items-center gap-6 text-xs font-semibold text-slate-600 md:flex">
            {data.show_services && <a href="#services" className="hover:text-[#1E293B]">Services</a>}
            <a href="#about" className="hover:text-[#1E293B]">About</a>
            {data.show_hours && <a href="#hours" className="hover:text-[#1E293B]">Hours & Contact</a>}
          </nav>

          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={() => onBookClick?.()}
              className={`${radius} min-h-[40px] px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition hover:opacity-90 sm:px-5 sm:py-2.5`}
              style={{ backgroundColor: brandBtn }}
            >
              Book Appointment
            </button>
            <MobileNavMenu
              breakpoint="md"
              links={[
                ...(data.show_services ? [{ href: "#services", label: "Services" }] : []),
                { href: "#about", label: "About" },
                ...(data.show_hours ? [{ href: "#hours", label: "Hours & Contact" }] : []),
              ]}
              buttonClassName="rounded-lg border border-slate-200 bg-slate-50 text-[#1E293B]"
              panelClassName="border-slate-200 bg-white text-[#1E293B]"
              linkClassName="text-slate-600 hover:bg-slate-100 hover:text-[#1E293B]"
            />
          </div>
        </div>
      </header>

      {/* Balanced Framed Hero */}
      <section className="border-b border-slate-200 bg-slate-50">
        <div className="mx-auto grid max-w-6xl items-center gap-8 px-4 py-10 sm:px-6 sm:py-12 lg:grid-cols-12">
          <div className="min-w-0 space-y-4 lg:col-span-6">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Welcome to {data.business.display_name}
            </p>
            <h1 className="break-words font-serif text-3xl font-bold leading-tight text-[#0F172A] sm:text-4xl lg:text-5xl">
              {data.headline || `Timeless Salon Care You Can Trust`}
            </h1>
            <p className="text-sm leading-relaxed text-slate-600">
              {data.tagline ||
                data.business.description ||
                "Experienced stylists, transparent pricing, and effortless online booking for every occasion."}
            </p>
            <div className="flex flex-wrap gap-3 pt-2">
              <button
                type="button"
                onClick={() => onBookClick?.()}
                className={`${radius} flex min-h-[44px] w-full items-center justify-center px-6 py-3 text-xs font-semibold text-white shadow-sm transition hover:opacity-90 sm:w-auto`}
                style={{ backgroundColor: brandBtn }}
              >
                Book Your Appointment
              </button>
              {data.show_services && (
                <a
                  href="#services"
                  className={`${radius} flex min-h-[44px] w-full items-center justify-center border border-slate-300 bg-white px-5 py-3 text-xs font-semibold text-slate-700 hover:bg-slate-100 sm:w-auto`}
                >
                  Browse Services
                </a>
              )}
            </div>
          </div>

          <div className="min-w-0 lg:col-span-6">
            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
              {data.cover_image_url ? (
                <img
                  src={data.cover_image_url}
                  alt={`${data.business.display_name} salon`}
                  className="h-[240px] w-full object-cover sm:h-[280px] lg:h-[360px]"
                />
              ) : (
                <div className="flex h-[240px] flex-col items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200 p-6 text-center sm:h-[260px] sm:p-8 lg:h-[340px]">
                  <p className="break-words font-serif text-xl font-bold text-[#1E293B] sm:text-2xl">
                    {data.business.display_name}
                  </p>
                  <p className="mt-2 text-xs text-slate-600">Professional Salon & Beauty Care</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Main Content + Sticky Booking & Hours Sidebar */}
      <section id="services" className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:gap-10 sm:px-6 sm:py-14 lg:grid-cols-12">
        <div className="min-w-0 space-y-10 lg:col-span-8">
          {data.show_services && (
            <div>
              <h2 className="font-serif text-2xl font-bold text-[#0F172A]">Service Menu</h2>
              <p className="mt-1 text-xs text-slate-500">Clear pricing and durations for every appointment.</p>

              <div className="mt-6 space-y-8">
                {categories.length === 0 ? (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
                    Contact our front desk for our full list of salon services and availability.
                  </div>
                ) : (
                  categories.map((group) => (
                    <div key={group.category} className="space-y-3">
                      <h3 className="border-b border-slate-200 pb-2 text-xs font-bold uppercase tracking-wider text-slate-500">
                        {group.category}
                      </h3>
                      <div className="space-y-3">
                        {group.items.map((svc) => (
                          <div
                            key={svc.id}
                            className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 transition hover:border-slate-400 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
                          >
                            <div className="min-w-0 flex-1">
                              <h4 className="break-words text-sm font-bold text-[#0F172A]">{svc.name}</h4>
                              {svc.description && (
                                <p className="mt-0.5 break-words text-xs text-slate-600">{svc.description}</p>
                              )}
                              <p className="mt-1 text-[11px] text-slate-400">{svc.duration_minutes} mins</p>
                            </div>
                            <div className="flex shrink-0 items-center justify-between gap-4 sm:justify-end">
                              <span className="text-sm font-bold text-[#0F172A]">
                                {formatServicePrice(svc.price, svc.currency)}
                              </span>
                              <button
                                type="button"
                                onClick={() => onBookClick?.(svc)}
                                className={`${radius} min-h-[40px] border border-slate-300 px-3.5 py-1.5 text-xs font-semibold text-[#1E293B] hover:bg-[#1E293B] hover:text-white`}
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
            </div>
          )}

          <div id="about" className="rounded-2xl border border-slate-200 bg-slate-50 p-5 sm:p-6">
            <h2 className="break-words font-serif text-xl font-bold text-[#0F172A]">About {data.business.display_name}</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              {data.business.description ||
                "Dedicated to consistent quality, welcoming service, and personalized salon appointments."}
            </p>
          </div>
        </div>

        {/* Sticky Info & Hours Sidebar */}
        <aside id="hours" className="min-w-0 space-y-6 lg:col-span-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <h3 className="text-sm font-bold text-[#0F172A]">Ready to Book?</h3>
            <p className="mt-1 text-xs text-slate-600">
              Reserve your preferred service and time directly with {data.business.display_name}.
            </p>
            <button
              type="button"
              onClick={() => onBookClick?.()}
              className={`${radius} mt-4 min-h-[44px] w-full px-4 py-2.5 text-xs font-semibold text-white transition hover:opacity-90`}
              style={{ backgroundColor: brandBtn }}
            >
              Book an Appointment
            </button>

            {data.receptionist.enabled && (
              <div className="mt-4 rounded-xl bg-slate-50 p-3.5 text-xs text-slate-600">
                <p className="font-semibold text-[#0F172A]">
                  AI Receptionist · {data.receptionist.assistant_name || "Svario"}
                </p>
                <p className="mt-1 break-words">{data.receptionist.greeting}</p>
              </div>
            )}
          </div>

          {data.show_hours && (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <h3 className="text-sm font-bold text-[#0F172A]">Opening Hours</h3>
              <ul className="mt-3 space-y-2 text-xs">
                {data.hours.map((h) => (
                  <li key={h.weekday} className="flex justify-between gap-3 border-b border-slate-100 pb-1.5 last:border-b-0">
                    <span className="text-slate-600">{formatWeekdayName(h.weekday)}</span>
                    <span className="shrink-0 font-semibold text-[#0F172A]">{formatHourRange(h)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </section>

      <footer className="border-t border-slate-200 bg-[#1E293B] px-4 py-8 text-center text-xs text-slate-300 sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-center gap-3">
          <div>
            <p className="break-words font-semibold text-white">{data.business.display_name}</p>
            {fullAddress && <p className="mt-1 break-words text-slate-400">{fullAddress}</p>}
          </div>
          {(igHref || fbHref || waHref) && (
            <div className="flex flex-wrap justify-center gap-4">
              {igHref && <a href={igHref} target="_blank" rel="noreferrer" className="py-1 hover:text-white">Instagram</a>}
              {fbHref && <a href={fbHref} target="_blank" rel="noreferrer" className="py-1 hover:text-white">Facebook</a>}
              {waHref && <a href={waHref} target="_blank" rel="noreferrer" className="py-1 hover:text-white">WhatsApp</a>}
            </div>
          )}
        </div>
      </footer>
    </div>
  );
}
