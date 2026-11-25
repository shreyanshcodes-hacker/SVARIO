"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SvarioBrandLogo } from "@/components/SvarioBrandLogo";
import { OrganizationOnboardingForm } from "@/components/organizations/OrganizationOnboardingForm";
import { OrganizationSwitcher } from "@/components/organizations/OrganizationSwitcher";
import { useAuthOrganization } from "@/context/AuthOrganizationContext";
import { fetchOnboardingBundle } from "@/lib/api";
import { ClinicDashboardView } from "@/components/dashboard/ClinicDashboardView";
import { SalonDashboardView } from "@/components/dashboard/SalonDashboardView";
import {
  DashboardWorkspaceSkeleton,
  SkeletonBlock,
} from "@/components/ui/LoadingSkeleton";
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
      <main className="min-h-screen bg-[#0B1020] text-[#F5F7FC]">
        <div className="mx-auto max-w-6xl space-y-6 px-6 py-10">
          <div className="flex items-center justify-between border-b border-[#A7B0C4]/15 pb-4">
            <SkeletonBlock className="h-8 w-32" />
            <SkeletonBlock className="h-8 w-44 rounded-xl" />
          </div>
          <DashboardWorkspaceSkeleton label="Checking session..." cards={3} />
        </div>
      </main>
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
    "Svario User";

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
              <SvarioBrandLogo />
            </Link>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {activeOrganization && (
              <>
                {activeOrganization.industry === "salon" && (
                  <Link
                    href="/dashboard/booking-website"
                    data-testid="nav-booking-website-link"
                    className="rounded-xl border border-emerald-400/50 bg-emerald-500/15 px-3.5 py-1.5 text-xs font-semibold text-emerald-200 transition hover:bg-emerald-500/25"
                  >
                    Booking Website
                  </Link>
                )}
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
          aria-label="Account and Workspace Summary"
          className="grid gap-5 md:grid-cols-3"
        >
          <div className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-5">
            <div className="font-mono text-[11px] uppercase tracking-wider text-[#A7B0C4]">
              Account
            </div>
            <div className="mt-2 text-lg font-bold text-[#F5F7FC]">
              {displayName}
            </div>
            <div className="mt-0.5 text-xs text-[#36C6D3]">{displayEmail}</div>
          </div>

          <div className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-5">
            <div className="font-mono text-[11px] uppercase tracking-wider text-[#A7B0C4]">
              Active Organization
            </div>
            <div className="mt-2 text-lg font-bold text-[#F5F7FC]">
              {activeOrganization ? activeOrganization.name : "None Selected"}
            </div>
            <div className="mt-0.5 text-xs text-[#A7B0C4]">
              {activeOrganization
                ? `${organizations.length} ${organizations.length === 1 ? "workspace" : "workspaces"}`
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
              {isCompleted ? "Setup complete" : `Setup progress: ${completedStepsCount}/8 steps`}
            </div>
          </div>
        </section>

        {/* Organization Onboarding or Active Workspace */}
        {isLoadingOrganizations ? (
          <DashboardWorkspaceSkeleton
            label="Loading your workspaces..."
            cards={3}
          />
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
                    BUSINESS WORKSPACE
                  </span>
                  <h1 className="mt-1 text-2xl font-bold text-[#F5F7FC]">
                    {activeOrganization.name}
                  </h1>
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
                      ? "Edit Business Settings"
                      : "Continue Onboarding"}
                  </Link>
                </div>
              </div>

              {isLoadingBundle && !onboardingBundle && (
                <div
                  role="status"
                  aria-label="Loading your business configuration..."
                  className="grid gap-4 md:grid-cols-3"
                >
                  <span className="sr-only">
                    Loading your business configuration...
                  </span>
                  {Array.from({ length: 3 }).map((_, idx) => (
                    <div
                      key={idx}
                      className="space-y-2.5 rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/60 p-4"
                    >
                      <SkeletonBlock className="h-3 w-24 bg-[#36C6D3]/20" />
                      <SkeletonBlock className="h-4 w-36" />
                      <SkeletonBlock className="h-3 w-full" />
                    </div>
                  ))}
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

                {/* 6. Workspace Privacy */}
                <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/80 p-5">
                  <div className="font-mono text-[10px] uppercase tracking-wider text-[#A7B0C4]">
                    Workspace &amp; Safeguards
                  </div>
                  <div className="mt-2 text-base font-semibold capitalize text-[#F5F7FC]">
                    {activeOrganization.industry} ({activeOrganization.membership_role})
                  </div>
                  <p className="mt-2 text-xs text-[#A7B0C4]">
                    {activeOrganization.industry === "clinic" ||
                    activeOrganization.industry === "hospital"
                      ? "Administrative-only healthcare mode enforced: no clinical advice, diagnosis, or prescriptions."
                      : "Your salon profile, services, and appointments are privately isolated to your workspace."}
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
