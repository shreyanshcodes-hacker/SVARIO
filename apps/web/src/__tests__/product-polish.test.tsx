import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import LandingPage from "@/app/page";
import AboutPage from "@/app/about/page";
import { SvarioBrandLogo } from "@/components/SvarioBrandLogo";
import { PublicBookingWebsiteRenderer } from "@/components/booking-website/PublicBookingWebsiteRenderer";
import type { BookingWebsiteTemplateId, PublicBookingWebsiteData } from "@/types/website";

const ALL_EIGHT_TEMPLATES: readonly BookingWebsiteTemplateId[] = [
  "luxe_studio",
  "minimal_elegance",
  "blush_beauty",
  "noir_salon",
  "organic_glow",
  "urban_chic",
  "editorial_pro",
  "classic_beauty",
];

function makeSampleSite(templateId: BookingWebsiteTemplateId): PublicBookingWebsiteData {
  return {
    slug: "test-salon",
    template_id: templateId,
    published_at: "2026-11-25T00:00:00Z",
    headline: "Test Salon",
    tagline: "Modern beauty studio",
    logo_url: null,
    cover_image_url: null,
    primary_color: "#7657F6",
    secondary_color: "#171D33",
    accent_color: "#36C6D3",
    background_color: "#0B1020",
    text_color: "#F5F7FC",
    theme: "dark",
    font_family: "inter",
    button_style: "rounded",
    social_instagram: null,
    social_facebook: null,
    social_whatsapp: null,
    show_services: true,
    show_hours: true,
    show_ai_receptionist: true,
    business: {
      display_name: "Test Salon",
      description: "Modern beauty studio",
      phone: "+919876543210",
      email: "hello@testsalon.example",
      address: "123 Main St",
      city: "Mumbai",
      state: "MH",
      country: "India",
      timezone: "Asia/Kolkata",
    },
    hours: [],
    services: [
      {
        id: "svc-1",
        name: "Basic Haircut",
        category: "Hair",
        description: "Classic haircut",
        price: 299,
        currency: "INR",
        duration_minutes: 30,
      },
    ],
    receptionist: {
      enabled: true,
      assistant_name: "Aria",
      greeting: "Welcome!",
    },
  };
}

describe("Product Polish — Branding, Pricing, About Us & Public Footer", () => {
  it("renders official Svario logo and removes Dashboard button from landing navigation", () => {
    render(<LandingPage />);
    const logos = screen.getAllByAltText("Svario logo");
    expect(logos.length).toBeGreaterThanOrEqual(2);
    for (const img of logos) {
      expect(img.getAttribute("src")).toBe("/svario-logo.jpg");
    }

    const nav = screen.getByRole("navigation", { name: "Primary Navigation" });
    expect(within(nav).queryByRole("link", { name: "Dashboard" })).toBeNull();
    expect(within(nav).getByRole("link", { name: "About" }).getAttribute("href")).toBe("/about");
    expect(within(nav).getByRole("link", { name: "Sign In" }).getAttribute("href")).toBe("/login");
    expect(within(nav).getByRole("link", { name: "Get Started" }).getAttribute("href")).toBe("/signup");
  });

  it("renders Simple, Transparent Pricing with Starter ₹3,999 and Pro Coming Soon", () => {
    render(<LandingPage />);

    expect(
      screen.getByRole("heading", { name: "Simple, Transparent Pricing" })
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Everything your salon needs to manage customer calls and appointments."
      )
    ).toBeTruthy();

    const starterCard = screen.getByRole("article", { name: "Starter Plan" });
    expect(within(starterCard).getByText("₹3,999")).toBeTruthy();
    expect(within(starterCard).getByText("Per month")).toBeTruthy();
    expect(within(starterCard).getByRole("link", { name: "Get Started" }).getAttribute("href")).toBe("/signup");

    const proCard = screen.getByRole("article", { name: "Pro Plan" });
    expect(within(proCard).getAllByText("Coming Soon").length).toBeGreaterThanOrEqual(2);
    expect(within(proCard).queryByRole("button")).toBeNull();
    expect(within(proCard).queryByText(/₹/)).toBeNull();
  });

  it("renders the About Us page with real founder portrait, bio, and Shreyansh Codes attribution", () => {
    render(<AboutPage />);

    expect(screen.getByRole("heading", { name: "Shreyansh Jaiswal" })).toBeTruthy();
    expect(screen.getByText("Founder & CEO, Svario")).toBeTruthy();
    expect(
      screen.getByText(
        "Building intelligent digital products with a focus on AI, software development, and automation. Through Shreyansh Codes, I work on creating practical technology solutions, websites, applications, and AI-powered systems."
      )
    ).toBeTruthy();
    expect(screen.getByText("Developed with Shreyansh Codes")).toBeTruthy();

    const portrait = screen.getByAltText("Shreyansh Jaiswal — Founder & CEO, Svario");
    expect(portrait.getAttribute("src")).toContain("founder-shreyansh.png");
  });

  it.each(ALL_EIGHT_TEMPLATES)(
    "renders centered Svario attribution and copyright footer for template '%s'",
    (templateId) => {
      render(<PublicBookingWebsiteRenderer data={makeSampleSite(templateId)} isPreview />);
      const footer = screen.getByTestId("public-website-svario-footer");
      expect(footer.className).toContain("text-center");
      expect(within(footer).getByText("Powered by Svario")).toBeTruthy();
      expect(within(footer).getByText("All rights reserved by Svario.")).toBeTruthy();
    }
  );

  it("positions Salons as Available Now, Clinics and Hospitals as Coming Soon, and removes developer text", () => {
    render(<LandingPage />);

    // Salons card is available with active /signup CTA
    const salonCard = screen.getByRole("article", { name: "Salons Industry" });
    expect(within(salonCard).getByText("Available Now")).toBeTruthy();
    expect(within(salonCard).getByRole("link", { name: "Get Started" }).getAttribute("href")).toBe("/signup");

    // Clinics card is Coming Soon with zero active CTAs
    const clinicCard = screen.getByRole("article", { name: "Clinics Industry" });
    expect(within(clinicCard).getAllByText("Coming Soon").length).toBeGreaterThanOrEqual(2);
    expect(within(clinicCard).queryByRole("link")).toBeNull();
    expect(within(clinicCard).queryByRole("button")).toBeNull();

    // Hospitals card is Coming Soon with zero active CTAs
    const hospitalCard = screen.getByRole("article", { name: "Hospitals Industry" });
    expect(within(hospitalCard).getAllByText("Coming Soon").length).toBeGreaterThanOrEqual(2);
    expect(within(hospitalCard).queryByRole("link")).toBeNull();
    expect(within(hospitalCard).queryByRole("button")).toBeNull();

    // Zero Stage 0 or internal developer labels anywhere on the landing page
    expect(screen.queryByText(/Stage 0/i)).toBeNull();
    expect(screen.queryByText(/Future Stages/i)).toBeNull();
    expect(screen.queryByText(/Shared Platform Contracts/i)).toBeNull();
    expect(screen.queryByText(/INDUSTRY VERTICAL/i)).toBeNull();
    expect(screen.queryByText(/Informational/i)).toBeNull();
  });

  it("supports dark, light, and compact SvarioBrandLogo presentations", () => {
    const { rerender } = render(<SvarioBrandLogo variant="dark" />);
    expect(screen.getByAltText("Svario logo")).toBeTruthy();
    rerender(<SvarioBrandLogo variant="light" compact />);
    expect(screen.getByAltText("Svario logo")).toBeTruthy();
  });
});
