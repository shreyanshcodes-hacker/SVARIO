import React from "react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import DashboardPage from "@/app/dashboard/page";
import BookingWebsiteDashboardPage from "@/app/dashboard/booking-website/page";
import OnboardingPage from "@/app/onboarding/page";
import {
  AuthOrganizationContext,
  AuthOrganizationProvider,
  useAuthOrganization,
  type AuthOrganizationContextValue,
} from "@/context/AuthOrganizationContext";
import * as api from "@/lib/api";
import * as supabaseClient from "@/lib/supabase/client";
import type { OrganizationSummary } from "@/types/platform";
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

const mockUser = {
  id: "user-123",
  email: "owner@shreyansh.salon",
} as unknown as User;

const mockSession = {
  access_token: "token-abc",
  user: mockUser,
} as unknown as Session;

function AuthProbe() {
  const { isInitializing, isLoadingOrganizations, session, organizations } =
    useAuthOrganization();
  return (
    <div>
      <span data-testid="init">{String(isInitializing)}</span>
      <span data-testid="loading-orgs">{String(isLoadingOrganizations)}</span>
      <span data-testid="has-session">{String(Boolean(session))}</span>
      <span data-testid="org-count">{organizations.length}</span>
    </div>
  );
}

describe("SVARIO Loading Experience Optimization", () => {
  beforeEach(() => {
    replaceMock.mockReset();
    pushMock.mockReset();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders lightweight skeleton instead of blocking splash while auth initializes", () => {
    render(
      <AuthOrganizationContext.Provider
        value={buildContextValue({ isInitializing: true })}
      >
        <DashboardPage />
      </AuthOrganizationContext.Provider>
    );

    expect(screen.getByRole("status", { name: /Checking session/i })).toBeTruthy();
    expect(screen.queryByText(/Restoring authenticated Svario session/i)).toBeNull();
    expect(screen.queryByText(/Shreyansh salon/i)).toBeNull();
  });

  it("redirects unauthenticated user to /login without exposing org data", async () => {
    render(
      <AuthOrganizationContext.Provider
        value={buildContextValue({ isInitializing: false, session: null })}
      >
        <DashboardPage />
      </AuthOrganizationContext.Provider>
    );

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/login");
    });
    expect(screen.getByText(/Redirecting unauthenticated user to \/login/i)).toBeTruthy();
  });

  it("renders skeleton placeholders on /onboarding and /dashboard/booking-website during initialization", () => {
    render(
      <AuthOrganizationContext.Provider
        value={buildContextValue({ isInitializing: true })}
      >
        <OnboardingPage />
      </AuthOrganizationContext.Provider>
    );
    expect(screen.getByRole("status", { name: /Checking session/i })).toBeTruthy();
    cleanup();

    render(
      <AuthOrganizationContext.Provider
        value={buildContextValue({ isInitializing: true })}
      >
        <BookingWebsiteDashboardPage />
      </AuthOrganizationContext.Provider>
    );
    expect(
      screen.getByRole("status", {
        name: /Loading Booking Website Studio configuration/i,
      })
    ).toBeTruthy();
  });

  it("does not block AuthOrganizationProvider initialization behind slow backend API calls", async () => {
    let resolveOrgs!: (value: OrganizationSummary[]) => void;
    const pendingOrgs = new Promise<OrganizationSummary[]>((resolve) => {
      resolveOrgs = resolve;
    });

    vi.spyOn(supabaseClient, "isSupabaseConfigured").mockReturnValue(true);
    vi.spyOn(supabaseClient, "getSupabaseBrowserClient").mockReturnValue({
      auth: {
        getSession: vi.fn().mockResolvedValue({
          data: { session: mockSession },
          error: null,
        }),
        onAuthStateChange: vi.fn().mockReturnValue({
          data: { subscription: { unsubscribe: vi.fn() } },
        }),
      },
    } as unknown as ReturnType<typeof supabaseClient.getSupabaseBrowserClient>);

    vi.spyOn(api, "fetchVerifiedAuthMe").mockResolvedValue({
      id: "user-123",
      email: "owner@shreyansh.salon",
      role: "authenticated",
      session_id: "sess-123",
      full_name: "Shreyansh",
      email_verified: true,
      issuer: "https://supabase.co/auth/v1",
      audience: "authenticated",
    });
    vi.spyOn(api, "fetchUserOrganizations").mockReturnValue(pendingOrgs);

    render(
      <AuthOrganizationProvider>
        <AuthProbe />
      </AuthOrganizationProvider>
    );

    // Initialization finishes immediately after getSession(), while orgs load progressively
    await waitFor(() => {
      expect(screen.getByTestId("init").textContent).toBe("false");
    });
    expect(screen.getByTestId("has-session").textContent).toBe("true");
    expect(screen.getByTestId("loading-orgs").textContent).toBe("true");
    expect(screen.getByTestId("org-count").textContent).toBe("0");

    // Once backend orgs resolve, state updates progressively
    resolveOrgs([
      {
        id: "org-1",
        name: "Shreyansh salon",
        slug: "shreyansh-salon",
        industry: "salon",
        membership_role: "owner",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]);

    await waitFor(() => {
      expect(screen.getByTestId("loading-orgs").textContent).toBe("false");
    });
    expect(screen.getByTestId("org-count").textContent).toBe("1");
  });

  it("clears session and marks initialization complete on expired/error session", async () => {
    vi.spyOn(supabaseClient, "isSupabaseConfigured").mockReturnValue(true);
    vi.spyOn(supabaseClient, "getSupabaseBrowserClient").mockReturnValue({
      auth: {
        getSession: vi.fn().mockResolvedValue({
          data: { session: null },
          error: new Error("Session expired"),
        }),
        onAuthStateChange: vi.fn().mockReturnValue({
          data: { subscription: { unsubscribe: vi.fn() } },
        }),
      },
    } as unknown as ReturnType<typeof supabaseClient.getSupabaseBrowserClient>);

    render(
      <AuthOrganizationProvider>
        <AuthProbe />
      </AuthOrganizationProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("init").textContent).toBe("false");
    });
    expect(screen.getByTestId("has-session").textContent).toBe("false");
    expect(screen.getByTestId("org-count").textContent).toBe("0");
  });

  it("renders dashboard workspace progressively with meaningful error when onboarding bundle fails", async () => {
    vi.spyOn(api, "fetchOnboardingBundle").mockRejectedValue(
      new Error("Network timeout loading bundle")
    );

    const org: OrganizationSummary = {
      id: "org-1",
      name: "Shreyansh salon",
      slug: "shreyansh-salon",
      industry: "salon",
      membership_role: "owner",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };

    render(
      <AuthOrganizationContext.Provider
        value={buildContextValue({
          session: mockSession,
          supabaseUser: mockUser,
          organizations: [org],
          activeOrganization: org,
        })}
      >
        <DashboardPage />
      </AuthOrganizationContext.Provider>
    );

    expect(screen.getByRole("heading", { name: "Shreyansh salon" })).toBeTruthy();
    await waitFor(() => {
      expect(
        screen.getByText(/Onboarding details note: Network timeout loading bundle/i)
      ).toBeTruthy();
    });
  });
});
