import React from "react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { BookingWebsiteWorkspace } from "@/components/website/BookingWebsiteWorkspace";
import * as api from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    fetchBookingWebsiteConfig: vi.fn(),
    fetchOnboardingBundle: vi.fn(),
    fetchSalonServices: vi.fn(),
    checkBookingWebsiteSlug: vi.fn(),
    saveBookingWebsiteDraft: vi.fn(),
  };
});

const mockConfig = {
  id: "11111111-1111-4111-8111-111111111111",
  organization_id: "8867eb36-95c3-4d87-b91f-a9e23f21c88b",
  business_id: "1962bebf-c4b2-4a56-a79e-963f8bd7e334",
  slug: "royal-beauty-studio",
  template_id: "luxe_studio" as const,
  status: "draft" as const,
  published_at: null,
  headline: "Book your visit at Royal Beauty Studio",
  tagline: "Premium hair and skin care.",
  logo_path: null,
  logo_url: null,
  cover_image_path: null,
  cover_image_url: null,
  primary_color: "#7657F6",
  secondary_color: "#36C6D3",
  accent_color: "#F59E0B",
  background_color: "#0B1020",
  text_color: "#F5F7FC",
  theme: "dark" as const,
  font_family: "inter" as const,
  button_style: "rounded" as const,
  social_instagram: null,
  social_facebook: null,
  social_whatsapp: null,
  show_services: true,
  show_hours: true,
  show_ai_receptionist: true,
  preview_url_path: "/s/royal-beauty-studio",
  public_url_path: null,
  publish_readiness: {
    is_valid: true,
    public_engine_ready: false,
    can_publish: false,
    missing_requirements: [],
    stage_notice: "Stage 1 Foundation: Public website engine pending Stage 2.",
  },
  created_at: "2026-11-24T10:00:00Z",
  updated_at: "2026-11-24T10:00:00Z",
};

const mockBundle = {
  organization: {
    id: mockConfig.organization_id,
    name: "Royal Beauty Studio",
    slug: "royal-beauty-studio",
    industry: "salon" as const,
    membership_role: "owner" as const,
    member_count: 1,
    created_at: "2026-11-24T10:00:00Z",
    updated_at: "2026-11-24T10:00:00Z",
  },
  business_id: mockConfig.business_id,
  profile: {
    id: "22222222-2222-4222-8222-222222222222",
    organization_id: mockConfig.organization_id,
    business_id: mockConfig.business_id,
    display_name: "Royal Beauty Studio",
    description: "Luxury salon",
    phone: "+919876543210",
    email: "hello@royalbeauty.example",
    website: null,
    address: "12 Park Street",
    city: "Mumbai",
    state: null,
    country: "India",
    postal_code: null,
    timezone: "Asia/Kolkata",
    created_at: "2026-11-24T10:00:00Z",
    updated_at: "2026-11-24T10:00:00Z",
  },
  hours: {
    organization_id: mockConfig.organization_id,
    business_id: mockConfig.business_id,
    timezone: "Asia/Kolkata",
    schedule: [
      { weekday: 1, is_closed: false, opens_at: "09:00", closes_at: "18:00", is_overnight: false },
    ],
  },
  languages: {
    organization_id: mockConfig.organization_id,
    business_id: mockConfig.business_id,
    primary_language: "en" as const,
    supported_languages: ["en" as const, "hinglish" as const],
    entries: [],
  },
  assistant: {
    id: "33333333-3333-4333-8333-333333333333",
    organization_id: mockConfig.organization_id,
    business_id: mockConfig.business_id,
    assistant_name: "Aria",
    greeting: "Welcome to Royal Beauty Studio!",
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
    organization_id: mockConfig.organization_id,
    business_id: mockConfig.business_id,
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
    organization_id: mockConfig.organization_id,
    business_id: mockConfig.business_id,
    current_step: "review" as const,
    completed_steps: [],
    is_completed: true,
    completed_at: "2026-11-24T10:00:00Z",
    created_at: "2026-11-24T10:00:00Z",
    updated_at: "2026-11-24T10:00:00Z",
  },
};

describe("Stage 1 — Booking Website Dashboard Foundation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchBookingWebsiteConfig).mockResolvedValue(mockConfig);
    vi.mocked(api.fetchOnboardingBundle).mockResolvedValue(mockBundle);
    vi.mocked(api.fetchSalonServices).mockResolvedValue([]);
    vi.mocked(api.checkBookingWebsiteSlug).mockResolvedValue({
      requested_slug: "glow-and-shine",
      normalized_slug: "glow-and-shine",
      available: true,
      reason: null,
    });
    vi.mocked(api.saveBookingWebsiteDraft).mockResolvedValue({
      ...mockConfig,
      slug: "glow-and-shine",
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders Website Overview with guarded Publish button, Brand Studio live preview, and slug check", async () => {
    render(
      <BookingWebsiteWorkspace
        accessToken="jwt-token"
        organizationId={mockConfig.organization_id}
        organizationName="Royal Beauty Studio"
        isOwnerOrAdmin={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("website-status-badge").textContent).toContain("draft");
    });

    // Publish button is safely disabled in Stage 1
    expect(
      (screen.getByTestId("overview-publish-button") as HTMLButtonElement).disabled
    ).toBe(true);

    // Brand Studio renders live preview
    fireEvent.click(screen.getByTestId("website-nav-brand"));
    expect(screen.getByTestId("booking-website-live-preview").textContent).toContain(
      "Royal Beauty Studio"
    );

    // Website URL slug availability check
    fireEvent.click(screen.getByTestId("website-nav-url"));
    fireEvent.change(screen.getByTestId("website-slug-input"), {
      target: { value: "glow-and-shine" },
    });
    fireEvent.click(screen.getByTestId("check-slug-button"));

    await waitFor(() => {
      expect(screen.getByTestId("slug-check-result").textContent).toContain(
        "/s/glow-and-shine"
      );
    });
  });
});
