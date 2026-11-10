/**
 * Stage 3 — Shared Browser Voice Infrastructure
 * Explicit State Machine & Typed OpenAI Realtime Data Channel Event Contracts.
 *
 * Security & Privacy Rules:
 * - Raw audio is never stored or persisted.
 * - Transcripts are not persisted by default.
 * - Only sanitized event metadata is surfaced to the UI state machine.
 */

import type {
  AgentToolNameType,
  LanguageCodeType,
  VoiceSessionCreateResponseData,
} from "@/types/platform";

export type VoiceSessionState =
  | "idle"
  | "requesting_permission"
  | "connecting"
  | "connected"
  | "listening"
  | "processing"
  | "speaking"
  | "reconnecting"
  | "error"
  | "ended";

export type MicrophonePermissionState =
  | "prompt"
  | "requesting"
  | "granted"
  | "denied"
  | "no_device";

export type VoiceErrorCode =
  | "MICROPHONE_PERMISSION_DENIED"
  | "MICROPHONE_NOT_FOUND"
  | "MICROPHONE_CAPTURE_ERROR"
  | "SESSION_CREATION_FAILED"
  | "SDP_NEGOTIATION_FAILED"
  | "WEBRTC_CONNECTION_FAILED"
  | "SESSION_EXPIRED"
  | "REALTIME_UPSTREAM_ERROR";

export interface VoiceClientError {
  code: VoiceErrorCode;
  message: string;
  recoverable: boolean;
}

export type RealtimeServerEventType =
  | "session.created"
  | "session.updated"
  | "input_audio_buffer.speech_started"
  | "input_audio_buffer.speech_stopped"
  | "input_audio_buffer.committed"
  | "input_audio_buffer.cleared"
  | "response.created"
  | "response.done"
  | "response.cancelled"
  | "response.audio.delta"
  | "response.audio.done"
  | "response.output_audio.delta"
  | "response.output_audio.done"
  | "output_audio_buffer.started"
  | "output_audio_buffer.stopped"
  | "output_audio_buffer.cleared"
  | "conversation.item.created"
  | "conversation.item.truncated"
  | "response.function_call_arguments.done"
  | "rate_limits.updated"
  | "error";

export interface RealtimeServerEventBase {
  type: string;
  event_id?: string;
}

export interface RealtimeSessionLifecycleEvent extends RealtimeServerEventBase {
  type: "session.created" | "session.updated";
  session?: {
    id?: string;
    model?: string;
    voice?: string;
    modalities?: string[];
  };
}

export interface RealtimeInputSpeechEvent extends RealtimeServerEventBase {
  type:
    | "input_audio_buffer.speech_started"
    | "input_audio_buffer.speech_stopped"
    | "input_audio_buffer.committed"
    | "input_audio_buffer.cleared";
  item_id?: string;
  audio_start_ms?: number;
  audio_end_ms?: number;
}

export interface RealtimeResponseLifecycleEvent extends RealtimeServerEventBase {
  type: "response.created" | "response.done" | "response.cancelled";
  response?: {
    id?: string;
    status?: string;
  };
}

export interface RealtimeAudioOutputEvent extends RealtimeServerEventBase {
  type:
    | "response.audio.delta"
    | "response.audio.done"
    | "response.output_audio.delta"
    | "response.output_audio.done"
    | "output_audio_buffer.started"
    | "output_audio_buffer.stopped"
    | "output_audio_buffer.cleared";
  response_id?: string;
  item_id?: string;
}

export interface RealtimeErrorEvent extends RealtimeServerEventBase {
  type: "error";
  error?: {
    type?: string;
    code?: string;
    message?: string;
  };
}

export interface RealtimeFunctionCallArgumentsDoneEvent
  extends RealtimeServerEventBase {
  type: "response.function_call_arguments.done";
  call_id?: string;
  name?: string;
  arguments?: string;
  item_id?: string;
  response_id?: string;
}

export type RealtimeServerEvent =
  | RealtimeSessionLifecycleEvent
  | RealtimeInputSpeechEvent
  | RealtimeResponseLifecycleEvent
  | RealtimeAudioOutputEvent
  | RealtimeFunctionCallArgumentsDoneEvent
  | RealtimeErrorEvent
  | RealtimeServerEventBase;

export interface RealtimeEventTelemetryEntry {
  id: string;
  timestamp: string;
  direction: "inbound" | "outbound" | "lifecycle";
  eventType: string;
  summary: string;
}

export interface LastToolExecutionState {
  callId: string;
  toolName: AgentToolNameType;
  status: "succeeded" | "rejected" | "error";
  summary: string;
  timestamp: string;
}

export interface HumanEscalationNoticeState {
  escalationReference: string;
  status: string;
  notificationDelivered: boolean;
  customerMessageDirective: string;
}

export interface VoiceClientSnapshot {
  state: VoiceSessionState;
  permissionState: MicrophonePermissionState;
  isMuted: boolean;
  activeSession: VoiceSessionCreateResponseData | null;
  error: VoiceClientError | null;
  activeResponseId: string | null;
  expiresAtIso: string | null;
  events: RealtimeEventTelemetryEntry[];
  preferredLanguage?: LanguageCodeType;
  lastToolExecution?: LastToolExecutionState | null;
  escalationNotice?: HumanEscalationNoticeState | null;
}
