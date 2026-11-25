"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SvarioBrandLogo } from "@/components/SvarioBrandLogo";
import { OrganizationSwitcher } from "@/components/organizations/OrganizationSwitcher";
import { BookingWebsiteWorkspace } from "@/components/website/BookingWebsiteWorkspace";
import {
  BookingStudioSkeleton,
  SkeletonBlock,
} from "@/components/ui/LoadingSkeleton";
import { useAuthOrganization } from "@/context/AuthOrganizationContext";

export default function BookingWebsiteDashboardPage(): React.JSX.Element {
  const router = useRouter();
  const {
    isInitializing,
    session,
    supabaseUser,
    verifiedBackendUser,
    activeOrganization,
    signOut,
  } = useAuthOrganization();

  const isAuthenticated = Boolean(session && (supabaseUser || verifiedBackendUser));

  useEffect(() => {
    if (!isInitializing && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isInitializing, isAuthenticated, router]);

  if (isInitializing) {
    return (
      <main className="min-h-screen bg-[#0B1020] text-[#F5F7FC]">
        <div className="mx-auto max-w-6xl space-y-6 px-6 py-10">
          <div className="flex items-center justify-between border-b border-[#A7B0C4]/15 pb-4">
            <SkeletonBlock className="h-8 w-32" />
            <SkeletonBlock className="h-8 w-44 rounded-xl" />
          </div>
          <BookingStudioSkeleton />
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
          Redirecting to /login...
        </div>
      </div>
    );
  }

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
            <Link
              href="/dashboard"
              className="rounded-xl border border-white/15 bg-[#171D33] px-3.5 py-1.5 text-xs font-semibold text-[#F5F7FC] transition hover:border-[#36C6D3]/50"
            >
              Dashboard
            </Link>
            <Link
              href="/voice-test"
              className="rounded-xl border border-[#36C6D3]/60 bg-[#36C6D3]/15 px-3.5 py-1.5 text-xs font-semibold text-[#36C6D3] transition hover:bg-[#36C6D3]/25"
            >
              Voice Test Lab
            </Link>
            <OrganizationSwitcher onNewOrganizationClick={() => router.push("/dashboard")} />
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

      <main className="mx-auto max-w-7xl space-y-6 px-6 py-8">
        {!activeOrganization ? (
          <div className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/80 p-8 text-center text-sm text-[#A7B0C4]">
            Select or create a salon organization on your{" "}
            <Link href="/dashboard" className="text-[#36C6D3] underline">
              Dashboard
            </Link>{" "}
            to configure a Booking Website.
          </div>
        ) : activeOrganization.industry !== "salon" ? (
          <div className="rounded-2xl border border-amber-400/35 bg-amber-950/25 p-6 text-sm text-amber-100">
            White-Label Booking Website configuration is scoped to salon organizations. Your active
            organization ({activeOrganization.name}) is configured for{" "}
            <strong className="uppercase">{activeOrganization.industry}</strong>.
          </div>
        ) : session?.access_token ? (
          <BookingWebsiteWorkspace
            accessToken={session.access_token}
            organizationId={activeOrganization.id}
            organizationName={activeOrganization.name}
            isOwnerOrAdmin={
              activeOrganization.membership_role === "owner" ||
              activeOrganization.membership_role === "admin"
            }
          />
        ) : null}
      </main>
    </div>
  );
}
