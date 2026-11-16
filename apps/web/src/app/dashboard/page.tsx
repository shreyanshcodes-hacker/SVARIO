"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SvarioLogoPlaceholder } from "@/components/SvarioLogoPlaceholder";
import { StageIndicatorBadge } from "@/components/StageIndicatorBadge";
import { OrganizationOnboardingForm } from "@/components/organizations/OrganizationOnboardingForm";
import { OrganizationSwitcher } from "@/components/organizations/OrganizationSwitcher";
import { useAuthOrganization } from "@/context/AuthOrganizationContext";
import { fetchOnboardingBundle } from "@/lib/api";
import { ClinicDashboardView } from "@/components/dashboard/ClinicDashboardView";
import { SalonDashboardView } from "@/components/dashboard/SalonDashboardView";
import type { OnboardingBundleData } from "@/types/platform";

const DAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const LANGUAGE_NAMES: Record<string, string> = {
  en: "English",
  hi: "Hindi",
  hinglish: "Hinglish",
};

export default function DashboardPage(): React.JSX.Element {
  const router = useRouter();
  const {
    isInitializing,
    isLoadingOrganizations,
    session,
    supabaseUser,
    verifiedBackendUser,
    backendAuthError,
    organizations,
    activeOrganization,
    signOut,
  } = useAuthOrganization();

  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [onboardingBundle, setOnboardingBundle] =
    useState<OnboardingBundleData | null>(null);
  const [isLoadingBundle, setIsLoadingBundle] = useState<boolean>(false);
  const [bundleError, setBundleError] = useState<string | null>(null);

  const isAuthenticated = Boolean(session && (supabaseUser || verifiedBackendUser));

  useEffect(() => {
    if (!isInitializing && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isInitializing, isAuthenticated, router]);

  useEffect(() => {
    let cancelled = false;
    async function loadBundle() {
      if (!session?.access_token || !activeOrganization?.id) {
        setOnboardingBundle(null);
        setBundleError(null);
        return;
      }
      setIsLoadingBundle(true);
      setBundleError(null);
      try {
        const bundle = await fetchOnboardingBundle(
          session.access_token,
          activeOrganization.id
        );
        if (!cancelled) {
          setOnboardingBundle(bundle);
        }
      } catch (err) {
        if (!cancelled) {
          setOnboardingBundle(null);
          setBundleError(
            err instanceof Error
              ? err.message
              : "Unable to load onboarding configuration."
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoadingBundle(false);
        }
      }
    }

    void loadBundle();
    return () => {
      cancelled = true;
    };
  }, [session?.access_token, activeOrganization?.id]);

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0B1020] text-[#F5F7FC]">
        <div
          role="status"
          className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 px-6 py-4 font-mono text-xs text-[#36C6D3]"
        >
          Restoring authenticated Svario session...
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0B1020] text-[#F5F7FC]">
        <div
          role="status"
          className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 px-6 py-4 font-mono text-xs text-[#A7B0C4]"
        >
          Redirecting unauthenticated user to /login...
        </div>
      </div>
    );
  }

  const displayEmail =
    verifiedBackendUser?.email ?? supabaseUser?.email ?? "Unavailable";
  const displayName =
    verifiedBackendUser?.full_name ??
    (typeof supabaseUser?.user_metadata?.full_name === "string"
      ? supabaseUser.user_metadata.full_name
      : null) ??
    "Svario Operator";
  const displayUserId = verifiedBackendUser?.id ?? supabaseUser?.id ?? "—";

  const isCompleted = Boolean(onboardingBundle?.progress?.is_completed);
  const completedStepsCount =
    onboardingBundle?.progress?.completed_steps?.length ?? 0;
  const scheduleList = onboardingBundle?.hours?.schedule ?? [];
  const openHoursList = scheduleList.filter((h) => !h.is_closed);

  return (
    <div className="min-h-screen bg-[#0B1020] text-[#F5F7FC]">
      <header className="border-b border-[#A7B0C4]/15 bg-[#0B1020]/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-4">
            <Link href="/">
              <SvarioLogoPlaceholder />
            </Link>
            <StageIndicatorBadge />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {activeOrganization && (
              <>
                <Link
                  href="/voice-test"
                  className="rounded-xl border border-[#36C6D3]/60 bg-[#36C6D3]/15 px-3.5 py-1.5 text-xs font-semibold text-[#36C6D3] transition hover:bg-[#36C6D3]/25"
                >
                  Voice Test Lab
                </Link>
                <Link
                  href="/onboarding"
                  className="rounded-xl border border-[#7657F6]/60 bg-[#7657F6]/20 px-3.5 py-1.5 text-xs font-semibold text-[#F5F7FC] transition hover:bg-[#7657F6]/35"
                >
                  {isCompleted ? "Edit Settings" : "Continue Onboarding"}
                </Link>
              </>
            )}
            <OrganizationSwitcher
              onNewOrganizationClick={() => setShowCreateModal(true)}
            />
            <button
              type="button"
              onClick={() => void signOut()}
              className="rounded-xl border border-rose-400/40 bg-rose-500/10 px-3.5 py-1.5 text-xs font-semibold text-rose-200 transition hover:bg-rose-500/20"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-8 px-6 py-10">
        {/* Top Status Overview */}
        <section
          aria-label="Operator and Organization Status"
          className="grid gap-5 md:grid-cols-2 lg:grid-cols-4"
        >
          <div className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-5">
            <div className="font-mono text-[11px] uppercase tracking-wider text-[#A7B0C4]">
              Logged-In User
            </div>
            <div className="mt-2 text-lg font-bold text-[#F5F7FC]">
              {displayName}
            </div>
            <div className="mt-0.5 text-xs text-[#36C6D3]">{displayEmail}</div>
            <div className="mt-2 truncate font-mono text-[10px] text-[#A7B0C4]">
              ID: {displayUserId}
            </div>
          </div>

          <div className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-5">
            <div className="font-mono text-[11px] uppercase tracking-wider text-[#A7B0C4]">
              Active Organization
            </div>
            <div className="mt-2 text-lg font-bold text-[#F5F7FC]">
              {activeOrganization ? activeOrganization.name : "None Selected"}
            </div>
            <div className="mt-0.5 font-mono text-xs text-[#A7B0C4]">
              {activeOrganization
                ? `slug: ${activeOrganization.slug}`
                : "Create an organization below"}
            </div>
          </div>

          <div className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-5">
            <div className="font-mono text-[11px] uppercase tracking-wider text-[#A7B0C4]">
              Industry & Role
            </div>
            <div className="mt-2 flex items-center gap-2">
              <span className="rounded-lg bg-[#7657F6]/25 px-2.5 py-1 font-mono text-xs font-bold uppercase text-[#F5F7FC]">
                {activeOrganization ? activeOrganization.industry : "Unassigned"}
              </span>
              {activeOrganization && (
                <span className="rounded-lg border border-[#36C6D3]/50 bg-[#36C6D3]/15 px-2.5 py-1 font-mono text-xs font-semibold uppercase text-[#36C6D3]">
                  {activeOrganization.membership_role}
                </span>
              )}
            </div>
            <div className="mt-2 text-xs text-[#A7B0C4]">
              Total memberships: {organizations.length}
            </div>
          </div>

          <div className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-5">
            <div className="font-mono text-[11px] uppercase tracking-wider text-[#A7B0C4]">
              Authentication Status
            </div>
            <div className="mt-2 flex items-center gap-2">
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  verifiedBackendUser ? "bg-[#36C6D3]" : "bg-amber-400"
                }`}
              />
              <span className="text-sm font-bold text-[#F5F7FC]">
                {verifiedBackendUser
                  ? "Verified by FastAPI JWT"
                  : "Session Active (Backend Pending)"}
              </span>
            </div>
            <div className="mt-2 text-xs text-[#A7B0C4]">
              {backendAuthError
                ? `API Note: ${backendAuthError}`
                : verifiedBackendUser
                  ? `Audience: ${verifiedBackendUser.audience}`
                  : "Awaiting GET /api/v1/auth/me"}
            </div>
          </div>
        </section>

        {/* Organization Onboarding or Active Workspace */}
        {isLoadingOrganizations ? (
          <div className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/70 p-8 text-center font-mono text-xs text-[#A7B0C4]">
            Loading organization memberships from Svario API...
          </div>
        ) : organizations.length === 0 || showCreateModal ? (
          <OrganizationOnboardingForm
            onSuccess={() => setShowCreateModal(false)}
            onCancel={
              organizations.length > 0
                ? () => setShowCreateModal(false)
                : undefined
            }
          />
        ) : (
          activeOrganization && (
            <section className="space-y-6 rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/80 p-6 sm:p-8">
              <div className="flex flex-col justify-between gap-4 border-b border-[#A7B0C4]/15 pb-6 sm:flex-row sm:items-center">
                <div>
                  <span className="font-mono text-xs font-semibold uppercase tracking-widest text-[#36C6D3]">
                    STAGE 2 ORGANIZATION & BUSINESS WORKSPACE
                  </span>
                  <h1 className="mt-1 text-2xl font-bold text-[#F5F7FC]">
                    {activeOrganization.name}
                  </h1>
                  <p className="mt-1 font-mono text-xs text-[#A7B0C4]">
                    Organization ID: {activeOrganization.id}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <span
                    className={`rounded-xl border px-3 py-1.5 font-mono text-xs font-bold uppercase ${
                      isCompleted
                        ? "border-emerald-400/50 bg-emerald-500/15 text-emerald-200"
                        : "border-amber-400/50 bg-amber-500/15 text-amber-200"
                    }`}
                  >
                    {isCompleted
                      ? "Onboarding Completed"
                      : `Onboarding In Progress (${completedStepsCount}/8 steps)`}
                  </span>
                  <Link
                    href="/onboarding"
                    className="rounded-xl bg-[#7657F6] px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#6546e6]"
                  >
                    {isCompleted
                      ? "Edit Business Onboarding Settings"
                      : "Continue Business Onboarding"}
                  </Link>
                </div>
              </div>

              {isLoadingBundle && (
                <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/60 p-4 font-mono text-xs text-[#36C6D3]">
                  Syncing Stage 2 business onboarding configuration...
                </div>
              )}

              {bundleError && !onboardingBundle && (
                <div className="rounded-xl border border-amber-400/30 bg-amber-500/10 p-4 text-xs text-amber-200">
                  Onboarding details note: {bundleError}
                </div>
              )}

              {/* Stage 2 Dashboard Cards */}
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {/* 1. Business Profile Summary */}
                <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/80 p-5">
                  <div className="font-mono text-[10px] uppercase tracking-wider text-[#A7B0C4]">
                    Business Profile Summary
                  </div>
                  <div className="mt-2 text-base font-semibold text-[#F5F7FC]">
                    {onboardingBundle?.profile?.display_name ??
                      activeOrganization.name}
                  </div>
                  <div className="mt-2 space-y-1 text-xs text-[#A7B0C4]">
                    <div>
                      Phone:{" "}
                      <span className="text-[#F5F7FC]">
                        {onboardingBundle?.profile?.phone || "Not configured"}
                      </span>
                    </div>
                    <div>
                      Email:{" "}
                      <span className="text-[#F5F7FC]">
                        {onboardingBundle?.profile?.email || "Not configured"}
                      </span>
                    </div>
                    <div>
                      Location:{" "}
                      <span className="text-[#F5F7FC]">
                        {[
                          onboardingBundle?.profile?.city,
                          onboardingBundle?.profile?.state,
                          onboardingBundle?.profile?.country,
                        ]
                          .filter(Boolean)
                          .join(", ") || "Not configured"}
                      </span>
                    </div>
                    <div>
                      Timezone:{" "}
                      <span className="font-mono text-[#36C6D3]">
                        {onboardingBundle?.profile?.timezone ?? "Asia/Kolkata"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 2. Operating Hours Summary */}
                <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/80 p-5">
                  <div className="font-mono text-[10px] uppercase tracking-wider text-[#A7B0C4]">
                    Operating Hours
                  </div>
                  <div className="mt-2 text-base font-semibold text-[#F5F7FC]">
                    {openHoursList.length > 0
                      ? `${openHoursList.length} Active Days / Week`
                      : "Schedule Pending"}
                  </div>
                  <div className="mt-2 space-y-1 text-xs text-[#A7B0C4]">
                    {scheduleList.length > 0 ? (
                      scheduleList.slice(0, 4).map((slot) => (
                        <div
                          key={slot.weekday}
                          className="flex justify-between font-mono text-[11px]"
                        >
                          <span>{DAY_LABELS[slot.weekday]}:</span>
                          <span className="text-[#F5F7FC]">
                            {slot.is_closed
                              ? "Closed"
                              : `${slot.opens_at} - ${slot.closes_at}`}
                          </span>
                        </div>
                      ))
                    ) : (
                      <p>Configure weekly hours in the onboarding wizard.</p>
                    )}
                  </div>
                </div>

                {/* 3. Supported Languages */}
                <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/80 p-5">
                  <div className="font-mono text-[10px] uppercase tracking-wider text-[#A7B0C4]">
                    Supported Languages
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {onboardingBundle?.languages?.supported_languages &&
                    onboardingBundle.languages.supported_languages.length > 0 ? (
                      onboardingBundle.languages.supported_languages.map(
                        (code) => {
                          const isPrimary =
                            onboardingBundle.languages.primary_language ===
                            code;
                          return (
                            <span
                              key={code}
                              className={`rounded-lg px-2.5 py-1 font-mono text-xs font-semibold ${
                                isPrimary
                                  ? "border border-[#36C6D3]/60 bg-[#36C6D3]/20 text-[#36C6D3]"
                                  : "border border-[#A7B0C4]/25 bg-[#171D33] text-[#F5F7FC]"
                              }`}
                            >
                              {LANGUAGE_NAMES[code] ?? code}
                              {isPrimary ? " (Primary)" : ""}
                            </span>
                          );
                        }
                      )
                    ) : (
                      <span className="text-xs text-[#A7B0C4]">
                        English (Default)
                      </span>
                    )}
                  </div>
                  <p className="mt-3 text-xs text-[#A7B0C4]">
                    Multi-lingual voice & text reception preferences stored per
                    business.
                  </p>
                </div>

                {/* 4. Assistant Configuration Status */}
                <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/80 p-5">
                  <div className="font-mono text-[10px] uppercase tracking-wider text-[#A7B0C4]">
                    Assistant Configuration Status
                  </div>
                  <div className="mt-2 flex items-center justify-between">
                    <span className="text-base font-semibold text-[#F5F7FC]">
                      {onboardingBundle?.assistant?.assistant_name ?? "Aria"}
                    </span>
                    <span
                      className={`rounded-md px-2 py-0.5 font-mono text-[10px] font-bold uppercase ${
                        onboardingBundle?.assistant?.enabled !== false
                          ? "bg-emerald-500/20 text-emerald-300"
                          : "bg-rose-500/20 text-rose-300"
                      }`}
                    >
                      {onboardingBundle?.assistant?.enabled !== false
                        ? "Enabled"
                        : "Paused"}
                    </span>
                  </div>
                  <div className="mt-2 space-y-1 text-xs text-[#A7B0C4]">
                    <div>
                      Personality:{" "}
                      <span className="capitalize text-[#F5F7FC]">
                        {onboardingBundle?.assistant?.personality ??
                          "Professional"}
                      </span>
                    </div>
                    <div>
                      Response Style:{" "}
                      <span className="capitalize text-[#F5F7FC]">
                        {onboardingBundle?.assistant?.response_style ??
                          "Balanced"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 5. FAQs & Human Escalation */}
                <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/80 p-5">
                  <div className="font-mono text-[10px] uppercase tracking-wider text-[#A7B0C4]">
                    FAQs & Human Escalation
                  </div>
                  <div className="mt-2 text-base font-semibold text-[#F5F7FC]">
                    {onboardingBundle?.faqs?.length ?? 0} Active FAQ Entries
                  </div>
                  <div className="mt-2 space-y-1 text-xs text-[#A7B0C4]">
                    <div>
                      Escalation Contact:{" "}
                      <span className="text-[#F5F7FC]">
                        {onboardingBundle?.escalation?.contact_name ||
                          "Unassigned"}
                      </span>
                    </div>
                    <div>
                      Preferred Method:{" "}
                      <span className="uppercase text-[#36C6D3]">
                        {onboardingBundle?.escalation?.preferred_method ??
                          "phone"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 6. Industry & Role Boundary */}
                <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/80 p-5">
                  <div className="font-mono text-[10px] uppercase tracking-wider text-[#A7B0C4]">
                    Industry Module & Healthcare Safeguards
                  </div>
                  <div className="mt-2 text-base font-semibold capitalize text-[#F5F7FC]">
                    {activeOrganization.industry} ({activeOrganization.membership_role})
                  </div>
                  <p className="mt-2 text-xs text-[#A7B0C4]">
                    {activeOrganization.industry === "clinic" ||
                    activeOrganization.industry === "hospital"
                      ? "Administrative-only healthcare mode enforced: no clinical advice, diagnosis, or prescriptions."
                      : "Isolated under PostgreSQL RLS & FastAPI membership checks."}
                  </p>
                </div>
              </div>

              {/* Stage 5 Salon Workflow Module UI */}
              {activeOrganization.industry === "salon" &&
                onboardingBundle?.business_id &&
                session?.access_token && (
                  <SalonDashboardView
                    accessToken={session.access_token}
                    organizationId={activeOrganization.id}
                    businessId={onboardingBundle.business_id}
                    isOwnerOrAdmin={
                      activeOrganization.membership_role === "owner" ||
                      activeOrganization.membership_role === "admin"
                    }
                  />
                )}

              {/* Stage 6 Clinic Workflow Module UI */}
              {activeOrganization.industry === "clinic" &&
                onboardingBundle?.business_id &&
                session?.access_token && (
                  <ClinicDashboardView
                    accessToken={session.access_token}
                    organizationId={activeOrganization.id}
                    businessId={onboardingBundle.business_id}
                    isOwnerOrAdmin={
                      activeOrganization.membership_role === "owner" ||
                      activeOrganization.membership_role === "admin"
                    }
                  />
                )}
            </section>
          )
        )}
      </main>
    </div>
  );
}
