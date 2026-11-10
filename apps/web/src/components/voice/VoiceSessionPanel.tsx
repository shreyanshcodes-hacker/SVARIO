"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { VoiceOrbWaveform } from "./VoiceOrbWaveform";
import {
  SvarioWebRtcVoiceClient,
  type WebRtcEnvironmentAdapters,
} from "@/lib/voice/webrtcClient";
import type { VoiceClientSnapshot } from "@/lib/voice/types";
import type {
  LanguageCodeType,
  OrganizationSummary,
  RealtimeVoicePresetType,
} from "@/types/platform";

export interface VoiceSessionPanelProps {
  organizations: OrganizationSummary[];
  selectedOrganizationId: string;
  onSelectOrganizationId?: (orgId: string) => void;
  accessToken: string | null;
  adapters?: WebRtcEnvironmentAdapters;
}

const VOICE_PRESETS: readonly { id: RealtimeVoicePresetType; label: string }[] = [
  { id: "alloy", label: "Alloy (Balanced)" },
  { id: "shimmer", label: "Shimmer (Clear & Warm)" },
  { id: "verse", label: "Verse (Expressive)" },
  { id: "sage", label: "Sage (Calm)" },
  { id: "coral", label: "Coral (Friendly)" },
  { id: "ash", label: "Ash (Direct)" },
];

const LANGUAGE_OPTIONS: readonly { id: LanguageCodeType; label: string }[] = [
  { id: "en", label: "English (EN)" },
  { id: "hi", label: "Hindi (HI / हिन्दी)" },
  { id: "hinglish", label: "Hinglish (Conversational)" },
];

const INITIAL_SNAPSHOT: VoiceClientSnapshot = {
  state: "idle",
  permissionState: "prompt",
  isMuted: false,
  activeSession: null,
  error: null,
  activeResponseId: null,
  expiresAtIso: null,
  events: [],
  preferredLanguage: "en",
  lastToolExecution: null,
  escalationNotice: null,
};

export function VoiceSessionPanel({
  organizations,
  selectedOrganizationId,
  onSelectOrganizationId,
  accessToken,
  adapters,
}: VoiceSessionPanelProps) {
  const [snapshot, setSnapshot] = useState<VoiceClientSnapshot>(INITIAL_SNAPSHOT);
  const [selectedVoice, setSelectedVoice] =
    useState<RealtimeVoicePresetType>("alloy");
  const clientRef = useRef<SvarioWebRtcVoiceClient | null>(null);

  useEffect(() => {
    const client = new SvarioWebRtcVoiceClient(
      {
        onSnapshotChange: (next) => {
          setSnapshot(next);
        },
      },
      adapters
    );
    clientRef.current = client;

    return () => {
      client.destroy();
      clientRef.current = null;
    };
  }, [adapters]);

  const activeOrg =
    organizations.find((o) => o.id === selectedOrganizationId) ??
    organizations[0] ??
    null;

  const isSessionActive =
    snapshot.state === "requesting_permission" ||
    snapshot.state === "connecting" ||
    snapshot.state === "connected" ||
    snapshot.state === "listening" ||
    snapshot.state === "processing" ||
    snapshot.state === "speaking" ||
    snapshot.state === "reconnecting";

  const handleStartConversation = useCallback(async () => {
    if (!clientRef.current || !activeOrg) return;
    await clientRef.current.startSession(
      {
        organization_id: activeOrg.id,
        access_mode: "organization_member",
        voice_override: selectedVoice,
      },
      accessToken
    );
  }, [activeOrg, accessToken, selectedVoice]);

  const handleEndConversation = useCallback(() => {
    clientRef.current?.endSession();
  }, []);

  const handleReconnect = useCallback(async () => {
    if (!clientRef.current) return;
    if (activeOrg) {
      await clientRef.current.startSession(
        {
          organization_id: activeOrg.id,
          access_mode: "organization_member",
          voice_override: selectedVoice,
        },
        accessToken,
        true
      );
    } else {
      await clientRef.current.reconnect();
    }
  }, [activeOrg, accessToken, selectedVoice]);

  const handleToggleMute = useCallback(() => {
    if (!clientRef.current) return;
    clientRef.current.setMuted(!snapshot.isMuted);
  }, [snapshot.isMuted]);

  const handleInterrupt = useCallback(() => {
    clientRef.current?.interruptResponse();
  }, []);

  const handleSelectLanguage = useCallback((lang: LanguageCodeType) => {
    clientRef.current?.setPreferredLanguage(lang);
  }, []);

  return (
    <div className="space-y-6 rounded-2xl border border-white/10 bg-[#171D33] p-6 text-[#F5F7FC] shadow-xl">
      {/* Top Header & Selector Row */}
      <div className="flex flex-col justify-between gap-4 border-b border-white/10 pb-5 md:flex-row md:items-center">
        <div>
          <span className="text-xs font-semibold uppercase tracking-widest text-[#36C6D3]">
            STAGE 3 • SHARED BROWSER VOICE INFRASTRUCTURE
          </span>
          <h2 className="mt-1 text-xl font-bold text-[#F5F7FC]">
            Realtime WebRTC Voice Receptionist Console
          </h2>
          <p className="mt-1 text-xs text-[#A7B0C4]">
            Short-lived ephemeral session credentials • No raw audio or transcript storage by default
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {organizations.length > 0 && (
            <label className="flex flex-col text-xs text-[#A7B0C4]">
              <span className="mb-1 font-medium uppercase tracking-wider">
                Organization
              </span>
              <select
                aria-label="Select organization for voice session"
                value={activeOrg?.id ?? ""}
                disabled={isSessionActive}
                onChange={(e) => onSelectOrganizationId?.(e.target.value)}
                className="rounded-lg border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC] focus:border-[#7657F6] focus:outline-none disabled:opacity-60"
              >
                {organizations.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name} ({org.industry.toUpperCase()})
                  </option>
                ))}
              </select>
            </label>
          )}

          <label className="flex flex-col text-xs text-[#A7B0C4]">
            <span className="mb-1 font-medium uppercase tracking-wider">
              Voice Persona
            </span>
            <select
              aria-label="Select Realtime voice"
              value={selectedVoice}
              disabled={isSessionActive}
              onChange={(e) =>
                setSelectedVoice(e.target.value as RealtimeVoicePresetType)
              }
              className="rounded-lg border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC] focus:border-[#7657F6] focus:outline-none disabled:opacity-60"
            >
              {VOICE_PRESETS.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col text-xs text-[#A7B0C4]">
            <span className="mb-1 font-medium uppercase tracking-wider">
              Language
            </span>
            <select
              aria-label="Select conversation language"
              data-testid="voice-language-select"
              value={snapshot.preferredLanguage ?? "en"}
              onChange={(e) =>
                handleSelectLanguage(e.target.value as LanguageCodeType)
              }
              className="rounded-lg border border-white/15 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC] focus:border-[#7657F6] focus:outline-none"
            >
              {LANGUAGE_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {/* Status Indicators Bar */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div
          data-testid="mic-permission-status"
          className="rounded-xl border border-white/10 bg-[#0B1020]/80 p-3"
        >
          <span className="block text-[11px] uppercase tracking-wider text-[#A7B0C4]">
            Microphone Status
          </span>
          <span className="mt-1 block text-xs font-semibold text-[#F5F7FC]">
            {snapshot.permissionState === "granted"
              ? "Permission Granted"
              : snapshot.permissionState === "denied"
              ? "Permission Denied"
              : snapshot.permissionState === "no_device"
              ? "No Microphone Found"
              : snapshot.permissionState === "requesting"
              ? "Requesting Access..."
              : "Ready to Request"}
          </span>
        </div>

        <div
          data-testid="connecting-indicator"
          className="rounded-xl border border-white/10 bg-[#0B1020]/80 p-3"
        >
          <span className="block text-[11px] uppercase tracking-wider text-[#A7B0C4]">
            Connection State
          </span>
          <span className="mt-1 block text-xs font-semibold text-[#F5F7FC]">
            {snapshot.state === "connecting" ||
            snapshot.state === "requesting_permission" ||
            snapshot.state === "reconnecting"
              ? "Connecting..."
              : isSessionActive
              ? "Connected (WebRTC)"
              : snapshot.state === "error"
              ? "Disconnected (Error)"
              : snapshot.state === "ended"
              ? "Ended"
              : "Standby"}
          </span>
        </div>

        <div
          data-testid="listening-indicator"
          className="rounded-xl border border-white/10 bg-[#0B1020]/80 p-3"
        >
          <span className="block text-[11px] uppercase tracking-wider text-[#A7B0C4]">
            Listening Indicator
          </span>
          <span
            className={`mt-1 block text-xs font-semibold ${
              snapshot.state === "listening"
                ? "text-[#36C6D3]"
                : "text-[#A7B0C4]"
            }`}
          >
            {snapshot.state === "listening"
              ? snapshot.isMuted
                ? "Paused (Muted)"
                : "Active — Listening"
              : "Inactive"}
          </span>
        </div>

        <div
          data-testid="speaking-indicator"
          className="rounded-xl border border-white/10 bg-[#0B1020]/80 p-3"
        >
          <span className="block text-[11px] uppercase tracking-wider text-[#A7B0C4]">
            Speaking Indicator
          </span>
          <span
            className={`mt-1 block text-xs font-semibold ${
              snapshot.state === "speaking"
                ? "text-[#7657F6]"
                : "text-[#A7B0C4]"
            }`}
          >
            {snapshot.state === "speaking"
              ? "Active — AI Speaking"
              : snapshot.state === "processing"
              ? "Thinking..."
              : "Silent"}
          </span>
        </div>
      </div>

      {/* Central Orb & Waveform */}
      <VoiceOrbWaveform state={snapshot.state} isMuted={snapshot.isMuted} />

      {/* Stage 4 Validated Tool Execution & Human Escalation Status Banners */}
      {snapshot.lastToolExecution && (
        <div
          data-testid="last-tool-execution-badge"
          className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[#36C6D3]/30 bg-[#0B1020]/90 px-4 py-2.5 text-xs"
        >
          <span className="font-semibold text-[#36C6D3]">
            Stage 4 Agent Tool Executed:{" "}
            <code className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[#F5F7FC]">
              {snapshot.lastToolExecution.toolName}
            </code>
          </span>
          <span className="text-[#A7B0C4]">
            Status:{" "}
            <strong className="uppercase text-[#F5F7FC]">
              {snapshot.lastToolExecution.status}
            </strong>
          </span>
        </div>
      )}

      {snapshot.escalationNotice && (
        <div
          role="status"
          data-testid="human-escalation-banner"
          className="rounded-xl border border-amber-400/40 bg-amber-950/30 p-4 text-xs text-amber-100"
        >
          <p className="font-semibold text-amber-200">
            Human Escalation Logged ({snapshot.escalationNotice.escalationReference}) —{" "}
            <span className="uppercase">{snapshot.escalationNotice.status}</span>
          </p>
          <p className="mt-1 text-amber-100/90">
            {snapshot.escalationNotice.customerMessageDirective}
          </p>
        </div>
      )}

      {/* Error Display Banner */}
      {snapshot.error && (
        <div
          role="alert"
          data-testid="voice-error-banner"
          className="flex flex-col justify-between gap-3 rounded-xl border border-rose-500/40 bg-rose-950/30 p-4 text-sm text-rose-200 sm:flex-row sm:items-center"
        >
          <div>
            <p className="font-semibold text-rose-100">
              Voice Session Error ({snapshot.error.code})
            </p>
            <p className="mt-0.5 text-xs text-rose-200/90">
              {snapshot.error.message}
            </p>
          </div>
          {snapshot.error.recoverable && (
            <button
              type="button"
              data-testid="voice-error-reconnect-button"
              onClick={() => void handleReconnect()}
              className="shrink-0 rounded-lg border border-[#36C6D3]/50 bg-[#36C6D3]/15 px-3.5 py-2 text-xs font-semibold text-[#36C6D3] transition hover:bg-[#36C6D3]/25"
            >
              Reconnect Session
            </button>
          )}
        </div>
      )}

      {/* Primary Action Controls */}
      <div className="flex flex-wrap items-center justify-center gap-3 pt-1">
        <button
          type="button"
          data-testid="start-conversation-button"
          disabled={isSessionActive || !activeOrg}
          onClick={() => void handleStartConversation()}
          className="rounded-xl bg-[#7657F6] px-5 py-2.5 text-sm font-semibold text-[#F5F7FC] shadow-lg shadow-[#7657F6]/25 transition hover:bg-[#6546e6] disabled:cursor-not-allowed disabled:opacity-45"
        >
          Start Conversation
        </button>

        <button
          type="button"
          data-testid="end-conversation-button"
          disabled={!isSessionActive}
          onClick={handleEndConversation}
          className="rounded-xl border border-rose-500/40 bg-rose-500/15 px-5 py-2.5 text-sm font-semibold text-rose-200 transition hover:bg-rose-500/25 disabled:cursor-not-allowed disabled:opacity-40"
        >
          End Conversation
        </button>

        <button
          type="button"
          data-testid="mute-unmute-button"
          disabled={!isSessionActive}
          onClick={handleToggleMute}
          className="rounded-xl border border-white/15 bg-[#0B1020] px-4 py-2.5 text-sm font-medium text-[#F5F7FC] transition hover:border-[#36C6D3]/50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {snapshot.isMuted ? "Unmute Microphone" : "Mute Microphone"}
        </button>

        <button
          type="button"
          data-testid="reconnect-session-button"
          disabled={snapshot.state === "requesting_permission" || snapshot.state === "connecting" || !activeOrg}
          onClick={() => void handleReconnect()}
          className="rounded-xl border border-[#36C6D3]/40 bg-[#36C6D3]/10 px-4 py-2.5 text-sm font-medium text-[#36C6D3] transition hover:bg-[#36C6D3]/20 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Reconnect
        </button>

        {snapshot.state === "speaking" && (
          <button
            type="button"
            data-testid="interrupt-response-button"
            onClick={handleInterrupt}
            className="rounded-xl border border-amber-400/40 bg-amber-500/15 px-4 py-2.5 text-sm font-medium text-amber-200 transition hover:bg-amber-500/25"
          >
            Interrupt Response
          </button>
        )}
      </div>

      {/* Active Business Context & Ephemeral Session Metadata */}
      {snapshot.activeSession && (
        <div
          data-testid="active-session-metadata"
          className="grid grid-cols-1 gap-4 rounded-xl border border-white/10 bg-[#0B1020]/70 p-4 text-xs md:grid-cols-2"
        >
          <div>
            <p className="font-semibold uppercase tracking-wider text-[#36C6D3]">
              Active Business Assistant Context
            </p>
            <p className="mt-1 text-[#F5F7FC]">
              <span className="text-[#A7B0C4]">Business:</span>{" "}
              {snapshot.activeSession.assistant_context.business_name} (
              {snapshot.activeSession.industry})
            </p>
            <p className="mt-0.5 text-[#F5F7FC]">
              <span className="text-[#A7B0C4]">Assistant:</span>{" "}
              {snapshot.activeSession.assistant_context.assistant_name} (
              {snapshot.activeSession.assistant_context.personality} /{" "}
              {snapshot.activeSession.assistant_context.response_style})
            </p>
            <p className="mt-0.5 text-[#F5F7FC]">
              <span className="text-[#A7B0C4]">Supported Languages:</span>{" "}
              {snapshot.activeSession.assistant_context.supported_languages
                .join(", ")
                .toUpperCase()}
            </p>
          </div>
          <div>
            <p className="font-semibold uppercase tracking-wider text-[#7657F6]">
              Security & Privacy Contract
            </p>
            <p className="mt-1 text-[#A7B0C4]">
              Session ID:{" "}
              <span className="font-mono text-[#F5F7FC]">
                {snapshot.activeSession.session_id}
              </span>
            </p>
            <p className="mt-0.5 text-[#A7B0C4]">
              Credential TTL:{" "}
              <span className="text-[#F5F7FC]">
                {snapshot.activeSession.client_secret.ttl_seconds}s (ephemeral)
              </span>
            </p>
            <p className="mt-0.5 text-[#A7B0C4]">
              Healthcare Administrative-Only Guardrails:{" "}
              <span className="text-[#F5F7FC]">
                {snapshot.activeSession.assistant_context
                  .administrative_only_guardrails
                  ? "Enforced"
                  : "Standard Business Scope"}
              </span>
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
