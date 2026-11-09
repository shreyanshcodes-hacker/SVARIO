"use client";

import React, { useState } from "react";
import Link from "next/link";
import { SvarioLogoPlaceholder } from "@/components/SvarioLogoPlaceholder";
import { StageIndicatorBadge } from "@/components/StageIndicatorBadge";
import { VoiceSessionPanel } from "@/components/voice/VoiceSessionPanel";
import { useAuthOrganization } from "@/context/AuthOrganizationContext";
import type { WebRtcEnvironmentAdapters } from "@/lib/voice/webrtcClient";
import type { OrganizationSummary } from "@/types/platform";

export interface VoiceTestViewProps {
  testOrganizations?: OrganizationSummary[];
  testAccessToken?: string | null;
  testAdapters?: WebRtcEnvironmentAdapters;
}

const DEFAULT_DEV_ORGANIZATIONS: OrganizationSummary[] = [
  {
    id: "00000000-0000-4000-8000-000000000301",
    name: "Svario Sandbox Salon",
    slug: "svario-sandbox-salon",
    industry: "salon",
    membership_role: "owner",
    created_at: "2026-11-09T00:00:00Z",
    updated_at: "2026-11-09T00:00:00Z",
  },
];

export function VoiceTestView({
  testOrganizations,
  testAccessToken,
  testAdapters,
}: VoiceTestViewProps = {}): React.JSX.Element {
  const {
    session,
    organizations: contextOrganizations,
    activeOrganization,
    setActiveOrganizationId,
  } = useAuthOrganization();

  const resolvedOrganizations =
    testOrganizations && testOrganizations.length > 0
      ? testOrganizations
      : contextOrganizations.length > 0
      ? contextOrganizations
      : DEFAULT_DEV_ORGANIZATIONS;

  const [localSelectedOrgId, setLocalSelectedOrgId] = useState<string>(
    activeOrganization?.id ?? resolvedOrganizations[0]?.id ?? ""
  );

  const effectiveOrgId =
    activeOrganization?.id ??
    localSelectedOrgId ??
    resolvedOrganizations[0]?.id ??
    "";

  const effectiveAccessToken =
    testAccessToken !== undefined
      ? testAccessToken
      : session?.access_token ?? null;

  const handleSelectOrg = (orgId: string) => {
    setLocalSelectedOrgId(orgId);
    if (contextOrganizations.some((o) => o.id === orgId)) {
      setActiveOrganizationId(orgId);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B1020] text-[#F5F7FC]">
      <header className="border-b border-[#A7B0C4]/15 bg-[#0B1020]/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div className="flex flex-wrap items-center gap-4">
            <Link href="/">
              <SvarioLogoPlaceholder />
            </Link>
            <StageIndicatorBadge />
          </div>

          <nav className="flex flex-wrap items-center gap-3">
            <Link
              href="/dashboard"
              className="rounded-xl border border-white/15 bg-[#171D33] px-3.5 py-1.5 text-xs font-semibold text-[#F5F7FC] transition hover:border-[#36C6D3]/50"
            >
              Dashboard
            </Link>
            <Link
              href="/onboarding"
              className="rounded-xl border border-[#7657F6]/60 bg-[#7657F6]/20 px-3.5 py-1.5 text-xs font-semibold text-[#F5F7FC] transition hover:bg-[#7657F6]/35"
            >
              Business Onboarding
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-6 py-10">
        <div className="rounded-2xl border border-[#7657F6]/30 bg-gradient-to-r from-[#171D33] via-[#171D33]/90 to-[#0B1020] p-6">
          <span className="font-mono text-xs uppercase tracking-widest text-[#36C6D3]">
            DEVELOPMENT & OPERATOR VOICE TEST LAB
          </span>
          <h1 className="mt-1 text-2xl font-bold text-[#F5F7FC]">
            Svario Browser Voice Infrastructure (Stage 3)
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-[#A7B0C4]">
            Test real-time bidirectional browser audio with your organization&apos;s
            configured AI voice receptionist over OpenAI Realtime WebRTC. All
            sessions use short-lived ephemeral credentials minted by the backend.
          </p>
        </div>

        <VoiceSessionPanel
          organizations={resolvedOrganizations}
          selectedOrganizationId={effectiveOrgId}
          onSelectOrganizationId={handleSelectOrg}
          accessToken={effectiveAccessToken}
          adapters={testAdapters}
        />
      </main>
    </div>
  );
}
