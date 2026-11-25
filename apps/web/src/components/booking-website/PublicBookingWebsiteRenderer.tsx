"use client";

import React, { useState } from "react";
import type { WebRtcEnvironmentAdapters } from "@/lib/voice/webrtcClient";
import type { PublicBookingWebsiteData, PublicSalonServiceItem } from "@/types/website";
import { PublicAiReceptionist } from "./receptionist/PublicAiReceptionist";
import { resolveReceptionistTemplateTheme } from "./receptionist/template-theme-adapter";
import { resolveTemplateEntry } from "./template-registry";
import { formatServicePrice, safeExternalHref } from "./template-utils";

export interface PublicBookingWebsiteRendererProps {
  data: PublicBookingWebsiteData;
  isPreview?: boolean;
  voiceAdapters?: WebRtcEnvironmentAdapters;
}

/**
 * Renders the approved salon website template and connects booking CTAs
 * and the template-aware Stage 3 Public AI Receptionist without modifying
 * any of the 8 locked template components or the locked voice core.
 */
export function PublicBookingWebsiteRenderer({
  data,
  isPreview = false,
  voiceAdapters,
}: PublicBookingWebsiteRendererProps): React.JSX.Element {
  const entry = resolveTemplateEntry(data.template_id);
  const TemplateComponent = entry.Component;
  const theme = resolveReceptionistTemplateTheme(data);
  const [bookingModalOpen, setBookingModalOpen] = useState(false);
  const [receptionistOpen, setReceptionistOpen] = useState(false);
  const [selectedService, setSelectedService] = useState<PublicSalonServiceItem | null>(null);

  const handleBookClick = (service?: PublicSalonServiceItem) => {
    setSelectedService(service ?? null);
    setBookingModalOpen(true);
  };

  const whatsappHref = safeExternalHref(data.social_whatsapp, "whatsapp");

  return (
    <div className="relative min-h-full">
      <TemplateComponent data={data} onBookClick={handleBookClick} isPreview={isPreview} />

      {/* Centralized, theme-adapted Svario attribution footer */}
      <div
        role="contentinfo"
        aria-label="Svario Platform Attribution"
        data-testid="public-website-svario-footer"
        style={{
          backgroundColor:
            theme.templateId === "urban_chic" ? "#FEF08A" : theme.surfaceBg,
          borderColor:
            theme.templateId === "urban_chic" ? "transparent" : theme.borderColor,
          color:
            theme.templateId === "urban_chic" ? "#12131F" : theme.textMuted,
          fontFamily: theme.fontFamily,
        }}
        className={`w-full px-6 text-center ${
          theme.templateId === "urban_chic" ? "pt-1 pb-6" : "border-t py-5"
        }`}
      >
        <div className="mx-auto flex max-w-4xl flex-col items-center justify-center gap-1 break-words">
          <p
            style={{
              color:
                theme.templateId === "urban_chic" ? "#12131F" : theme.textPrimary,
            }}
            className="text-xs font-medium tracking-wide"
          >
            Powered by Svario
          </p>
          <p className="text-[11px] font-medium opacity-85">
            All rights reserved by Svario.
          </p>
        </div>
      </div>

      <PublicAiReceptionist
        data={data}
        isPreview={isPreview}
        isOpen={receptionistOpen}
        onOpen={() => setReceptionistOpen(true)}
        onClose={() => setReceptionistOpen(false)}
        selectedService={selectedService}
        adapters={voiceAdapters}
      />

      {bookingModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Book with ${data.business.display_name}`}
          data-testid="public-booking-entry-modal"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
        >
          <div className="w-full max-w-md rounded-2xl border border-white/15 bg-[#111629] p-6 text-[#F5F7FC] shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-widest text-[#36C6D3]">
                  {isPreview ? "Preview Booking Entry" : "Reserve Your Appointment"}
                </p>
                <h3 className="mt-1 text-lg font-bold text-white">{data.business.display_name}</h3>
              </div>
              <button
                type="button"
                aria-label="Close booking dialog"
                onClick={() => setBookingModalOpen(false)}
                className="rounded-lg border border-white/15 px-2.5 py-1 text-xs text-slate-300 hover:bg-white/10"
              >
                ✕
              </button>
            </div>

            {selectedService ? (
              <div className="mt-4 rounded-xl border border-white/10 bg-[#0B1020] p-4">
                <p className="text-xs text-slate-400">Selected Treatment</p>
                <div className="mt-1 flex items-baseline justify-between gap-2">
                  <p className="text-sm font-semibold text-white">{selectedService.name}</p>
                  <span className="text-sm font-bold text-[#36C6D3]">
                    {formatServicePrice(selectedService.price, selectedService.currency)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-400">
                  Duration: {selectedService.duration_minutes} minutes
                </p>
              </div>
            ) : (
              <p className="mt-3 text-xs leading-relaxed text-slate-300">
                Choose how you would like to reserve your appointment with{" "}
                <strong className="text-white">{data.business.display_name}</strong>.
              </p>
            )}

            {data.show_ai_receptionist && data.receptionist.enabled && (
              <div className="mt-4 rounded-xl border border-[#7657F6]/40 bg-[#7657F6]/10 p-4 text-xs">
                <p className="font-semibold text-[#C4B5FD]">
                  AI Voice Receptionist · {data.receptionist.assistant_name || "Svario"}
                </p>
                <p className="mt-1 text-slate-200">
                  {data.receptionist.greeting ||
                    "Our AI receptionist checks live salon availability and confirms your booking."}
                </p>
                <button
                  type="button"
                  data-testid="booking-modal-talk-to-ai-button"
                  onClick={() => {
                    setBookingModalOpen(false);
                    setReceptionistOpen(true);
                  }}
                  className="mt-3 w-full rounded-xl bg-[#7657F6] px-4 py-2.5 text-center text-xs font-semibold text-white transition hover:bg-[#6546e6]"
                >
                  Talk to AI Receptionist
                </button>
              </div>
            )}

            <div className="mt-5 space-y-2.5">
              {data.business.phone && (
                <a
                  href={`tel:${data.business.phone}`}
                  className="block w-full rounded-xl bg-[#7657F6] px-4 py-2.5 text-center text-xs font-semibold text-white transition hover:bg-[#6546e6]"
                >
                  Call Salon · {data.business.phone}
                </a>
              )}
              {whatsappHref && (
                <a
                  href={whatsappHref}
                  target="_blank"
                  rel="noreferrer"
                  className="block w-full rounded-xl border border-emerald-400/40 bg-emerald-500/15 px-4 py-2.5 text-center text-xs font-semibold text-emerald-200 hover:bg-emerald-500/25"
                >
                  Message on WhatsApp
                </a>
              )}
              {data.business.email && (
                <a
                  href={`mailto:${data.business.email}?subject=${encodeURIComponent(
                    selectedService
                      ? `Booking Inquiry: ${selectedService.name}`
                      : `Appointment Request — ${data.business.display_name}`
                  )}`}
                  className="block w-full rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-center text-xs font-semibold text-slate-200 hover:bg-white/10"
                >
                  Email · {data.business.email}
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
