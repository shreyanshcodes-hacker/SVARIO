"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createPublicWebsiteVoiceSessionApi,
  executePublicWebsiteVoiceToolApi,
} from "@/lib/api";
import {
  SvarioWebRtcVoiceClient,
  type WebRtcEnvironmentAdapters,
} from "@/lib/voice/webrtcClient";
import type { VoiceClientSnapshot, VoiceSessionState } from "@/lib/voice/types";
import type {
  PublicBookingWebsiteData,
  PublicSalonServiceItem,
} from "@/types/website";
import type { VoiceSessionCreateResponseData } from "@/types/platform";
import { resolveReceptionistTemplateTheme } from "./template-theme-adapter";

export interface PublicAiReceptionistProps {
  data: PublicBookingWebsiteData;
  isPreview?: boolean;
  isOpen: boolean;
  onOpen: () => void;
  onClose: () => void;
  selectedService?: PublicSalonServiceItem | null;
  adapters?: WebRtcEnvironmentAdapters;
}

const INITIAL_SNAPSHOT: VoiceClientSnapshot = {
  state: "idle",
  permissionState: "prompt",
  isMuted: false,
  isUserSpeaking: false,
  activeSession: null,
  error: null,
  responseError: null,
  activeResponseId: null,
  expiresAtIso: null,
  events: [],
  preferredLanguage: "en",
  lastToolExecution: null,
  escalationNotice: null,
  microphoneDiagnostics: {
    trackAttached: false,
    trackEnabled: false,
    trackReadyState: "unknown",
    trackMutedBySystem: false,
    inputLevel: 0,
    hasDetectedAudioActivity: false,
  },
  playbackState: {
    remoteTrackReceived: false,
    autoplayBlocked: false,
    isPlaying: false,
    warningMessage: null,
  },
};

function formatStatusLabel(state: VoiceSessionState, isMuted: boolean): string {
  switch (state) {
    case "requesting_permission":
      return "Requesting Microphone…";
    case "connecting":
      return "Connecting to Receptionist…";
    case "connected":
      return "Connected";
    case "listening":
      return isMuted ? "Microphone Muted" : "Listening…";
    case "processing":
      return "Checking Salon Details…";
    case "speaking":
      return "Receptionist Speaking…";
    case "reconnecting":
      return "Reconnecting…";
    case "error":
      return "Connection Issue";
    case "ended":
      return "Call Ended";
    case "idle":
    default:
      return "Ready to Talk";
  }
}

function formatMicPermissionLabel(permission: VoiceClientSnapshot["permissionState"]): string {
  switch (permission) {
    case "granted":
      return "Microphone Allowed";
    case "denied":
      return "Microphone Blocked";
    case "prompt":
    default:
      return "Microphone Ready";
  }
}

/**
 * Stage 3 — Template-Aware Public AI Receptionist UI.
 * Reuses the locked `SvarioWebRtcVoiceClient` core via its adapter interface without
 * modifying any protected voice core or template files.
 */
export function PublicAiReceptionist({
  data,
  isPreview = false,
  isOpen,
  onOpen,
  onClose,
  selectedService = null,
  adapters,
}: PublicAiReceptionistProps): React.JSX.Element | null {
  const [snapshot, setSnapshot] = useState<VoiceClientSnapshot>(INITIAL_SNAPSHOT);
  const clientRef = useRef<SvarioWebRtcVoiceClient | null>(null);
  const visitorTokenRef = useRef<string | null>(null);

  const theme = useMemo(() => resolveReceptionistTemplateTheme(data), [data]);

  // Build slug-scoped adapters wrapping the locked SvarioWebRtcVoiceClient
  const mergedAdapters = useMemo<WebRtcEnvironmentAdapters>(() => {
    return {
      ...adapters,
      createVoiceSession:
        adapters?.createVoiceSession ??
        (async (payload) => {
          const publicSession = await createPublicWebsiteVoiceSessionApi(
            data.slug,
            payload.voice_override
          );
          visitorTokenRef.current = publicSession.visitor_session_token;
          const adapted: VoiceSessionCreateResponseData = {
            session_id: publicSession.session_id,
            organization_id: "public-slug-session",
            business_id: "public-slug-session",
            industry: "salon",
            access_mode: "public_visitor",
            model: publicSession.model,
            voice: publicSession.voice,
            webrtc_url: publicSession.webrtc_url,
            webrtc_calls_url: publicSession.webrtc_calls_url,
            data_channel_label: publicSession.data_channel_label,
            client_secret: publicSession.client_secret,
            capabilities: publicSession.capabilities,
            assistant_context: publicSession.assistant_context,
          };
          return adapted;
        }),
      executeVoiceTool:
        adapters?.executeVoiceTool ??
        (async (payload) => {
          const token = visitorTokenRef.current;
          if (!token) {
            throw new Error("Voice session token is unavailable. Please reconnect.");
          }
          return executePublicWebsiteVoiceToolApi(data.slug, {
            session_id: payload.session_id,
            call_id: payload.call_id,
            tool_name: payload.tool_name,
            arguments: payload.arguments,
            visitor_session_token: token,
          });
        }),
    };
  }, [adapters, data.slug]);

  useEffect(() => {
    const client = new SvarioWebRtcVoiceClient(
      {
        onSnapshotChange: (next) => {
          setSnapshot(next);
        },
      },
      mergedAdapters
    );
    clientRef.current = client;

    return () => {
      visitorTokenRef.current = null;
      client.destroy();
      clientRef.current = null;
    };
  }, [mergedAdapters]);

  // Keyboard Escape closes the panel cleanly
  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        clientRef.current?.endSession();
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isOpen, onClose]);

  const isSessionActive =
    snapshot.state === "requesting_permission" ||
    snapshot.state === "connecting" ||
    snapshot.state === "connected" ||
    snapshot.state === "listening" ||
    snapshot.state === "processing" ||
    snapshot.state === "speaking" ||
    snapshot.state === "reconnecting";

  const handleStartCall = useCallback(async () => {
    if (isPreview || !clientRef.current) return;
    await clientRef.current.startSession(
      {
        organization_id: "public-slug-session",
        access_mode: "public_visitor",
      },
      null
    );
  }, [isPreview]);

  const handleReconnect = useCallback(async () => {
    if (isPreview || !clientRef.current) return;
    await clientRef.current.startSession(
      {
        organization_id: "public-slug-session",
        access_mode: "public_visitor",
      },
      null,
      true
    );
  }, [isPreview]);

  const handleToggleMute = useCallback(() => {
    clientRef.current?.setMuted(!snapshot.isMuted);
  }, [snapshot.isMuted]);

  const handleInterrupt = useCallback(() => {
    clientRef.current?.interruptResponse();
  }, []);

  const handleResumePlayback = useCallback(async () => {
    await clientRef.current?.resumePlayback();
  }, []);

  const handleEndCall = useCallback(() => {
    visitorTokenRef.current = null;
    clientRef.current?.endSession();
  }, []);

  const handleClosePanel = useCallback(() => {
    if (isSessionActive) {
      visitorTokenRef.current = null;
      clientRef.current?.endSession();
    }
    onClose();
  }, [isSessionActive, onClose]);

  if (!data.show_ai_receptionist || !data.receptionist.enabled) {
    return null;
  }

  const receptionistName =
    data.receptionist.assistant_name || `${data.business.display_name} AI Receptionist`;
  const greeting =
    data.receptionist.greeting ||
    `Hi! Ask me about ${data.business.display_name}'s services, prices, hours, or availability.`;

  const isOrbPulsing =
    snapshot.state === "speaking" ||
    snapshot.state === "listening" ||
    snapshot.state === "processing" ||
    snapshot.state === "connecting";

  return (
    <>
      {/* Tasteful Floating Template-Aware Launcher (bottom-right, never blocks hero/nav) */}
      {!isOpen && (
        <div className="fixed right-4 bottom-4 z-40 sm:right-6 sm:bottom-6">
          <button
            type="button"
            data-testid="public-ai-receptionist-launcher"
            data-template-theme={theme.templateId}
            aria-label={`Talk to ${receptionistName}`}
            onClick={onOpen}
            className={`group flex items-center gap-2.5 border px-4 py-3 text-xs font-semibold transition-transform hover:-translate-y-0.5 focus:outline-none focus:ring-2 ${theme.buttonRadiusClass} ${theme.launcherShadowClass}`}
            style={{
              fontFamily: theme.fontFamily,
              backgroundColor: theme.accentBg,
              color: theme.accentText,
              borderColor: theme.borderColor,
            }}
          >
            <span
              aria-hidden="true"
              className="inline-flex h-2.5 w-2.5 rounded-full bg-current opacity-90 animate-pulse"
            />
            <span>Talk to AI Receptionist</span>
          </button>
        </div>
      )}

      {/* Responsive Template-Aware Voice Receptionist Panel */}
      {isOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`AI Receptionist for ${data.business.display_name}`}
          data-testid="public-ai-receptionist-panel"
          data-template-theme={theme.templateId}
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/55 p-3 backdrop-blur-xs sm:items-center sm:p-6"
          style={{ fontFamily: theme.fontFamily }}
        >
          <div
            className={`flex w-full max-w-md flex-col overflow-hidden rounded-3xl border ${theme.panelShadowClass}`}
            style={{
              backgroundColor: theme.surfaceBg,
              borderColor: theme.borderColor,
              color: theme.textPrimary,
            }}
          >
            {/* Header */}
            <div
              className="flex items-start justify-between gap-3 border-b px-5 py-4"
              style={{
                borderColor: theme.borderColor,
                backgroundColor: theme.surfaceElevatedBg,
              }}
            >
              <div className="min-w-0">
                <span
                  className="inline-block rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
                  style={{
                    backgroundColor: theme.badgeBg,
                    color: theme.badgeText,
                  }}
                >
                  AI Receptionist · {data.business.display_name}
                </span>
                <h2 className={`mt-1.5 truncate text-lg ${theme.headingClass}`}>
                  {receptionistName}
                </h2>
              </div>
              <button
                type="button"
                data-testid="close-ai-receptionist-button"
                aria-label="Close AI Receptionist"
                onClick={handleClosePanel}
                className="rounded-xl border px-2.5 py-1.5 text-xs font-semibold transition hover:opacity-80"
                style={{
                  borderColor: theme.borderColor,
                  color: theme.textPrimary,
                }}
              >
                ✕
              </button>
            </div>

            {/* Body */}
            <div className="space-y-4 px-5 py-5">
              {/* Selected Service Context Pill (if launched from a service card) */}
              {selectedService && (
                <div
                  className="rounded-2xl border px-3.5 py-2.5 text-xs"
                  style={{
                    borderColor: theme.borderColor,
                    backgroundColor: theme.surfaceElevatedBg,
                  }}
                >
                  <span style={{ color: theme.textMuted }}>Interested in: </span>
                  <strong>{selectedService.name}</strong> ({selectedService.duration_minutes} min)
                </div>
              )}

              {/* Voice Status & Animated Template-Matched Orb */}
              <div
                className="flex flex-col items-center rounded-2xl border px-5 py-6 text-center"
                style={{
                  borderColor: theme.borderColor,
                  backgroundColor: theme.surfaceElevatedBg,
                }}
              >
                <div
                  data-testid="receptionist-voice-orb"
                  className={`flex h-20 w-20 items-center justify-center rounded-full border-2 transition-all duration-300 ${
                    isOrbPulsing ? "scale-105 animate-pulse" : ""
                  }`}
                  style={{
                    backgroundColor: theme.accentBg,
                    color: theme.accentText,
                    borderColor: theme.borderColor,
                  }}
                >
                  <span className="text-2xl" aria-hidden="true">
                    {snapshot.state === "speaking"
                      ? "🔊"
                      : snapshot.isMuted
                      ? "🔇"
                      : "🎙️"}
                  </span>
                </div>

                <p
                  data-testid="receptionist-voice-status"
                  className="mt-4 text-sm font-semibold"
                >
                  {formatStatusLabel(snapshot.state, snapshot.isMuted)}
                </p>

                <div className="mt-2 flex flex-wrap items-center justify-center gap-2 text-[11px]">
                  <span
                    data-testid="receptionist-mic-permission"
                    className="rounded-full px-2.5 py-0.5 font-medium"
                    style={{
                      backgroundColor: theme.badgeBg,
                      color: theme.badgeText,
                    }}
                  >
                    {formatMicPermissionLabel(snapshot.permissionState)}
                  </span>
                  {snapshot.lastToolExecution && (
                    <span
                      className="rounded-full px-2.5 py-0.5 font-medium"
                      style={{
                        backgroundColor: theme.badgeBg,
                        color: theme.badgeText,
                      }}
                    >
                      Checked: {snapshot.lastToolExecution.toolName.replaceAll("_", " ")}
                    </span>
                  )}
                </div>

                <p
                  className="mt-3 max-w-xs text-xs leading-relaxed"
                  style={{ color: theme.textMuted }}
                >
                  {greeting}
                </p>
              </div>

              {/* Preview Notice */}
              {isPreview && (
                <div
                  data-testid="receptionist-preview-notice"
                  className="rounded-2xl border px-3.5 py-2.5 text-xs"
                  style={{
                    borderColor: theme.borderColor,
                    backgroundColor: theme.badgeBg,
                    color: theme.badgeText,
                  }}
                >
                  Preview Mode: Styling automatically adapts to{" "}
                  <strong>{theme.templateName}</strong>. Live browser voice connects on your
                  published <code>/s/{data.slug}</code> website.
                </div>
              )}

              {/* Autoplay Recovery Banner */}
              {snapshot.playbackState?.autoplayBlocked && (
                <div className="flex items-center justify-between gap-2 rounded-2xl border border-amber-400/50 bg-amber-500/10 px-3.5 py-2.5 text-xs">
                  <span>Browser paused AI audio playback.</span>
                  <button
                    type="button"
                    onClick={() => void handleResumePlayback()}
                    className={`${theme.buttonRadiusClass} px-3 py-1 font-semibold`}
                    style={{
                      backgroundColor: theme.accentBg,
                      color: theme.accentText,
                    }}
                  >
                    Enable AI Audio
                  </button>
                </div>
              )}

              {/* Error State */}
              {(snapshot.error || snapshot.responseError) && (
                <div
                  role="alert"
                  data-testid="receptionist-voice-error"
                  className="rounded-2xl border border-rose-500/45 bg-rose-500/10 px-3.5 py-2.5 text-xs text-rose-500"
                >
                  {snapshot.error?.message || snapshot.responseError?.message}
                </div>
              )}

              {/* Controls */}
              <div className="flex flex-wrap items-center gap-2.5 pt-1">
                {!isSessionActive ? (
                  <button
                    type="button"
                    data-testid="start-public-voice-button"
                    disabled={isPreview}
                    onClick={() =>
                      void (snapshot.state === "error" || snapshot.state === "ended"
                        ? handleReconnect()
                        : handleStartCall())
                    }
                    className={`flex-1 border px-4 py-3 text-xs font-semibold transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 ${theme.buttonRadiusClass}`}
                    style={{
                      backgroundColor: theme.accentBg,
                      color: theme.accentText,
                      borderColor: theme.borderColor,
                    }}
                  >
                    {isPreview
                      ? "Available on Published Site"
                      : snapshot.state === "error" || snapshot.state === "ended"
                      ? "Reconnect Voice Call"
                      : "Start Voice Conversation"}
                  </button>
                ) : (
                  <>
                    <button
                      type="button"
                      data-testid="mute-public-voice-button"
                      onClick={handleToggleMute}
                      className={`flex-1 border px-3.5 py-2.5 text-xs font-semibold transition hover:opacity-85 ${theme.buttonRadiusClass}`}
                      style={{
                        borderColor: theme.borderColor,
                        backgroundColor: theme.surfaceElevatedBg,
                        color: theme.textPrimary,
                      }}
                    >
                      {snapshot.isMuted ? "Unmute Mic" : "Mute Mic"}
                    </button>

                    {snapshot.state === "speaking" && (
                      <button
                        type="button"
                        data-testid="interrupt-public-voice-button"
                        onClick={handleInterrupt}
                        className={`border px-3.5 py-2.5 text-xs font-semibold transition hover:opacity-85 ${theme.buttonRadiusClass}`}
                        style={{
                          borderColor: theme.borderColor,
                          backgroundColor: theme.badgeBg,
                          color: theme.badgeText,
                        }}
                      >
                        Interrupt
                      </button>
                    )}

                    <button
                      type="button"
                      data-testid="disconnect-public-voice-button"
                      onClick={handleEndCall}
                      className={`border border-rose-500/60 bg-rose-600 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-rose-700 ${theme.buttonRadiusClass}`}
                    >
                      End Call
                    </button>
                  </>
                )}
              </div>

              <p
                className="text-center text-[11px]"
                style={{ color: theme.textMuted }}
              >
                Ask about services, pricing, business hours, or availability · No raw audio stored
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
