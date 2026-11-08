"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { Session, User } from "@supabase/supabase-js";
import {
  createOrganizationApi,
  fetchUserOrganizations,
  fetchVerifiedAuthMe,
} from "@/lib/api";
import {
  getSupabaseBrowserClient,
  isSupabaseConfigured,
} from "@/lib/supabase/client";
import type {
  CreateOrganizationPayload,
  OrganizationSummary,
  VerifiedBackendUser,
} from "@/types/platform";

const ACTIVE_ORG_STORAGE_KEY = "svario.active_organization_id";

export interface AuthOrganizationContextValue {
  isInitializing: boolean;
  isLoadingOrganizations: boolean;
  supabaseConfigured: boolean;
  session: Session | null;
  supabaseUser: User | null;
  verifiedBackendUser: VerifiedBackendUser | null;
  backendAuthError: string | null;
  organizations: OrganizationSummary[];
  activeOrganization: OrganizationSummary | null;
  setActiveOrganizationId: (organizationId: string) => void;
  refreshOrganizations: () => Promise<void>;
  createOrganization: (
    payload: CreateOrganizationPayload
  ) => Promise<OrganizationSummary>;
  signOut: () => Promise<void>;
}

export const AuthOrganizationContext =
  createContext<AuthOrganizationContextValue | null>(null);

interface AuthOrganizationProviderProps {
  children: React.ReactNode;
}

export function AuthOrganizationProvider({
  children,
}: AuthOrganizationProviderProps): React.JSX.Element {
  const [isInitializing, setIsInitializing] = useState<boolean>(true);
  const [isLoadingOrganizations, setIsLoadingOrganizations] =
    useState<boolean>(false);
  const [session, setSession] = useState<Session | null>(null);
  const [supabaseUser, setSupabaseUser] = useState<User | null>(null);
  const [verifiedBackendUser, setVerifiedBackendUser] =
    useState<VerifiedBackendUser | null>(null);
  const [backendAuthError, setBackendAuthError] = useState<string | null>(null);
  const [organizations, setOrganizations] = useState<OrganizationSummary[]>([]);
  const [activeOrgId, setActiveOrgIdState] = useState<string | null>(null);

  const supabaseConfigured = isSupabaseConfigured();

  const resolveActiveOrgId = useCallback(
    (orgs: OrganizationSummary[], preferredId?: string | null): string | null => {
      if (orgs.length === 0) {
        return null;
      }
      if (preferredId && orgs.some((o) => o.id === preferredId)) {
        return preferredId;
      }
      if (typeof window !== "undefined") {
        const stored = window.localStorage.getItem(ACTIVE_ORG_STORAGE_KEY);
        if (stored && orgs.some((o) => o.id === stored)) {
          return stored;
        }
      }
      return orgs[0].id;
    },
    []
  );

  const setActiveOrganizationId = useCallback((organizationId: string) => {
    setActiveOrgIdState(organizationId);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(ACTIVE_ORG_STORAGE_KEY, organizationId);
    }
  }, []);

  const syncBackendIdentityAndOrganizations = useCallback(
    async (activeSession: Session | null) => {
      if (!activeSession?.access_token) {
        setVerifiedBackendUser(null);
        setBackendAuthError(null);
        setOrganizations([]);
        setActiveOrgIdState(null);
        return;
      }

      setIsLoadingOrganizations(true);
      setBackendAuthError(null);

      try {
        const [verifiedUser, userOrgs] = await Promise.all([
          fetchVerifiedAuthMe(activeSession.access_token),
          fetchUserOrganizations(activeSession.access_token),
        ]);
        setVerifiedBackendUser(verifiedUser);
        setOrganizations(userOrgs);
        const resolvedId = resolveActiveOrgId(userOrgs);
        setActiveOrgIdState(resolvedId);
        if (resolvedId && typeof window !== "undefined") {
          window.localStorage.setItem(ACTIVE_ORG_STORAGE_KEY, resolvedId);
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error
            ? err.message
            : "Backend JWT verification failed.";
        setBackendAuthError(message);
        setVerifiedBackendUser(null);
        setOrganizations([]);
        setActiveOrgIdState(null);
      } finally {
        setIsLoadingOrganizations(false);
      }
    },
    [resolveActiveOrgId]
  );

  useEffect(() => {
    if (!supabaseConfigured) {
      setIsInitializing(false);
      return;
    }

    const supabase = getSupabaseBrowserClient();
    let mounted = true;

    async function initializeAuth() {
      try {
        const { data, error } = await supabase.auth.getSession();
        if (!mounted) return;
        if (error) {
          setSession(null);
          setSupabaseUser(null);
        } else {
          setSession(data.session);
          setSupabaseUser(data.session?.user ?? null);
          if (data.session) {
            await syncBackendIdentityAndOrganizations(data.session);
          }
        }
      } finally {
        if (mounted) {
          setIsInitializing(false);
        }
      }
    }

    void initializeAuth();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (!mounted) return;
      setSession(nextSession);
      setSupabaseUser(nextSession?.user ?? null);
      void syncBackendIdentityAndOrganizations(nextSession);
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, [supabaseConfigured, syncBackendIdentityAndOrganizations]);

  const refreshOrganizations = useCallback(async () => {
    if (!session?.access_token) {
      return;
    }
    await syncBackendIdentityAndOrganizations(session);
  }, [session, syncBackendIdentityAndOrganizations]);

  const createOrganization = useCallback(
    async (payload: CreateOrganizationPayload): Promise<OrganizationSummary> => {
      if (!session?.access_token) {
        throw new Error("You must be authenticated to create an organization.");
      }
      const created = await createOrganizationApi(
        session.access_token,
        payload
      );
      setOrganizations((prev) => {
        const next = [...prev, created];
        return next;
      });
      setActiveOrganizationId(created.id);
      return created;
    },
    [session, setActiveOrganizationId]
  );

  const signOut = useCallback(async () => {
    if (supabaseConfigured) {
      const supabase = getSupabaseBrowserClient();
      await supabase.auth.signOut();
    }
    setSession(null);
    setSupabaseUser(null);
    setVerifiedBackendUser(null);
    setOrganizations([]);
    setActiveOrgIdState(null);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(ACTIVE_ORG_STORAGE_KEY);
    }
  }, [supabaseConfigured]);

  const activeOrganization = useMemo(() => {
    if (!activeOrgId) return organizations[0] ?? null;
    return (
      organizations.find((org) => org.id === activeOrgId) ??
      organizations[0] ??
      null
    );
  }, [organizations, activeOrgId]);

  const value = useMemo<AuthOrganizationContextValue>(
    () => ({
      isInitializing,
      isLoadingOrganizations,
      supabaseConfigured,
      session,
      supabaseUser,
      verifiedBackendUser,
      backendAuthError,
      organizations,
      activeOrganization,
      setActiveOrganizationId,
      refreshOrganizations,
      createOrganization,
      signOut,
    }),
    [
      isInitializing,
      isLoadingOrganizations,
      supabaseConfigured,
      session,
      supabaseUser,
      verifiedBackendUser,
      backendAuthError,
      organizations,
      activeOrganization,
      setActiveOrganizationId,
      refreshOrganizations,
      createOrganization,
      signOut,
    ]
  );

  return (
    <AuthOrganizationContext.Provider value={value}>
      {children}
    </AuthOrganizationContext.Provider>
  );
}

export function useAuthOrganization(): AuthOrganizationContextValue {
  const ctx = useContext(AuthOrganizationContext);
  if (!ctx) {
    throw new Error(
      "useAuthOrganization must be used within an AuthOrganizationProvider"
    );
  }
  return ctx;
}
