/**
 * Stage 3 — Reusable Browser WebRTC Voice Client (`SvarioWebRtcVoiceClient`)
 *
 * Implements:
 * 1. Microphone permission & track acquisition (`getUserMedia`)
 * 2. Ephemeral session creation via `POST /api/v1/voice/sessions`
 * 3. `RTCPeerConnection` + `oai-events` `RTCDataChannel` setup
 * 4. Remote `<audio>` playback management
 * 5. SDP Offer / Answer exchange with OpenAI Realtime WebRTC endpoint
 * 6. Full 10-state machine (`idle`, `requesting_permission`, `connecting`,
 *    `connected`, `listening`, `processing`, `speaking`, `reconnecting`, `error`, `ended`)
 * 7. Barge-in / AI response interruption (`response.cancel` + `output_audio_buffer.clear`)
 * 8. Session expiration timer, reconnection without resource leaks, and tab cleanup
 */

import { createVoiceSessionApi, executeVoiceToolApi } from "@/lib/api";
import type {
  AgentToolNameType,
  LanguageCodeType,
  VoiceSessionCreatePayload,
  VoiceSessionCreateResponseData,
  VoiceToolExecutionPayload,
  VoiceToolExecutionResponseData,
} from "@/types/platform";
import type {
  HumanEscalationNoticeState,
  LastToolExecutionState,
  MicrophonePermissionState,
  RealtimeEventTelemetryEntry,
  RealtimeServerEvent,
  VoiceClientError,
  VoiceClientSnapshot,
  VoiceErrorCode,
  VoiceSessionState,
} from "./types";

export interface WebRtcVoiceClientCallbacks {
  onSnapshotChange?: (snapshot: VoiceClientSnapshot) => void;
  onRealtimeEvent?: (event: RealtimeServerEvent) => void;
}

export interface WebRtcEnvironmentAdapters {
  getUserMedia?: (constraints: MediaStreamConstraints) => Promise<MediaStream>;
  createPeerConnection?: (configuration?: RTCConfiguration) => RTCPeerConnection;
  createAudioElement?: () => HTMLAudioElement;
  createVoiceSession?: (
    payload: VoiceSessionCreatePayload,
    accessToken?: string | null
  ) => Promise<VoiceSessionCreateResponseData>;
  exchangeSdpOffer?: (
    webrtcUrl: string,
    ephemeralToken: string,
    sdpOffer: string
  ) => Promise<string>;
  executeVoiceTool?: (
    payload: VoiceToolExecutionPayload,
    accessToken?: string | null
  ) => Promise<VoiceToolExecutionResponseData>;
}

const MAX_TELEMETRY_EVENTS = 40;

async function defaultExchangeSdpOffer(
  webrtcUrl: string,
  ephemeralToken: string,
  sdpOffer: string
): Promise<string> {
  const response = await fetch(webrtcUrl, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${ephemeralToken}`,
      "Content-Type": "application/sdp",
    },
    body: sdpOffer,
  });

  if (!response.ok) {
    throw new Error(`WebRTC SDP negotiation failed with HTTP ${response.status}.`);
  }

  const answerSdp = await response.text();
  if (!answerSdp || !answerSdp.trim()) {
    throw new Error("Upstream Realtime endpoint returned an empty SDP answer.");
  }
  return answerSdp;
}

function classifyMediaError(err: unknown): VoiceClientError {
  const name =
    typeof err === "object" && err !== null && "name" in err
      ? String((err as { name: unknown }).name)
      : "";
  const msg =
    err instanceof Error ? err.message : "Unable to access microphone audio.";

  if (
    name === "NotAllowedError" ||
    name === "PermissionDeniedError" ||
    name === "SecurityError" ||
    msg.toLowerCase().includes("permission denied")
  ) {
    return {
      code: "MICROPHONE_PERMISSION_DENIED",
      message:
        "Microphone permission was denied. Allow microphone access in your browser settings and try again.",
      recoverable: true,
    };
  }

  if (
    name === "NotFoundError" ||
    name === "DevicesNotFoundError" ||
    msg.toLowerCase().includes("not found") ||
    msg.toLowerCase().includes("no microphone")
  ) {
    return {
      code: "MICROPHONE_NOT_FOUND",
      message:
        "No microphone device was detected. Connect a microphone and try again.",
      recoverable: true,
    };
  }

  return {
    code: "MICROPHONE_CAPTURE_ERROR",
    message: msg || "Failed to capture microphone audio.",
    recoverable: true,
  };
}

export class SvarioWebRtcVoiceClient {
  private state: VoiceSessionState = "idle";
  private permissionState: MicrophonePermissionState = "prompt";
  private isMuted = false;
  private activeSession: VoiceSessionCreateResponseData | null = null;
  private error: VoiceClientError | null = null;
  private activeResponseId: string | null = null;
  private expiresAtIso: string | null = null;
  private events: RealtimeEventTelemetryEntry[] = [];
  private preferredLanguage: LanguageCodeType = "en";
  private lastToolExecution: LastToolExecutionState | null = null;
  private escalationNotice: HumanEscalationNoticeState | null = null;

  private peerConnection: RTCPeerConnection | null = null;
  private dataChannel: RTCDataChannel | null = null;
  private localStream: MediaStream | null = null;
  private remoteAudioElement: HTMLAudioElement | null = null;
  private expirationTimer: ReturnType<typeof setTimeout> | null = null;
  private lastConnectArgs: {
    payload: VoiceSessionCreatePayload;
    accessToken?: string | null;
  } | null = null;
  private boundPageUnloadHandler: (() => void) | null = null;

  private readonly callbacks: WebRtcVoiceClientCallbacks;
  private readonly adapters: WebRtcEnvironmentAdapters;

  constructor(
    callbacks: WebRtcVoiceClientCallbacks = {},
    adapters: WebRtcEnvironmentAdapters = {}
  ) {
    this.callbacks = callbacks;
    this.adapters = adapters;

    if (typeof window !== "undefined") {
      this.boundPageUnloadHandler = () => {
        this.cleanupResources();
      };
      window.addEventListener("pagehide", this.boundPageUnloadHandler);
      window.addEventListener("beforeunload", this.boundPageUnloadHandler);
    }
  }

  public getSnapshot(): VoiceClientSnapshot {
    return {
      state: this.state,
      permissionState: this.permissionState,
      isMuted: this.isMuted,
      activeSession: this.activeSession,
      error: this.error,
      activeResponseId: this.activeResponseId,
      expiresAtIso: this.expiresAtIso,
      events: [...this.events],
      preferredLanguage: this.preferredLanguage,
      lastToolExecution: this.lastToolExecution,
      escalationNotice: this.escalationNotice,
    };
  }

  private emitSnapshot(): void {
    this.callbacks.onSnapshotChange?.(this.getSnapshot());
  }

  private appendTelemetry(
    direction: "inbound" | "outbound" | "lifecycle",
    eventType: string,
    summary: string
  ): void {
    const entry: RealtimeEventTelemetryEntry = {
      id: `evt_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      timestamp: new Date().toISOString(),
      direction,
      eventType,
      summary,
    };
    this.events = [entry, ...this.events].slice(0, MAX_TELEMETRY_EVENTS);
  }

  private transitionToError(
    code: VoiceErrorCode,
    message: string,
    recoverable = true
  ): void {
    this.cleanupResources();
    this.state = "error";
    this.error = { code, message, recoverable };
    this.appendTelemetry("lifecycle", `error.${code}`, message);
    this.emitSnapshot();
  }

  /**
   * Connect a new Realtime WebRTC voice session.
   */
  public async startSession(
    payload: VoiceSessionCreatePayload,
    accessToken?: string | null,
    isReconnect = false
  ): Promise<void> {
    this.lastConnectArgs = { payload, accessToken };

    // Always clean up any previous peer connection / tracks before starting
    this.cleanupResources();
    this.error = null;
    this.isMuted = false;
    this.activeResponseId = null;
    this.lastToolExecution = null;
    this.escalationNotice = null;

    this.state = isReconnect ? "reconnecting" : "requesting_permission";
    this.permissionState = "requesting";
    this.appendTelemetry(
      "lifecycle",
      isReconnect ? "session.reconnecting" : "permission.requesting",
      isReconnect
        ? "Reconnecting voice session and verifying microphone access."
        : "Requesting browser microphone permission."
    );
    this.emitSnapshot();

    // 1. Acquire microphone stream
    let stream: MediaStream;
    try {
      const getUserMediaFn =
        this.adapters.getUserMedia ??
        (typeof navigator !== "undefined" &&
        navigator.mediaDevices &&
        typeof navigator.mediaDevices.getUserMedia === "function"
          ? navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices)
          : null);

      if (!getUserMediaFn) {
        this.permissionState = "no_device";
        this.transitionToError(
          "MICROPHONE_NOT_FOUND",
          "Browser mediaDevices API is unavailable or no microphone device was found."
        );
        return;
      }

      stream = await getUserMediaFn({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });

      const audioTracks = stream.getAudioTracks();
      if (!audioTracks || audioTracks.length === 0) {
        this.permissionState = "no_device";
        this.transitionToError(
          "MICROPHONE_NOT_FOUND",
          "No audio input track was returned by the microphone device."
        );
        return;
      }

      this.localStream = stream;
      this.permissionState = "granted";
    } catch (err: unknown) {
      const classified = classifyMediaError(err);
      this.permissionState =
        classified.code === "MICROPHONE_PERMISSION_DENIED"
          ? "denied"
          : "no_device";
      this.transitionToError(
        classified.code,
        classified.message,
        classified.recoverable
      );
      return;
    }

    // 2. Request short-lived ephemeral Realtime credential from Svario backend
    this.state = isReconnect ? "reconnecting" : "connecting";
    this.appendTelemetry(
      "lifecycle",
      "session.minting",
      "Requesting short-lived Realtime session credential from Svario API."
    );
    this.emitSnapshot();

    let sessionData: VoiceSessionCreateResponseData;
    try {
      const createSessionFn =
        this.adapters.createVoiceSession ?? createVoiceSessionApi;
      sessionData = await createSessionFn(payload, accessToken);
      this.activeSession = sessionData;
      this.expiresAtIso = sessionData.client_secret.expires_at;
      if (sessionData.assistant_context.primary_language) {
        this.preferredLanguage = sessionData.assistant_context.primary_language;
      }
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Failed to create voice session on the server.";
      this.transitionToError("SESSION_CREATION_FAILED", msg, true);
      return;
    }

    // 3. Create RTCPeerConnection, attach tracks, data channel, and negotiate SDP
    try {
      const createPc =
        this.adapters.createPeerConnection ??
        ((cfg?: RTCConfiguration) => new RTCPeerConnection(cfg));
      const pc = createPc();
      this.peerConnection = pc;

      // Setup remote audio element for AI voice playback
      const createAudio =
        this.adapters.createAudioElement ??
        (() => {
          const el = document.createElement("audio");
          el.autoplay = true;
          el.setAttribute("playsinline", "true");
          return el;
        });
      const audioEl = createAudio();
      this.remoteAudioElement = audioEl;

      pc.ontrack = (event: RTCTrackEvent) => {
        if (this.remoteAudioElement && event.streams && event.streams[0]) {
          this.remoteAudioElement.srcObject = event.streams[0];
          void this.remoteAudioElement.play?.().catch(() => {
            // Autoplay policies handled gracefully
          });
        }
      };

      pc.onconnectionstatechange = () => {
        if (!this.peerConnection) return;
        const connState = this.peerConnection.connectionState;
        if (connState === "failed" || connState === "disconnected") {
          this.transitionToError(
            "WEBRTC_CONNECTION_FAILED",
            `WebRTC peer connection ${connState}. Check your network connection and reconnect.`
          );
        }
      };

      // Attach local microphone tracks
      for (const track of this.localStream.getAudioTracks()) {
        pc.addTrack(track, this.localStream);
      }

      // Create OpenAI Realtime event data channel (`oai-events`)
      const dc = pc.createDataChannel(
        sessionData.data_channel_label || "oai-events"
      );
      this.dataChannel = dc;

      dc.onopen = () => {
        if (this.state === "connecting" || this.state === "reconnecting" || this.state === "connected") {
          this.state = "listening";
          this.appendTelemetry(
            "lifecycle",
            "datachannel.open",
            "Realtime data channel (oai-events) open; listening for speech."
          );
          this.emitSnapshot();
        }
      };

      dc.onmessage = (messageEvent: MessageEvent) => {
        this.handleDataChannelMessage(messageEvent.data);
      };

      dc.onerror = () => {
        this.appendTelemetry(
          "lifecycle",
          "datachannel.error",
          "Data channel reported a transport warning."
        );
        this.emitSnapshot();
      };

      // Generate SDP Offer
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      const sdpOffer = offer.sdp || pc.localDescription?.sdp;
      if (!sdpOffer) {
        throw new Error("Browser failed to generate a valid WebRTC SDP offer.");
      }

      // Exchange SDP Offer for SDP Answer using short-lived ephemeral token
      const exchangeFn =
        this.adapters.exchangeSdpOffer ?? defaultExchangeSdpOffer;
      const answerSdp = await exchangeFn(
        sessionData.webrtc_url,
        sessionData.client_secret.value,
        sdpOffer
      );

      await pc.setRemoteDescription({
        type: "answer",
        sdp: answerSdp,
      });

      this.state = dc.readyState === "open" ? "listening" : "connected";
      this.appendTelemetry(
        "lifecycle",
        "webrtc.connected",
        `Connected to ${sessionData.model} (${sessionData.voice} voice).`
      );
      this.scheduleSessionExpiration(sessionData);
      this.emitSnapshot();
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Failed to establish WebRTC voice connection.";
      this.transitionToError("SDP_NEGOTIATION_FAILED", msg, true);
    }
  }

  /**
   * Reconnect the most recent voice session cleanly without leaking peer connections.
   */
  public async reconnect(): Promise<void> {
    if (!this.lastConnectArgs) {
      return;
    }
    const { payload, accessToken } = this.lastConnectArgs;
    await this.startSession(payload, accessToken, true);
  }

  /**
   * Interrupt an active AI spoken response (barge-in).
   */
  public interruptResponse(): void {
    if (
      !this.dataChannel ||
      this.dataChannel.readyState !== "open"
    ) {
      return;
    }

    try {
      this.dataChannel.send(JSON.stringify({ type: "response.cancel" }));
      this.dataChannel.send(
        JSON.stringify({ type: "output_audio_buffer.clear" })
      );
      this.activeResponseId = null;
      this.state = "listening";
      this.appendTelemetry(
        "outbound",
        "response.cancel",
        "Interrupted active AI response and returned to listening state."
      );
      this.emitSnapshot();
    } catch {
      // Ignore transient data channel send errors
    }
  }

  /**
   * Mute or unmute the local microphone track.
   */
  public setMuted(muted: boolean): void {
    this.isMuted = Boolean(muted);
    if (this.localStream) {
      for (const track of this.localStream.getAudioTracks()) {
        track.enabled = !this.isMuted;
      }
    }
    this.appendTelemetry(
      "lifecycle",
      this.isMuted ? "microphone.muted" : "microphone.unmuted",
      this.isMuted ? "Microphone muted by user." : "Microphone unmuted by user."
    );
    this.emitSnapshot();
  }

  /**
   * Update preferred conversation language (`en`, `hi`, or `hinglish`) for the active session.
   */
  public setPreferredLanguage(language: LanguageCodeType): void {
    this.preferredLanguage = language;
    this.appendTelemetry(
      "lifecycle",
      "language.selected",
      `Preferred conversation language set to ${language.toUpperCase()}.`
    );

    if (this.dataChannel && this.dataChannel.readyState === "open") {
      const langLabel =
        language === "hi"
          ? "Hindi (hi)"
          : language === "hinglish"
          ? "Hinglish (conversational Hindi-English mix)"
          : "English (en)";
      try {
        this.dataChannel.send(
          JSON.stringify({
            type: "conversation.item.create",
            item: {
              type: "message",
              role: "user",
              content: [
                {
                  type: "input_text",
                  text: `[Language Preference Updated: Please respond in ${langLabel} while keeping all safety and tool-calling rules intact.]`,
                },
              ],
            },
          })
        );
      } catch {
        // Ignore transient data channel send errors
      }
    }
    this.emitSnapshot();
  }

  /**
   * End the current voice session and release all WebRTC & microphone resources.
   */
  public endSession(): void {
    this.cleanupResources();
    this.state = "ended";
    this.activeSession = null;
    this.activeResponseId = null;
    this.expiresAtIso = null;
    this.lastToolExecution = null;
    this.escalationNotice = null;
    this.appendTelemetry(
      "lifecycle",
      "session.ended",
      "Voice session ended and audio tracks released."
    );
    this.emitSnapshot();
  }

  /**
   * Permanently dispose the client (e.g., on component unmount).
   */
  public destroy(): void {
    this.cleanupResources();
    if (typeof window !== "undefined" && this.boundPageUnloadHandler) {
      window.removeEventListener("pagehide", this.boundPageUnloadHandler);
      window.removeEventListener("beforeunload", this.boundPageUnloadHandler);
      this.boundPageUnloadHandler = null;
    }
  }

  private scheduleSessionExpiration(
    sessionData: VoiceSessionCreateResponseData
  ): void {
    if (this.expirationTimer) {
      clearTimeout(this.expirationTimer);
      this.expirationTimer = null;
    }

    const ttlMs = Math.max(1, sessionData.client_secret.ttl_seconds) * 1000;
    this.expirationTimer = setTimeout(() => {
      this.handleSessionExpired();
    }, ttlMs);
  }

  public handleSessionExpired(): void {
    this.transitionToError(
      "SESSION_EXPIRED",
      "Short-lived voice session credential expired. Click Reconnect to start a fresh session.",
      true
    );
  }

  private handleDataChannelMessage(rawData: unknown): void {
    if (typeof rawData !== "string") return;

    let parsed: RealtimeServerEvent;
    try {
      parsed = JSON.parse(rawData) as RealtimeServerEvent;
    } catch {
      return;
    }

    if (!parsed || typeof parsed.type !== "string") {
      return;
    }

    switch (parsed.type) {
      case "session.created":
      case "session.updated": {
        if (this.state === "connected" || this.state === "connecting") {
          this.state = "listening";
        }
        this.appendTelemetry(
          "inbound",
          parsed.type,
          "Realtime session configuration confirmed."
        );
        break;
      }

      case "input_audio_buffer.speech_started": {
        // Automatic barge-in when user begins speaking while AI is speaking
        if (this.state === "speaking") {
          this.interruptResponse();
        }
        this.state = "listening";
        this.appendTelemetry(
          "inbound",
          parsed.type,
          "Caller speech activity detected."
        );
        break;
      }

      case "input_audio_buffer.speech_stopped":
      case "input_audio_buffer.committed": {
        this.state = "processing";
        this.appendTelemetry(
          "inbound",
          parsed.type,
          "Caller turn complete; processing response."
        );
        break;
      }

      case "response.created": {
        const respId =
          "response" in parsed && parsed.response?.id
            ? String(parsed.response.id)
            : null;
        this.activeResponseId = respId;
        if (this.state !== "speaking") {
          this.state = "processing";
        }
        this.appendTelemetry(
          "inbound",
          parsed.type,
          "AI receptionist preparing spoken response."
        );
        break;
      }

      case "response.audio.delta":
      case "response.output_audio.delta":
      case "output_audio_buffer.started": {
        this.state = "speaking";
        this.appendTelemetry(
          "inbound",
          parsed.type,
          "Streaming AI voice output."
        );
        break;
      }

      case "output_audio_buffer.stopped":
      case "output_audio_buffer.cleared":
      case "response.audio.done":
      case "response.output_audio.done":
      case "response.done":
      case "response.cancelled": {
        this.activeResponseId = null;
        this.state = "listening";
        this.appendTelemetry(
          "inbound",
          parsed.type,
          "AI voice turn completed; listening for caller."
        );
        break;
      }

      case "response.function_call_arguments.done": {
        const callId =
          "call_id" in parsed && typeof parsed.call_id === "string"
            ? parsed.call_id
            : `call_${Date.now()}`;
        const toolNameRaw =
          "name" in parsed && typeof parsed.name === "string"
            ? parsed.name
            : "";
        const rawArguments =
          "arguments" in parsed && typeof parsed.arguments === "string"
            ? parsed.arguments
            : "{}";

        this.state = "processing";
        this.appendTelemetry(
          "inbound",
          parsed.type,
          `Realtime agent requested tool '${toolNameRaw}' (${callId}).`
        );
        void this.executeFunctionCallAndRespond(
          callId,
          toolNameRaw as AgentToolNameType,
          rawArguments
        );
        break;
      }

      case "error": {
        const errMessage =
          "error" in parsed && parsed.error?.message
            ? String(parsed.error.message)
            : "Realtime voice session reported an upstream error.";
        this.transitionToError("REALTIME_UPSTREAM_ERROR", errMessage, true);
        this.callbacks.onRealtimeEvent?.(parsed);
        return;
      }

      default: {
        this.appendTelemetry("inbound", parsed.type, "Realtime event received.");
        break;
      }
    }

    this.callbacks.onRealtimeEvent?.(parsed);
    this.emitSnapshot();
  }

  private async executeFunctionCallAndRespond(
    callId: string,
    toolName: AgentToolNameType,
    rawArguments: string
  ): Promise<void> {
    if (!this.activeSession) {
      return;
    }

    let parsedArgs: Record<string, unknown> = {};
    try {
      const candidate = JSON.parse(rawArguments || "{}") as unknown;
      if (candidate && typeof candidate === "object" && !Array.isArray(candidate)) {
        parsedArgs = candidate as Record<string, unknown>;
      }
    } catch {
      parsedArgs = {};
    }

    const executeToolFn =
      this.adapters.executeVoiceTool ?? executeVoiceToolApi;
    const accessToken = this.lastConnectArgs?.accessToken ?? null;
    const publicAccessToken = this.lastConnectArgs?.payload.public_access_token;

    let toolOutputPayload: Record<string, unknown>;

    try {
      const result = await executeToolFn(
        {
          session_id: this.activeSession.session_id,
          organization_id: this.activeSession.organization_id,
          business_id: this.activeSession.business_id,
          access_mode: this.activeSession.access_mode,
          public_access_token: publicAccessToken,
          call_id: callId,
          tool_name: toolName,
          arguments: parsedArgs,
        },
        accessToken
      );

      toolOutputPayload = result.output;
      this.lastToolExecution = {
        callId,
        toolName: result.tool_name,
        status: result.status,
        summary:
          result.status === "succeeded"
            ? `Validated & executed ${result.tool_name}`
            : `Tool ${result.tool_name} ${result.status}`,
        timestamp: new Date().toISOString(),
      };

      if (result.escalation_triggered && result.escalation_reference) {
        const out = result.output;
        this.escalationNotice = {
          escalationReference: result.escalation_reference,
          status:
            typeof out.status === "string"
              ? out.status
              : "pending_human_review",
          notificationDelivered: Boolean(out.notification_delivered),
          customerMessageDirective:
            typeof out.customer_message_directive === "string"
              ? out.customer_message_directive
              : "Escalation request logged for staff review (no automatic live staff notification delivered).",
        };
      }

      this.appendTelemetry(
        "lifecycle",
        `tool.${result.status}`,
        `Backend tool '${result.tool_name}' completed (${result.status}).`
      );
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Backend tool execution failed.";
      toolOutputPayload = {
        error: "tool_execution_failed",
        message: `${message} Do not claim the action succeeded.`,
      };
      this.lastToolExecution = {
        callId,
        toolName,
        status: "error",
        summary: `Tool ${toolName} failed: ${message}`,
        timestamp: new Date().toISOString(),
      };
      this.appendTelemetry(
        "lifecycle",
        "tool.error",
        `Tool '${toolName}' failed on backend.`
      );
    }

    if (this.dataChannel && this.dataChannel.readyState === "open") {
      try {
        this.dataChannel.send(
          JSON.stringify({
            type: "conversation.item.create",
            item: {
              type: "function_call_output",
              call_id: callId,
              output: JSON.stringify(toolOutputPayload),
            },
          })
        );
        this.dataChannel.send(
          JSON.stringify({
            type: "response.create",
          })
        );
        this.appendTelemetry(
          "outbound",
          "conversation.item.create",
          `Returned validated tool output for '${toolName}' (${callId}) to Realtime session.`
        );
      } catch {
        // Ignore data channel send errors
      }
    }

    this.emitSnapshot();
  }

  /**
   * Idempotently stop microphone tracks, close data channel, reset remote audio,
   * and close RTCPeerConnection.
   */
  public cleanupResources(): void {
    if (this.expirationTimer) {
      clearTimeout(this.expirationTimer);
      this.expirationTimer = null;
    }

    if (this.dataChannel) {
      try {
        this.dataChannel.onopen = null;
        this.dataChannel.onmessage = null;
        this.dataChannel.onerror = null;
        this.dataChannel.onclose = null;
        this.dataChannel.close();
      } catch {
        // Ignore close errors
      }
      this.dataChannel = null;
    }

    if (this.localStream) {
      try {
        for (const track of this.localStream.getTracks()) {
          track.stop();
        }
      } catch {
        // Ignore stop errors
      }
      this.localStream = null;
    }

    if (this.remoteAudioElement) {
      try {
        const isJsdom =
          typeof navigator !== "undefined" &&
          typeof navigator.userAgent === "string" &&
          navigator.userAgent.toLowerCase().includes("jsdom");
        if (!isJsdom && typeof this.remoteAudioElement.pause === "function") {
          this.remoteAudioElement.pause();
        }
        this.remoteAudioElement.srcObject = null;
      } catch {
        // Ignore audio reset errors
      }
      this.remoteAudioElement = null;
    }

    if (this.peerConnection) {
      try {
        this.peerConnection.ontrack = null;
        this.peerConnection.onconnectionstatechange = null;
        this.peerConnection.close();
      } catch {
        // Ignore peer connection close errors
      }
      this.peerConnection = null;
    }
  }
}
