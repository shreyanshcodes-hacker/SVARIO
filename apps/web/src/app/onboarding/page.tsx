"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SvarioBrandLogo } from "@/components/SvarioBrandLogo";
import { OrganizationOnboardingForm } from "@/components/organizations/OrganizationOnboardingForm";
import { OrganizationSwitcher } from "@/components/organizations/OrganizationSwitcher";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { useAuthOrganization } from "@/context/AuthOrganizationContext";

export default function OnboardingPage(): React.JSX.Element {
  const router = useRouter();
  const {
    isInitializing,
    isLoadingOrganizations,
    session,
    supabaseUser,
    verifiedBackendUser,
    organizations,
    activeOrganization,
    refreshOrganizations,
    signOut,
  } = useAuthOrganization();

  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);

  const isAuthenticated = Boolean(session && (supabaseUser || verifiedBackendUser));

  useEffect(() => {
    if (!isInitializing && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isInitializing, isAuthenticated, router]);

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

  if (!isAuthenticated || !session) {
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

  return (
    <div className="min-h-screen bg-[#0B1020] text-[#F5F7FC]">
      <header className="border-b border-[#A7B0C4]/15 bg-[#0B1020]/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-4">
            <Link href="/dashboard">
              <SvarioBrandLogo />
            </Link>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/dashboard"
              className="rounded-xl border border-[#A7B0C4]/30 bg-[#171D33]/70 px-3.5 py-1.5 text-xs font-semibold text-[#F5F7FC] transition hover:border-[#36C6D3]"
            >
              Dashboard
            </Link>
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
            <OnboardingWizard
              key={activeOrganization.id}
              accessToken={session.access_token}
              organizationId={activeOrganization.id}
              onOrganizationUpdated={refreshOrganizations}
            />
          )
        )}
      </main>
    </div>
  );
}
