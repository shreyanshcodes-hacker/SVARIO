import React from "react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import DashboardPage from "@/app/dashboard/page";
import OnboardingPage from "@/app/onboarding/page";
import {
  AuthOrganizationContext,
  type AuthOrganizationContextValue,
} from "@/context/AuthOrganizationContext";
import type { OnboardingBundleData, OrganizationSummary } from "@/types/platform";
import type { Session, User } from "@supabase/supabase-js";
import * as api from "@/lib/api";

const replaceMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
    push: pushMock,
  }),
}));

const sampleOrg: OrganizationSummary = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Aura Clinic Center",
  slug: "aura-clinic-center",
  industry: "clinic",
  membership_role: "owner",
  created_at: "2026-11-08T10:00:00Z",
  updated_at: "2026-11-08T10:00:00Z",
};

const businessId = "bbbbbbbb-1111-4111-8111-111111111111";

function buildSampleBundle(
  overrides: Partial<OnboardingBundleData> = {}
): OnboardingBundleData {
  return {
    organization: {
      ...sampleOrg,
      member_count: 1,
    },
    business_id: businessId,
    profile: {
      id: "pppppppp-1111-4111-8111-111111111111",
      organization_id: sampleOrg.id,
      business_id: businessId,
      display_name: "Aura Multi-Specialty Clinic",
      description: "Administrative clinic reception",
      phone: "+91 9876543210",
      email: "desk@auraclinic.in",
      website: "https://auraclinic.in",
      address: "12 MG Road",
      city: "Bengaluru",
      state: "Karnataka",
      country: "India",
      postal_code: "560001",
      timezone: "Asia/Kolkata",
      created_at: "2026-11-08T10:00:00Z",
      updated_at: "2026-11-08T10:00:00Z",
    },
    hours: {
      organization_id: sampleOrg.id,
      business_id: businessId,
      timezone: "Asia/Kolkata",
      schedule: [
        {
          weekday: 0,
          is_closed: true,
          opens_at: null,
          closes_at: null,
          is_overnight: false,
        },
        {
          weekday: 1,
          is_closed: false,
          opens_at: "09:00",
          closes_at: "18:00",
          is_overnight: false,
        },
        {
          weekday: 2,
          is_closed: false,
          opens_at: "09:00",
          closes_at: "18:00",
          is_overnight: false,
        },
        {
          weekday: 3,
          is_closed: false,
          opens_at: "09:00",
          closes_at: "18:00",
          is_overnight: false,
        },
        {
          weekday: 4,
          is_closed: false,
          opens_at: "09:00",
          closes_at: "18:00",
          is_overnight: false,
        },
        {
          weekday: 5,
          is_closed: false,
          opens_at: "09:00",
          closes_at: "18:00",
          is_overnight: false,
        },
        {
          weekday: 6,
          is_closed: false,
          opens_at: "10:00",
          closes_at: "16:00",
          is_overnight: false,
        },
      ],
    },
    languages: {
      organization_id: sampleOrg.id,
      business_id: businessId,
      primary_language: "en",
      supported_languages: ["en", "hi"],
      entries: [
        {
          id: "l1",
          organization_id: sampleOrg.id,
          business_id: businessId,
          language_code: "en",
          is_primary: true,
          created_at: "2026-11-08T10:00:00Z",
        },
        {
          id: "l2",
          organization_id: sampleOrg.id,
          business_id: businessId,
          language_code: "hi",
          is_primary: false,
          created_at: "2026-11-08T10:00:00Z",
        },
      ],
    },
    assistant: {
      id: "aaaaaaaa-1111-4111-8111-111111111111",
      organization_id: sampleOrg.id,
      business_id: businessId,
      assistant_name: "Meera",
      greeting: "Hello! Thank you for calling Aura Multi-Specialty Clinic.",
      personality: "warm",
      response_style: "balanced",
      enabled: true,
      created_at: "2026-11-08T10:00:00Z",
      updated_at: "2026-11-08T10:00:00Z",
    },
    faqs: [
      {
        id: "ffffffff-1111-4111-8111-111111111111",
        organization_id: sampleOrg.id,
        business_id: businessId,
        question: "What are your consultation hours?",
        answer: "Monday to Saturday 9 AM to 6 PM.",
        category: "hours",
        is_active: true,
        sort_order: 0,
        created_at: "2026-11-08T10:00:00Z",
        updated_at: "2026-11-08T10:00:00Z",
      },
    ],
    faq_templates: [
      {
        industry: "clinic",
        question: "What are your clinic hours?",
        answer_placeholder: "Enter clinic hours...",
        category: "hours",
      },
    ],
    escalation: {
      id: "eeeeeeee-1111-4111-8111-111111111111",
      organization_id: sampleOrg.id,
      business_id: businessId,
      enabled: true,
      contact_name: "Front Desk Coordinator",
      contact_email: "coordinator@auraclinic.in",
      contact_phone: "+91 9876500000",
      escalation_instructions: "Transfer urgent queries to reception.",
      preferred_method: "phone",
      created_at: "2026-11-08T10:00:00Z",
      updated_at: "2026-11-08T10:00:00Z",
    },
    progress: {
      id: "prprprpr-1111-4111-8111-111111111111",
      organization_id: sampleOrg.id,
      business_id: businessId,
      current_step: "industry",
      completed_steps: ["industry"],
      is_completed: false,
      completed_at: null,
      created_at: "2026-11-08T10:00:00Z",
      updated_at: "2026-11-08T10:00:00Z",
    },
    healthcare_safeguards: {
      applies_to_healthcare: true,
      administrative_only: true,
      prohibited_actions: [
        "No medical diagnosis",
        "No prescription advice",
        "No treatment recommendations",
        "No clinical decision-making",
      ],
      emergency_directive:
        "Medical emergencies must immediately be directed to emergency services or hospital emergency contacts.",
    },
    ...overrides,
  };
}

function buildAuthenticatedContext(
  overrides: Partial<AuthOrganizationContextValue> = {}
): AuthOrganizationContextValue {
  return {
    isInitializing: false,
    isLoadingOrganizations: false,
    supabaseConfigured: true,
    session: { access_token: "stage2-jwt-token" } as Session,
    supabaseUser: {
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      email: "founder@auraclinic.in",
    } as User,
    verifiedBackendUser: {
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      email: "founder@auraclinic.in",
      role: "authenticated",
      session_id: "sess-stage2",
      full_name: "Dr. Rohan Mehta",
      email_verified: true,
      issuer: "https://test.supabase.co/auth/v1",
      audience: "authenticated",
    },
    backendAuthError: null,
    organizations: [sampleOrg],
    activeOrganization: sampleOrg,
    setActiveOrganizationId: vi.fn(),
    refreshOrganizations: vi.fn().mockResolvedValue(undefined),
    createOrganization: vi.fn(),
    signOut: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

describe("SVARIO Stage 2 — Onboarding Wizard & Dashboard Integration", () => {
  beforeEach(() => {
    replaceMock.mockReset();
    pushMock.mockReset();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("loads onboarding wizard on /onboarding, supports industry selection, and saves progress for continue-later", async () => {
    const bundle = buildSampleBundle();
    vi.spyOn(api, "fetchOnboardingBundle").mockResolvedValue(bundle);
    const updateIndustrySpy = vi
      .spyOn(api, "updateOnboardingIndustry")
      .mockResolvedValue({
        ...bundle.organization,
        industry: "hospital",
      });
    const updateProgressSpy = vi
      .spyOn(api, "updateOnboardingProgressApi")
      .mockResolvedValue(bundle.progress);

    render(
      <AuthOrganizationContext.Provider value={buildAuthenticatedContext()}>
        <OnboardingPage />
      </AuthOrganizationContext.Provider>
    );

    await waitFor(() => {
      expect(
        screen.getByText(/1\. Industry Selection & Domain Alignment/i)
      ).toBeTruthy();
    });

    // Select Hospital industry card and save & next
    fireEvent.click(screen.getByText("Hospital"));
    fireEvent.click(screen.getByText(/Save & Next/i));

    await waitFor(() => {
      expect(updateIndustrySpy).toHaveBeenCalledWith(
        "stage2-jwt-token",
        sampleOrg.id,
        "hospital"
      );
    });

    // Click Save & Continue Later on Step 2 and verify redirect to /dashboard
    vi.spyOn(api, "updateBusinessProfileApi").mockResolvedValue(bundle.profile);
    fireEvent.click(screen.getByText("Save & Continue Later"));
    await waitFor(() => {
      expect(updateProgressSpy).toHaveBeenCalled();
      expect(pushMock).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("validates business profile required display_name before calling backend API", async () => {
    const bundle = buildSampleBundle({
      progress: {
        ...buildSampleBundle().progress,
        current_step: "profile",
        completed_steps: ["industry"],
        is_completed: false,
      },
      profile: {
        ...buildSampleBundle().profile,
        display_name: "",
      },
    });
    vi.spyOn(api, "fetchOnboardingBundle").mockResolvedValue(bundle);
    const updateProfileSpy = vi.spyOn(api, "updateBusinessProfileApi");

    render(
      <AuthOrganizationContext.Provider value={buildAuthenticatedContext()}>
        <OnboardingPage />
      </AuthOrganizationContext.Provider>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Business Name \*/i)).toBeTruthy();
    });

    const nameInput = screen.getByLabelText(
      /Business Name \*/i
    ) as HTMLInputElement;
    fireEvent.change(nameInput, { target: { value: "A" } });
    fireEvent.click(screen.getByText(/Save & Next/i));

    await waitFor(() => {
      expect(
        screen.getByText(/Business name must be at least 2 characters/i)
      ).toBeTruthy();
    });
    expect(updateProfileSpy).not.toHaveBeenCalled();
  });

  it("completes onboarding from review step and redirects to /dashboard", async () => {
    const bundle = buildSampleBundle({
      progress: {
        ...buildSampleBundle().progress,
        current_step: "review",
        completed_steps: [
          "industry",
          "profile",
          "hours",
          "languages",
          "assistant",
          "faqs",
          "escalation",
        ],
        is_completed: false,
      },
    });
    vi.spyOn(api, "fetchOnboardingBundle").mockResolvedValue(bundle);
    const updateProgressSpy = vi
      .spyOn(api, "updateOnboardingProgressApi")
      .mockResolvedValue({
        ...bundle.progress,
        current_step: "review",
        completed_steps: [
          "industry",
          "profile",
          "hours",
          "languages",
          "assistant",
          "faqs",
          "escalation",
          "review",
        ],
        is_completed: true,
        completed_at: "2026-11-08T12:00:00Z",
      });

    render(
      <AuthOrganizationContext.Provider value={buildAuthenticatedContext()}>
        <OnboardingPage />
      </AuthOrganizationContext.Provider>
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Complete Onboarding/i })
      ).toBeTruthy();
    });

    fireEvent.click(
      screen.getByRole("button", { name: /Complete Onboarding/i })
    );

    await waitFor(() => {
      expect(updateProgressSpy).toHaveBeenCalledWith(
        "stage2-jwt-token",
        sampleOrg.id,
        expect.objectContaining({
          current_step: "review",
          is_completed: true,
        })
      );
      expect(pushMock).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("displays Stage 2 business onboarding summary, hours, languages, assistant status, and edit link on /dashboard", async () => {
    const completedBundle = buildSampleBundle({
      progress: {
        ...buildSampleBundle().progress,
        current_step: "review",
        completed_steps: [
          "industry",
          "profile",
          "hours",
          "languages",
          "assistant",
          "faqs",
          "escalation",
          "review",
        ],
        is_completed: true,
        completed_at: "2026-11-08T12:00:00Z",
      },
    });
    vi.spyOn(api, "fetchOnboardingBundle").mockResolvedValue(completedBundle);

    render(
      <AuthOrganizationContext.Provider value={buildAuthenticatedContext()}>
        <DashboardPage />
      </AuthOrganizationContext.Provider>
    );

    await waitFor(() => {
      expect(screen.getByText("Aura Multi-Specialty Clinic")).toBeTruthy();
    });

    expect(screen.getByText("Onboarding Completed")).toBeTruthy();
    expect(screen.getByText("6 Active Days / Week")).toBeTruthy();
    expect(screen.getByText("English (Primary)")).toBeTruthy();
    expect(screen.getByText("Hindi")).toBeTruthy();
    expect(screen.getByText("Meera")).toBeTruthy();
    expect(
      screen.getByText("Edit Business Settings")
    ).toBeTruthy();
  });
});
