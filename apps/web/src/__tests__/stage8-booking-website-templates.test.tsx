import React from "react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { PublicBookingWebsiteRenderer } from "@/components/booking-website/PublicBookingWebsiteRenderer";
import {
  TEMPLATE_CATALOG,
  isApprovedTemplateId,
  resolveTemplateEntry,
} from "@/components/booking-website/template-registry";
import { BookingWebsiteWorkspace } from "@/components/website/BookingWebsiteWorkspace";
import * as api from "@/lib/api";
import {
  APPROVED_TEMPLATE_IDS,
  type BookingWebsiteTemplateId,
  type PublicBookingWebsiteData,
} from "@/types/website";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    fetchBookingWebsiteConfig: vi.fn(),
    fetchOnboardingBundle: vi.fn(),
    fetchSalonServices: vi.fn(),
    saveBookingWebsiteDraft: vi.fn(),
    publishBookingWebsite: vi.fn(),
    unpublishBookingWebsite: vi.fn(),
  };
});

function buildSamplePublicData(
  templateId: BookingWebsiteTemplateId,
  overrides: Partial<PublicBookingWebsiteData> = {}
): PublicBookingWebsiteData {
  return {
    slug: "riya-women-salon",
    template_id: templateId,
    published_at: "2026-11-24T12:00:00Z",
    headline: "Luxury Hair & Botanical Care",
    tagline: "Tailored salon rituals in Mumbai.",
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
    social_instagram: "@riyawomensalon",
    social_facebook: null,
    social_whatsapp: "+919876543210",
    show_services: true,
    show_hours: true,
    show_ai_receptionist: true,
    business: {
      display_name: "Riya Women Salon",
      description: "Modern women's beauty studio offering precision cuts and skincare.",
      phone: "+919876543210",
      email: "hello@riyasalon.example",
      address: "14 Linking Road",
      city: "Mumbai",
      state: "MH",
      country: "India",
      timezone: "Asia/Kolkata",
    },
    hours: [
      { weekday: 1, is_closed: false, opens_at: "10:00", closes_at: "20:00", is_overnight: false },
      { weekday: 0, is_closed: true, opens_at: null, closes_at: null, is_overnight: false },
    ],
    services: [
      {
        id: "svc-1",
        name: "Basic Haircut",
        category: "Hair",
        description: "Wash, cut & signature blow dry",
        duration_minutes: 30,
        price: 299,
        currency: "INR",
      },
      {
        id: "svc-2",
        name: "Premium Facial",
        category: "Skin",
        description: "Hydrating botanical glow facial",
        duration_minutes: 75,
        price: 1299,
        currency: "INR",
      },
    ],
    receptionist: {
      enabled: true,
      assistant_name: "Riya AI Concierge",
      greeting: "Welcome! Ask me about services or book your visit.",
    },
    ...overrides,
  };
}

describe("Stage 2 — 8 Distinct Salon Website Templates & Safe Registry", () => {
  afterEach(() => {
    cleanup();
  });

  it("registers exactly 8 approved templates and safely rejects unknown template IDs", () => {
    expect(TEMPLATE_CATALOG).toHaveLength(8);
    expect(TEMPLATE_CATALOG.map((t) => t.id)).toEqual([...APPROVED_TEMPLATE_IDS]);

    expect(isApprovedTemplateId("luxe_studio")).toBe(true);
    expect(isApprovedTemplateId("classic_beauty")).toBe(true);
    expect(isApprovedTemplateId("../../malicious")).toBe(false);
    expect(isApprovedTemplateId(null)).toBe(false);

    // Unknown IDs fall back safely to luxe_studio
    expect(resolveTemplateEntry("unknown_template_xyz").id).toBe("luxe_studio");
  });

  it.each(APPROVED_TEMPLATE_IDS)(
    "renders template '%s' cleanly with salon data, services, and missing optional images",
    (templateId) => {
      const data = buildSamplePublicData(templateId);
      render(<PublicBookingWebsiteRenderer data={data} />);

      const container = screen.getByTestId(`template-${templateId}`);
      expect(container.textContent).toContain("Riya Women Salon");
      expect(container.textContent).toContain("Basic Haircut");
      expect(container.textContent).toContain("299");
    }
  );

  it("handles empty services and missing contact/images gracefully and opens booking entry modal", () => {
    const minimalData = buildSamplePublicData("minimal_elegance", {
      logo_url: null,
      cover_image_url: null,
      services: [],
      hours: [],
      social_instagram: null,
      social_whatsapp: null,
    });
    render(<PublicBookingWebsiteRenderer data={minimalData} />);

    const bookButtons = screen.getAllByRole("button", { name: /schedule appointment|book now/i });
    fireEvent.click(bookButtons[0]);

    expect(screen.getByTestId("public-booking-entry-modal").textContent).toContain(
      "Riya Women Salon"
    );
  });
});

describe("Stage 2 — Dashboard Template Gallery, Switching & Publishing Lifecycle", () => {
  const baseConfig = {
    id: "11111111-1111-4111-8111-111111111111",
    organization_id: "8867eb36-95c3-4d87-b91f-a9e23f21c88b",
    business_id: "1962bebf-c4b2-4a56-a79e-963f8bd7e334",
    slug: "riya-women-salon",
    template_id: "luxe_studio" as const,
    status: "draft" as const,
    published_at: null,
    headline: "Luxury Hair & Botanical Care",
    tagline: "Tailored salon rituals.",
    logo_path: "org/biz/logo.png",
    logo_url: "https://example.test/logo.png",
    cover_image_path: null,
    cover_image_url: null,
    primary_color: "#7657F6",
    secondary_color: "#36C6D3",
    accent_color: "#D4AF37",
    background_color: "#0B1020",
    text_color: "#F5F7FC",
    theme: "dark" as const,
    font_family: "inter" as const,
    button_style: "rounded" as const,
    social_instagram: "@riyasalon",
    social_facebook: null,
    social_whatsapp: null,
    show_services: true,
    show_hours: true,
    show_ai_receptionist: true,
    preview_url_path: "/s/riya-women-salon",
    public_url_path: null,
    publish_readiness: {
      is_valid: true,
      public_engine_ready: true,
      can_publish: true,
      missing_requirements: [],
      stage_notice: "Stage 2 Dynamic Engine active.",
    },
    created_at: "2026-11-24T10:00:00Z",
    updated_at: "2026-11-24T10:00:00Z",
  };

  const baseBundle = {
    organization: {
      id: baseConfig.organization_id,
      name: "Riya Women Salon",
      slug: "riya-women-salon",
      industry: "salon" as const,
      membership_role: "owner" as const,
      member_count: 1,
      created_at: "2026-11-24T10:00:00Z",
      updated_at: "2026-11-24T10:00:00Z",
    },
    business_id: baseConfig.business_id,
    profile: {
      id: "22222222-2222-4222-8222-222222222222",
      organization_id: baseConfig.organization_id,
      business_id: baseConfig.business_id,
      display_name: "Riya Women Salon",
      description: "Modern women's studio",
      phone: "+919876543210",
      email: "hello@riyasalon.example",
      website: null,
      address: "14 Linking Road",
      city: "Mumbai",
      state: null,
      country: "India",
      postal_code: null,
      timezone: "Asia/Kolkata",
      created_at: "2026-11-24T10:00:00Z",
      updated_at: "2026-11-24T10:00:00Z",
    },
    hours: {
      organization_id: baseConfig.organization_id,
      business_id: baseConfig.business_id,
      timezone: "Asia/Kolkata",
      schedule: [
        { weekday: 1, is_closed: false, opens_at: "10:00", closes_at: "20:00", is_overnight: false },
      ],
    },
    languages: {
      organization_id: baseConfig.organization_id,
      business_id: baseConfig.business_id,
      primary_language: "en" as const,
      supported_languages: ["en" as const],
      entries: [],
    },
    assistant: {
      id: "33333333-3333-4333-8333-333333333333",
      organization_id: baseConfig.organization_id,
      business_id: baseConfig.business_id,
      assistant_name: "Aria",
      greeting: "Welcome!",
      personality: "warm" as const,
      response_style: "balanced" as const,
      enabled: true,
      created_at: "2026-11-24T10:00:00Z",
      updated_at: "2026-11-24T10:00:00Z",
    },
    faqs: [],
    faq_templates: [],
    escalation: {
      id: "44444444-4444-4444-8444-444444444444",
      organization_id: baseConfig.organization_id,
      business_id: baseConfig.business_id,
      enabled: false,
      contact_name: null,
      contact_email: null,
      contact_phone: null,
      preferred_method: "phone" as const,
      escalation_instructions: null,
      created_at: "2026-11-24T10:00:00Z",
      updated_at: "2026-11-24T10:00:00Z",
    },
    healthcare_safeguards: {
      applies_to_healthcare: false,
      administrative_only: false,
      prohibited_actions: [],
      emergency_directive: "",
    },
    progress: {
      id: "55555555-5555-4555-8555-555555555555",
      organization_id: baseConfig.organization_id,
      business_id: baseConfig.business_id,
      current_step: "review" as const,
      completed_steps: [],
      is_completed: true,
      completed_at: "2026-11-24T10:00:00Z",
      created_at: "2026-11-24T10:00:00Z",
      updated_at: "2026-11-24T10:00:00Z",
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchBookingWebsiteConfig).mockResolvedValue(baseConfig);
    vi.mocked(api.fetchOnboardingBundle).mockResolvedValue(baseBundle);
    vi.mocked(api.fetchSalonServices).mockResolvedValue([]);
    vi.mocked(api.saveBookingWebsiteDraft).mockResolvedValue({
      ...baseConfig,
      template_id: "organic_glow",
    });
    vi.mocked(api.publishBookingWebsite).mockResolvedValue({
      ...baseConfig,
      template_id: "organic_glow",
      status: "published",
      published_at: "2026-11-24T12:00:00Z",
      public_url_path: "/s/riya-women-salon",
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("switches templates in draft without resetting branding, opens full preview, and publishes", async () => {
    render(
      <BookingWebsiteWorkspace
        accessToken="jwt-token"
        organizationId={baseConfig.organization_id}
        organizationName="Riya Women Salon"
        isOwnerOrAdmin={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("website-nav-templates")).toBeTruthy();
    });

    // Open Website Templates gallery
    fireEvent.click(screen.getByTestId("website-nav-templates"));
    expect(screen.getByTestId("template-gallery")).toBeTruthy();

    // All 8 template cards are rendered
    for (const id of APPROVED_TEMPLATE_IDS) {
      expect(screen.getByTestId(`template-card-${id}`)).toBeTruthy();
    }

    // Preview Organic Glow in full-page preview modal
    fireEvent.click(screen.getByTestId("preview-template-organic_glow"));
    expect(screen.getByTestId("template-full-preview-modal")).toBeTruthy();
    expect(screen.getByTestId("template-organic_glow")).toBeTruthy();
    fireEvent.click(screen.getByTestId("close-template-preview-button"));

    // Select Organic Glow template -> persists as draft
    fireEvent.click(screen.getByTestId("select-template-organic_glow"));
    await waitFor(() => {
      expect(api.saveBookingWebsiteDraft).toHaveBeenCalledWith(
        "jwt-token",
        baseConfig.organization_id,
        { template_id: "organic_glow" }
      );
    });

    // Publish website from Overview
    fireEvent.click(screen.getByTestId("website-nav-overview"));
    fireEvent.click(screen.getByTestId("overview-publish-button"));
    await waitFor(() => {
      expect(api.publishBookingWebsite).toHaveBeenCalledWith(
        "jwt-token",
        baseConfig.organization_id
      );
      expect(screen.getByTestId("website-status-badge").textContent).toContain("published");
      expect(screen.getByTestId("overview-public-url-link")).toBeTruthy();
    });
  });
});
