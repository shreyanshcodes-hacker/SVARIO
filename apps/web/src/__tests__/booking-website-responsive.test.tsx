import React from "react";
import { describe, expect, it, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { PublicBookingWebsiteRenderer } from "@/components/booking-website/PublicBookingWebsiteRenderer";
import {
  APPROVED_TEMPLATE_IDS,
  type BookingWebsiteTemplateId,
  type PublicBookingWebsiteData,
} from "@/types/website";

function buildResponsiveTestWebsiteData(
  templateId: BookingWebsiteTemplateId,
  overrides: Partial<PublicBookingWebsiteData> = {}
): PublicBookingWebsiteData {
  return {
    slug: "riya-luxury-salon-studio",
    template_id: templateId,
    published_at: "2026-11-24T12:00:00Z",
    headline: "Bespoke Hair Architecture & Botanical Skin Rituals",
    tagline: "Tailored luxury salon treatments designed for effortless beauty.",
    logo_url: null,
    cover_image_url: null,
    primary_color: "#7657F6",
    secondary_color: "#36C6D3",
    accent_color: "#D4AF37",
    background_color: "#0B1020",
    text_color: "#F5F7FC",
    theme: "dark",
    font_family: "inter",
    button_style: "rounded",
    social_instagram: "@riyasalon",
    social_facebook: "riyasalon",
    social_whatsapp: "+919876543210",
    show_services: true,
    show_hours: true,
    show_ai_receptionist: true,
    business: {
      display_name: "Riya's Signature Hair & Beauty Atelier",
      description: "An intimate studio offering precision cuts, dimensional color, and restorative facials.",
      phone: "+919876543210",
      email: "concierge.appointments@riyasignatureatelier.example",
      address: "14 Linking Road, Bandra West",
      city: "Mumbai",
      state: "MH",
      country: "India",
      timezone: "Asia/Kolkata",
    },
    hours: [
      { weekday: 1, is_closed: false, opens_at: "10:00", closes_at: "20:00", is_overnight: false },
      { weekday: 2, is_closed: false, opens_at: "10:00", closes_at: "20:00", is_overnight: false },
      { weekday: 0, is_closed: true, opens_at: null, closes_at: null, is_overnight: false },
    ],
    services: [
      {
        id: "svc-1",
        name: "Signature Balayage & Gloss Treatment",
        category: "Color & Gloss",
        description: "Custom hand-painted dimension with bond-building glaze and blowout.",
        duration_minutes: 120,
        price: 4999,
        currency: "INR",
      },
      {
        id: "svc-2",
        name: "Botanical Hydration Facial",
        category: "Skin Rituals",
        description: "Deeply nourishing facial massage and calming botanical mask.",
        duration_minutes: 60,
        price: 1999,
        currency: "INR",
      },
    ],
    receptionist: {
      enabled: true,
      assistant_name: "Riya AI Concierge",
      greeting: "Welcome! Ask me about services, pricing, or live availability.",
    },
    ...overrides,
  };
}

describe("Public Booking Website — Responsive Layout & Mobile Usability", () => {
  afterEach(() => {
    cleanup();
  });

  it.each(APPROVED_TEMPLATE_IDS)(
    "renders template '%s' with overflow-x-clip protection and Svario footer clearance",
    (templateId) => {
      const data = buildResponsiveTestWebsiteData(templateId);
      const { container } = render(<PublicBookingWebsiteRenderer data={data} />);

      const root = container.firstElementChild as HTMLElement;
      expect(root.className).toContain("overflow-x-clip");
      expect(root.className).toContain("w-full");

      expect(screen.getByTestId(`template-${templateId}`)).toBeTruthy();

      const footer = screen.getByTestId("public-website-svario-footer");
      expect(footer.textContent).toContain("Powered by Svario");
      expect(footer.textContent).toContain("All rights reserved by Svario.");
      expect(footer.className).toContain("pb-20");
    }
  );

  it.each(["luxe_studio", "blush_beauty", "organic_glow", "classic_beauty"] as const)(
    "provides accessible mobile navigation menu for template '%s'",
    (templateId) => {
      const data = buildResponsiveTestWebsiteData(templateId);
      render(<PublicBookingWebsiteRenderer data={data} />);

      const toggle = screen.getByTestId("mobile-nav-toggle");
      expect(toggle.getAttribute("aria-expanded")).toBe("false");
      expect(toggle.className).toContain("min-h-[40px]");
      expect(toggle.className).toContain("min-w-[40px]");

      fireEvent.click(toggle);
      expect(toggle.getAttribute("aria-expanded")).toBe("true");

      const panel = screen.getByTestId("mobile-nav-panel");
      const links = panel.querySelectorAll("a");
      expect(links.length).toBeGreaterThanOrEqual(2);
      links.forEach((link) => {
        expect(link.className).toContain("min-h-[44px]");
      });

      // Clicking a link closes the mobile menu
      fireEvent.click(links[0]);
      expect(screen.queryByTestId("mobile-nav-panel")).toBeNull();

      // Re-open and close with Escape
      fireEvent.click(toggle);
      expect(screen.getByTestId("mobile-nav-panel")).toBeTruthy();
      fireEvent.keyDown(window, { key: "Escape" });
      expect(screen.queryByTestId("mobile-nav-panel")).toBeNull();
    }
  );

  it("renders responsive booking modal with viewport height constraints and accessible touch targets", () => {
    const data = buildResponsiveTestWebsiteData("luxe_studio");
    render(<PublicBookingWebsiteRenderer data={data} />);

    // Trigger booking from a service card
    const reserveButtons = screen.getAllByRole("button", { name: /Reserve/i });
    fireEvent.click(reserveButtons[reserveButtons.length - 1]);

    const modal = screen.getByTestId("public-booking-entry-modal");
    const card = modal.firstElementChild as HTMLElement;
    expect(card.className).toContain("max-h-[calc(100dvh-1.5rem)]");
    expect(card.className).toContain("overflow-y-auto");

    const closeBtn = screen.getByRole("button", { name: "Close booking dialog" });
    expect(closeBtn.className).toContain("min-h-[40px]");
    expect(closeBtn.className).toContain("min-w-[40px]");

    const talkToAiBtn = screen.getByTestId("booking-modal-talk-to-ai-button");
    expect(talkToAiBtn.className).toContain("min-h-[44px]");
  });

  it("renders responsive Public AI Receptionist panel with dvh height cap and scrollable body", () => {
    const data = buildResponsiveTestWebsiteData("urban_chic");
    render(<PublicBookingWebsiteRenderer data={data} />);

    const launcher = screen.getByTestId("public-ai-receptionist-launcher");
    expect(launcher.className).toContain("min-h-[44px]");

    fireEvent.click(launcher);
    const panel = screen.getByTestId("public-ai-receptionist-panel");
    const card = panel.firstElementChild as HTMLElement;
    expect(card.className).toContain("max-h-[calc(100dvh-1.25rem)]");

    const startBtn = screen.getByTestId("start-public-voice-button");
    expect(startBtn.className).toContain("min-h-[44px]");

    const closeBtn = screen.getByTestId("close-ai-receptionist-button");
    expect(closeBtn.className).toContain("min-h-[40px]");
  });
});
