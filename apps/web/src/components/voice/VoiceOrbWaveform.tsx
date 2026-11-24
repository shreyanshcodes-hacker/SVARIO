"use client";

import React from "react";
import type { VoiceSessionState } from "@/lib/voice/types";

interface VoiceOrbWaveformProps {
  state: VoiceSessionState;
  isMuted: boolean;
  isUserSpeaking?: boolean;
  hasResponseError?: boolean;
}

const STATE_VISUALS: Record<
  VoiceSessionState,
  {
    badge: string;
    subtitle: string;
    ringColor: string;
    glowColor: string;
    barHeights: readonly number[];
  }
> = {
  idle: {
    badge: "READY FOR VOICE",
    subtitle: "Press Start Conversation to launch a live WebRTC voice session",
    ringColor: "border-[#7657F6]/40",
    glowColor: "from-[#7657F6]/25 via-[#36C6D3]/15 to-transparent",
    barHeights: [18, 26, 22, 32, 22, 26, 18],
  },
  requesting_permission: {
    badge: "MICROPHONE ACCESS",
    subtitle: "Waiting for browser microphone permission...",
    ringColor: "border-[#36C6D3]/70 animate-pulse",
    glowColor: "from-[#36C6D3]/35 via-[#7657F6]/20 to-transparent",
    barHeights: [24, 34, 44, 34, 44, 34, 24],
  },
  connecting: {
    badge: "CONNECTING WEBRTC",
    subtitle: "Minting short-lived credential and negotiating WebRTC audio...",
    ringColor: "border-[#7657F6] animate-pulse",
    glowColor: "from-[#7657F6]/40 via-[#36C6D3]/25 to-transparent",
    barHeights: [28, 42, 36, 52, 36, 42, 28],
  },
  connected: {
    badge: "SESSION CONNECTED",
    subtitle: "WebRTC peer connection established; initializing audio stream...",
    ringColor: "border-[#36C6D3]",
    glowColor: "from-[#36C6D3]/35 via-[#7657F6]/25 to-transparent",
    barHeights: [30, 44, 54, 40, 54, 44, 30],
  },
  listening: {
    badge: "LISTENING",
    subtitle: "Speak naturally — Svario is listening in real time",
    ringColor: "border-[#36C6D3]",
    glowColor: "from-[#36C6D3]/45 via-[#7657F6]/30 to-transparent",
    barHeights: [36, 58, 46, 68, 46, 58, 36],
  },
  processing: {
    badge: "PROCESSING TURN",
    subtitle: "Synthesizing context-aware response...",
    ringColor: "border-[#7657F6]",
    glowColor: "from-[#7657F6]/45 via-[#36C6D3]/30 to-transparent",
    barHeights: [42, 50, 64, 52, 64, 50, 42],
  },
  speaking: {
    badge: "SPEAKING",
    subtitle: "AI receptionist is speaking — speak anytime to interrupt",
    ringColor: "border-[#7657F6]",
    glowColor: "from-[#7657F6]/55 via-[#36C6D3]/40 to-transparent",
    barHeights: [48, 76, 62, 88, 62, 76, 48],
  },
  reconnecting: {
    badge: "RECONNECTING",
    subtitle: "Re-establishing fresh WebRTC session and audio tracks...",
    ringColor: "border-[#36C6D3] animate-pulse",
    glowColor: "from-[#36C6D3]/35 via-[#7657F6]/25 to-transparent",
    barHeights: [26, 38, 48, 38, 48, 38, 26],
  },
  error: {
    badge: "ATTENTION REQUIRED",
    subtitle: "Session encountered an issue — review details below or reconnect",
    ringColor: "border-rose-500/70",
    glowColor: "from-rose-500/30 via-[#7657F6]/15 to-transparent",
    barHeights: [16, 20, 16, 24, 16, 20, 16],
  },
  ended: {
    badge: "SESSION ENDED",
    subtitle: "Microphone tracks and WebRTC peer connection cleanly released",
    ringColor: "border-white/20",
    glowColor: "from-[#7657F6]/15 via-[#36C6D3]/10 to-transparent",
    barHeights: [14, 18, 14, 20, 14, 18, 14],
  },
};

export function VoiceOrbWaveform({
  state,
  isMuted,
  isUserSpeaking = false,
  hasResponseError = false,
}: VoiceOrbWaveformProps) {
  const visual = STATE_VISUALS[state];
  const badgeText =
    state === "error"
      ? "ERROR"
      : hasResponseError
      ? "RESPONSE ERROR"
      : isMuted &&
        (state === "listening" || state === "processing" || state === "connected")
      ? "PAUSED"
      : state === "listening" && isUserSpeaking
      ? "LISTENING / SPEECH DETECTED"
      : state === "processing"
      ? "THINKING"
      : state === "speaking"
      ? "AI SPEAKING"
      : visual.badge;

  const subtitleText =
    hasResponseError && state !== "error"
      ? "AI response failed — review the error details below and try speaking again"
      : isMuted && state === "listening"
      ? "Microphone is muted — unmute to resume listening"
      : state === "listening" && isUserSpeaking
      ? "Speech detected — Svario is capturing your voice"
      : visual.subtitle;

  return (
    <div
      data-testid="voice-orb-waveform"
      data-voice-state={state}
      className="relative flex flex-col items-center justify-center rounded-2xl border border-white/10 bg-[#0B1020]/90 px-6 py-8 text-center shadow-inner"
    >
      {/* Ambient Radial Aura */}
      <div
        className={`pointer-events-none absolute h-52 w-52 rounded-full bg-radial ${visual.glowColor} blur-2xl transition-all duration-500`}
      />

      {/* Orb Core */}
      <div
        className={`relative z-10 flex h-36 w-36 items-center justify-center rounded-full border-2 ${visual.ringColor} bg-[#171D33]/90 shadow-[0_0_45px_rgba(118,87,246,0.28)] transition-all duration-300`}
      >
        <div className="flex items-center justify-center gap-1.5">
          {visual.barHeights.map((height, idx) => (
            <span
              key={idx}
              style={{ height: `${isMuted ? 14 : height}px` }}
              className={`w-1.5 rounded-full transition-all duration-300 ${
                state === "speaking"
                  ? "bg-gradient-to-t from-[#7657F6] to-[#36C6D3]"
                  : state === "listening"
                  ? "bg-[#36C6D3]"
                  : state === "error"
                  ? "bg-rose-400"
                  : "bg-[#7657F6]/80"
              }`}
            />
          ))}
        </div>
      </div>

      {/* Status Badge & Indicators */}
      <div className="relative z-10 mt-5 flex flex-wrap items-center justify-center gap-2">
        <span
          data-testid="voice-state-badge"
          className="inline-flex items-center gap-2 rounded-full border border-[#7657F6]/40 bg-[#171D33] px-3.5 py-1 text-xs font-semibold tracking-wider text-[#F5F7FC]"
        >
          <span
            className={`h-2 w-2 rounded-full ${
              state === "listening" || state === "speaking" || state === "connected"
                ? "bg-[#36C6D3]"
                : state === "connecting" ||
                  state === "requesting_permission" ||
                  state === "reconnecting" ||
                  state === "processing"
                ? "bg-[#7657F6]"
                : state === "error"
                ? "bg-rose-400"
                : "bg-[#A7B0C4]"
            }`}
          />
          {badgeText}
        </span>

        {isMuted && (
          <span
            data-testid="voice-muted-pill"
            className="inline-flex items-center rounded-full border border-amber-400/40 bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-200"
          >
            Microphone Muted
          </span>
        )}
      </div>

      <p className="relative z-10 mt-2 max-w-md text-xs text-[#A7B0C4]">
        {subtitleText}
      </p>
    </div>
  );
}
