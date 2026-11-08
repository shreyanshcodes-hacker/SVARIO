import React from "react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import LoginPage from "@/app/login/page";
import SignupPage from "@/app/signup/page";
import DashboardPage from "@/app/dashboard/page";
import {
  AuthOrganizationContext,
  type AuthOrganizationContextValue,
} from "@/context/AuthOrganizationContext";
import type { Session, User } from "@supabase/supabase-js";

const replaceMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
    push: pushMock,
  }),
}));

function buildContextValue(
  overrides: Partial<AuthOrganizationContextValue> = {}
): AuthOrganizationContextValue {
  return {
    isInitializing: false,
    isLoadingOrganizations: false,
    supabaseConfigured: true,
    session: null,
    supabaseUser: null,
    verifiedBackendUser: null,
    backendAuthError: null,
    organizations: [],
    activeOrganization: null,
    setActiveOrganizationId: vi.fn(),
    refreshOrganizations: vi.fn().mockResolvedValue(undefined),
    createOrganization: vi.fn(),
    signOut: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

describe("SVARIO Stage 1 — Frontend Auth & Organization Experience", () => {
  beforeEach(() => {
    replaceMock.mockReset();
    pushMock.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders the Login page with email and password inputs", () => {
    render(<LoginPage />);
    expect(
      screen.getByRole("heading", { name: "Sign In to Svario" })
    ).toBeTruthy();
    expect(screen.getByLabelText(/Email Address/i)).toBeTruthy();
    expect(screen.getByLabelText(/Password/i)).toBeTruthy();
  });

  it("renders the Signup page with full name, email, and password fields", () => {
    render(<SignupPage />);
    expect(screen.getByText("Create Your Svario Account")).toBeTruthy();
    expect(screen.getByLabelText(/Full Name/i)).toBeTruthy();
    expect(screen.getByLabelText(/Work Email/i)).toBeTruthy();
  });

  it("redirects unauthenticated users away from /dashboard to /login", () => {
    const unauthContext = buildContextValue({
      isInitializing: false,
      session: null,
      supabaseUser: null,
      verifiedBackendUser: null,
      organizations: [],
    });

    render(
      <AuthOrganizationContext.Provider value={unauthContext}>
        <DashboardPage />
      </AuthOrganizationContext.Provider>
    );

    expect(replaceMock).toHaveBeenCalledWith("/login");
    expect(
      screen.getByText(/Redirecting unauthenticated user to \/login/i)
    ).toBeTruthy();
  });

  it("loads authenticated user and active organization context on /dashboard and supports switching", () => {
    const setActiveOrganizationId = vi.fn();
    const orgSalon = {
      id: "11111111-1111-4111-8111-111111111111",
      name: "Lumiere Salon Studio",
      slug: "lumiere-salon-studio",
      industry: "salon" as const,
      membership_role: "owner" as const,
      created_at: "2026-11-03T10:00:00Z",
      updated_at: "2026-11-03T10:00:00Z",
    };
    const orgClinic = {
      id: "22222222-2222-4222-8222-222222222222",
      name: "Apex Care Clinic",
      slug: "apex-care-clinic",
      industry: "clinic" as const,
      membership_role: "admin" as const,
      created_at: "2026-11-03T11:00:00Z",
      updated_at: "2026-11-03T11:00:00Z",
    };

    const authContext = buildContextValue({
      isInitializing: false,
      session: { access_token: "test-jwt-token" } as Session,
      supabaseUser: {
        id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        email: "operator@svario.ai",
      } as User,
      verifiedBackendUser: {
        id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        email: "operator@svario.ai",
        role: "authenticated",
        session_id: "sess-1",
        full_name: "Ananya Rao",
        email_verified: true,
        issuer: "https://test.supabase.co/auth/v1",
        audience: "authenticated",
      },
      organizations: [orgSalon, orgClinic],
      activeOrganization: orgSalon,
      setActiveOrganizationId,
    });

    render(
      <AuthOrganizationContext.Provider value={authContext}>
        <DashboardPage />
      </AuthOrganizationContext.Provider>
    );

    expect(replaceMock).not.toHaveBeenCalled();
    expect(screen.getByText("Ananya Rao")).toBeTruthy();
    expect(screen.getByText("operator@svario.ai")).toBeTruthy();
    expect(screen.getAllByText("Lumiere Salon Studio").length).toBeGreaterThan(0);
    expect(screen.getByText("Verified by FastAPI JWT")).toBeTruthy();

    // Switch organization using the OrganizationSwitcher dropdown
    const switcher = screen.getByLabelText(
      /Select Active Organization/i
    ) as HTMLSelectElement;
    fireEvent.change(switcher, { target: { value: orgClinic.id } });
    expect(setActiveOrganizationId).toHaveBeenCalledWith(orgClinic.id);
  });

  it("shows organization onboarding form when authenticated user has zero organizations (no fake data)", () => {
    const emptyOrgAuthContext = buildContextValue({
      isInitializing: false,
      session: { access_token: "test-jwt-token" } as Session,
      supabaseUser: {
        id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        email: "newfounder@svario.ai",
      } as User,
      verifiedBackendUser: {
        id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        email: "newfounder@svario.ai",
        role: "authenticated",
        session_id: "sess-2",
        full_name: "Vikram Sen",
        email_verified: true,
        issuer: "https://test.supabase.co/auth/v1",
        audience: "authenticated",
      },
      organizations: [],
      activeOrganization: null,
    });

    render(
      <AuthOrganizationContext.Provider value={emptyOrgAuthContext}>
        <DashboardPage />
      </AuthOrganizationContext.Provider>
    );

    expect(screen.getByText("Create Your Organization")).toBeTruthy();
    expect(screen.getByLabelText(/Organization Name/i)).toBeTruthy();
    expect(screen.getByText("Salon")).toBeTruthy();
    expect(screen.getByText("Clinic")).toBeTruthy();
    expect(screen.getByText("Hospital")).toBeTruthy();
  });
});
