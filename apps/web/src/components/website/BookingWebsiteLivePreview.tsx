"use client";

import React from "react";
import type { OnboardingBundleData } from "@/types/platform";
import type { SalonService } from "@/types/salon";
import type {
  BookingWebsiteButtonStyleType,
  BookingWebsiteFontFamilyType,
  BookingWebsiteThemeType,
} from "@/types/website";

export interface BookingWebsiteLivePreviewProps {
  businessName: string;
  description: string | null;
  phone: string | null;
  email: string | null;
  city: string | null;
  address: string | null;
  slug: string;
  headline: string;
  tagline: string;
  logoUrl: string | null;
  coverImageUrl: string | null;
  primaryColor: string;
  secondaryColor: string;
  accentColor: string;
  backgroundColor: string;
  textColor: string;
  theme: BookingWebsiteThemeType;
  fontFamily: BookingWebsiteFontFamilyType;
  buttonStyle: BookingWebsiteButtonStyleType;
  showServices: boolean;
  showHours: boolean;
  showAiReceptionist: boolean;
  services: SalonService[];
  onboardingBundle: OnboardingBundleData | null;
}

const FONT_STACK_MAP: Record<BookingWebsiteFontFamilyType, string> = {
  inter: "Inter, ui-sans-serif, system-ui, sans-serif",
  plus_jakarta_sans: "'Plus Jakarta Sans', ui-sans-serif, system-ui, sans-serif",
  dm_sans: "'DM Sans', ui-sans-serif, system-ui, sans-serif",
  playfair_display: "'Playfair Display', Georgia, serif",
  poppins: "Poppins, ui-sans-serif, system-ui, sans-serif",
};

const BUTTON_RADIUS_MAP: Record<BookingWebsiteButtonStyleType, string> = {
  rounded: "rounded-xl",
  pill: "rounded-full",
  square: "rounded-none",
};

const DAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function BookingWebsiteLivePreview({
  businessName,
  description,
  phone,
  email,
  city,
  address,
  slug,
  headline,
  tagline,
  logoUrl,
  coverImageUrl,
  primaryColor,
  secondaryColor,
  accentColor,
  backgroundColor,
  textColor,
  theme,
  fontFamily,
  buttonStyle,
  showServices,
  showHours,
  showAiReceptionist,
  services,
  onboardingBundle,
}: BookingWebsiteLivePreviewProps): React.JSX.Element {
  const cardSurface =
    theme === "light" ? "rgba(15, 23, 42, 0.04)" : "rgba(255, 255, 255, 0.05)";
  const borderColor =
    theme === "light" ? "rgba(15, 23, 42, 0.12)" : "rgba(255, 255, 255, 0.12)";
  const mutedText = theme === "light" ? "rgba(15, 23, 42, 0.68)" : "rgba(245, 247, 252, 0.72)";
  const buttonRadius = BUTTON_RADIUS_MAP[buttonStyle] ?? "rounded-xl";
  const activeServices = services.filter((s) => s.is_active).slice(0, 6);
  const openDays = (onboardingBundle?.hours?.schedule ?? []).filter((d) => !d.is_closed);

  return (
    <div
      data-testid="booking-website-live-preview"
      className="overflow-hidden rounded-2xl border border-white/15 shadow-2xl"
      style={{
        backgroundColor,
        color: textColor,
        fontFamily: FONT_STACK_MAP[fontFamily],
      }}
    >
      {/* Simulated Browser Chrome */}
      <div
        className="flex items-center justify-between border-b px-4 py-2.5 text-[11px]"
        style={{ borderColor, backgroundColor: cardSurface }}
      >
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-rose-400/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" />
        </div>
        <span className="rounded-md px-2.5 py-0.5 font-mono text-[10px]" style={{ color: mutedText }}>
          svario.ai/s/{slug || "your-salon"} (Stage 1 Preview)
        </span>
        <span className="font-mono text-[10px] uppercase" style={{ color: secondaryColor }}>
          {theme}
        </span>
      </div>

      {/* Hero Section */}
      <div className="relative p-6">
        {coverImageUrl && (
          <div
            className="mb-4 h-32 w-full overflow-hidden rounded-xl border bg-cover bg-center"
            style={{
              borderColor,
              backgroundImage: `url(${coverImageUrl})`,
            }}
          />
        )}

        <div className="flex items-center gap-3">
          {logoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={logoUrl}
              alt={`${businessName} logo`}
              className="h-12 w-12 rounded-xl border object-cover"
              style={{ borderColor }}
            />
          ) : (
            <div
              className="flex h-12 w-12 items-center justify-center rounded-xl text-sm font-bold text-white"
              style={{ backgroundColor: primaryColor }}
            >
              {(businessName || "S").slice(0, 2).toUpperCase()}
            </div>
          )}
          <div>
            <p className="text-sm font-bold">{businessName || "Your Salon"}</p>
            <p className="text-xs" style={{ color: mutedText }}>
              {[address, city].filter(Boolean).join(", ") || "Salon location"}
            </p>
          </div>
        </div>

        <h3 className="mt-4 text-xl font-bold leading-snug">
          {headline || `Book your next visit at ${businessName || "our salon"}`}
        </h3>
        <p className="mt-1.5 text-xs leading-relaxed" style={{ color: mutedText }}>
          {tagline || description || "Real-time salon booking powered by Svario."}
        </p>

        <div className="mt-4 flex flex-wrap gap-2.5">
          <span
            className={`inline-flex items-center px-4 py-2 text-xs font-semibold text-white ${buttonRadius}`}
            style={{ backgroundColor: primaryColor }}
          >
            Book Appointment
          </span>
          {showAiReceptionist && (
            <span
              className={`inline-flex items-center border px-4 py-2 text-xs font-semibold ${buttonRadius}`}
              style={{ borderColor: secondaryColor, color: secondaryColor }}
            >
              Talk to {onboardingBundle?.assistant?.assistant_name || "AI Receptionist"}
            </span>
          )}
        </div>
      </div>

      {/* Services Section */}
      {showServices && (
        <div className="border-t px-6 py-4" style={{ borderColor }}>
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold uppercase tracking-wider" style={{ color: secondaryColor }}>
              Featured Services
            </h4>
            <span className="text-[11px]" style={{ color: mutedText }}>
              {activeServices.length} shown
            </span>
          </div>
          {activeServices.length > 0 ? (
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {activeServices.map((svc) => (
                <div
                  key={svc.id}
                  className="flex items-center justify-between rounded-xl border p-2.5 text-xs"
                  style={{ borderColor, backgroundColor: cardSurface }}
                >
                  <div>
                    <p className="font-semibold">{svc.name}</p>
                    <p className="text-[11px]" style={{ color: mutedText }}>
                      {svc.category} • {svc.duration_minutes} min
                    </p>
                  </div>
                  <span className="font-mono font-bold" style={{ color: accentColor }}>
                    {svc.currency} {svc.price}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-xs" style={{ color: mutedText }}>
              Active services from your Salon Dashboard will appear here automatically.
            </p>
          )}
        </div>
      )}

      {/* AI Receptionist & Hours Footer */}
      <div className="grid gap-3 border-t px-6 py-4 sm:grid-cols-2" style={{ borderColor }}>
        {showAiReceptionist && (
          <div className="rounded-xl border p-3 text-xs" style={{ borderColor, backgroundColor: cardSurface }}>
            <p className="font-semibold" style={{ color: primaryColor }}>
              AI Voice Receptionist
            </p>
            <p className="mt-1 text-[11px]" style={{ color: mutedText }}>
              {onboardingBundle?.assistant?.greeting ||
                `Hello, welcome to ${businessName || "our salon"}!`}
            </p>
          </div>
        )}
        {showHours && (
          <div className="rounded-xl border p-3 text-xs" style={{ borderColor, backgroundColor: cardSurface }}>
            <p className="font-semibold" style={{ color: secondaryColor }}>
              Opening Hours & Contact
            </p>
            <p className="mt-1 text-[11px]" style={{ color: mutedText }}>
              {openDays.length > 0
                ? `${openDays.map((d) => DAY_SHORT[d.weekday]).join(", ")} • ${openDays[0].opens_at}–${openDays[0].closes_at}`
                : "Configure hours in Business Profile"}
            </p>
            {(phone || email) && (
              <p className="mt-1 text-[11px]" style={{ color: mutedText }}>
                {[phone, email].filter(Boolean).join(" • ")}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
