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
  MicrophoneDiagnosticsState,
  MicrophonePermissionState,
  RealtimeEventTelemetryEntry,
  RealtimeServerEvent,
  RemotePlaybackState,
  ResponseErrorState,
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

const MAX_TELEMETRY_EVENTS = 60;

const DEFAULT_MIC_DIAGNOSTICS: MicrophoneDiagnosticsState = {
  trackAttached: false,
  trackEnabled: false,
  trackReadyState: "unknown",
  trackMutedBySystem: false,
  inputLevel: 0,
  hasDetectedAudioActivity: false,
};

const DEFAULT_PLAYBACK_STATE: RemotePlaybackState = {
  remoteTrackReceived: false,
  autoplayBlocked: false,
  isPlaying: false,
  warningMessage: null,
};

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
  private isUserSpeaking = false;
  private activeSession: VoiceSessionCreateResponseData | null = null;
  private error: VoiceClientError | null = null;
  private responseError: ResponseErrorState | null = null;
  private activeResponseId: string | null = null;
  private expiresAtIso: string | null = null;
  private events: RealtimeEventTelemetryEntry[] = [];
  private preferredLanguage: LanguageCodeType = "en";
  private lastToolExecution: LastToolExecutionState | null = null;
  private escalationNotice: HumanEscalationNoticeState | null = null;
  private microphoneDiagnostics: MicrophoneDiagnosticsState = {
    ...DEFAULT_MIC_DIAGNOSTICS,
  };
  private playbackState: RemotePlaybackState = {
    ...DEFAULT_PLAYBACK_STATE,
  };

  private peerConnection: RTCPeerConnection | null = null;
  private dataChannel: RTCDataChannel | null = null;
  private localStream: MediaStream | null = null;
  private remoteAudioElement: HTMLAudioElement | null = null;
  private remoteAudioAttachedToDom = false;
  private audioContext: AudioContext | null = null;
  private micMonitorTimer: ReturnType<typeof setInterval> | null = null;
  private isOutputAudioBufferActive = false;
  private pendingToolCallCount = 0;
  private loggedAudioDeltaForResponseId: string | null = null;
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
      isUserSpeaking: this.isUserSpeaking,
      activeSession: this.activeSession,
      error: this.error,
      responseError: this.responseError,
      activeResponseId: this.activeResponseId,
      expiresAtIso: this.expiresAtIso,
      events: [...this.events],
      preferredLanguage: this.preferredLanguage,
      lastToolExecution: this.lastToolExecution,
      escalationNotice: this.escalationNotice,
      microphoneDiagnostics: { ...this.microphoneDiagnostics },
      playbackState: { ...this.playbackState },
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
    this.responseError = null;
    this.isMuted = false;
    this.isUserSpeaking = false;
    this.activeResponseId = null;
    this.isOutputAudioBufferActive = false;
    this.pendingToolCallCount = 0;
    this.loggedAudioDeltaForResponseId = null;
    this.lastToolExecution = null;
    this.escalationNotice = null;
    this.microphoneDiagnostics = { ...DEFAULT_MIC_DIAGNOSTICS };
    this.playbackState = { ...DEFAULT_PLAYBACK_STATE };

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

      const primaryTrack = audioTracks[0];
      if (!primaryTrack.enabled) {
        primaryTrack.enabled = true;
      }
      const readyState =
        typeof primaryTrack.readyState === "string"
          ? primaryTrack.readyState
          : "live";
      if (readyState === "ended") {
        this.permissionState = "no_device";
        this.transitionToError(
          "MICROPHONE_CAPTURE_ERROR",
          "Microphone audio track ended immediately after capture. Check your browser or OS microphone settings."
        );
        return;
      }

      this.localStream = stream;
      this.permissionState = "granted";
      this.microphoneDiagnostics = {
        trackAttached: false,
        trackEnabled: Boolean(primaryTrack.enabled),
        trackReadyState: readyState === "live" ? "live" : "unknown",
        trackMutedBySystem: Boolean(primaryTrack.muted),
        inputLevel: 0,
        hasDetectedAudioActivity: false,
      };
      this.attachMicrophoneTrackListeners(primaryTrack);
      this.startMicrophoneLevelMonitor(stream);
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
          el.muted = false;
          el.volume = 1.0;
          (el as HTMLAudioElement & { playsInline?: boolean }).playsInline = true;
          el.setAttribute("playsinline", "true");
          el.setAttribute("data-testid", "svario-remote-audio");
          el.className = "sr-only";
          if (typeof document !== "undefined" && document.body) {
            document.body.appendChild(el);
            this.remoteAudioAttachedToDom = true;
          }
          return el;
        });
      const audioEl = createAudio();
      this.remoteAudioElement = audioEl;

      pc.ontrack = (event: RTCTrackEvent) => {
        if (!this.remoteAudioElement) return;
        let remoteStream: MediaStream | null =
          event.streams && event.streams[0] ? event.streams[0] : null;
        if (!remoteStream && event.track && typeof MediaStream !== "undefined") {
          remoteStream = new MediaStream([event.track]);
        }
        if (!remoteStream) return;

        this.remoteAudioElement.srcObject = remoteStream;
        this.playbackState = {
          ...this.playbackState,
          remoteTrackReceived: true,
        };
        this.appendTelemetry(
          "lifecycle",
          "webrtc.remote_track",
          "Remote AI audio track received and attached to browser audio element."
        );
        this.emitSnapshot();
        void this.attemptRemoteAudioPlayback();
      };

      pc.onconnectionstatechange = () => {
        if (!this.peerConnection) return;
        const connState = this.peerConnection.connectionState;
        this.appendTelemetry(
          "lifecycle",
          `webrtc.connection.${connState}`,
          `WebRTC peer connection state changed to '${connState}'.`
        );
        if (connState === "failed" || connState === "disconnected") {
          this.transitionToError(
            "WEBRTC_CONNECTION_FAILED",
            `WebRTC peer connection ${connState}. Check your network connection and reconnect.`
          );
          return;
        }
        this.emitSnapshot();
      };

      pc.oniceconnectionstatechange = () => {
        if (!this.peerConnection) return;
        const iceState = this.peerConnection.iceConnectionState;
        this.appendTelemetry(
          "lifecycle",
          `webrtc.ice.${iceState}`,
          `WebRTC ICE connection state: '${iceState}'.`
        );
        if (iceState === "failed") {
          this.transitionToError(
            "WEBRTC_CONNECTION_FAILED",
            "WebRTC ICE connection failed. Check firewall or network connectivity and reconnect."
          );
          return;
        }
        this.emitSnapshot();
      };

      // Attach local microphone tracks
      for (const track of this.localStream.getAudioTracks()) {
        track.enabled = !this.isMuted;
        pc.addTrack(track, this.localStream);
      }
      const attachedTrack = this.localStream.getAudioTracks()[0];
      this.microphoneDiagnostics = {
        ...this.microphoneDiagnostics,
        trackAttached: true,
        trackEnabled: Boolean(attachedTrack?.enabled),
        trackReadyState:
          attachedTrack && typeof attachedTrack.readyState === "string"
            ? attachedTrack.readyState === "live"
              ? "live"
              : "ended"
            : "live",
      };
      this.appendTelemetry(
        "lifecycle",
        "microphone.track_attached",
        `Local microphone track attached (enabled=${this.microphoneDiagnostics.trackEnabled}, state=${this.microphoneDiagnostics.trackReadyState}).`
      );

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

      dc.onclose = () => {
        if (
          this.state !== "ended" &&
          this.state !== "idle" &&
          this.state !== "error"
        ) {
          this.transitionToError(
            "WEBRTC_CONNECTION_FAILED",
            "Realtime event data channel closed unexpectedly. Click Reconnect to resume."
          );
        }
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
   * User-initiated recovery when browser autoplay policies block remote AI audio playback.
   */
  public async resumePlayback(): Promise<boolean> {
    return this.attemptRemoteAudioPlayback(true);
  }

  private async attemptRemoteAudioPlayback(isUserInitiated = false): Promise<boolean> {
    if (!this.remoteAudioElement) {
      return false;
    }

    const isJsdom =
      typeof navigator !== "undefined" &&
      typeof navigator.userAgent === "string" &&
      navigator.userAgent.toLowerCase().includes("jsdom");
    if (isJsdom && !this.adapters.createAudioElement) {
      return true;
    }

    if (typeof this.remoteAudioElement.play !== "function") {
      return true;
    }

    try {
      await this.remoteAudioElement.play();
      this.playbackState = {
        ...this.playbackState,
        autoplayBlocked: false,
        isPlaying: true,
        warningMessage: null,
      };
      this.appendTelemetry(
        "lifecycle",
        isUserInitiated ? "playback.resumed" : "playback.started",
        isUserInitiated
          ? "Remote AI audio playback resumed by user interaction."
          : "Remote AI audio playback active."
      );
      this.emitSnapshot();
      return true;
    } catch (err: unknown) {
      const reason =
        err instanceof Error && err.message
          ? err.message
          : "Browser blocked automatic audio playback.";
      this.playbackState = {
        ...this.playbackState,
        autoplayBlocked: true,
        isPlaying: false,
        warningMessage:
          "Browser autoplay policy blocked AI voice playback. Click Enable AI Audio to hear responses.",
      };
      this.appendTelemetry(
        "lifecycle",
        "playback.autoplay_blocked",
        `Audio playback blocked (${reason}). User interaction required to resume.`
      );
      this.emitSnapshot();
      return false;
    }
  }

  private attachMicrophoneTrackListeners(track: MediaStreamTrack): void {
    try {
      track.onended = () => {
        this.microphoneDiagnostics = {
          ...this.microphoneDiagnostics,
          trackReadyState: "ended",
          trackEnabled: false,
          inputLevel: 0,
        };
        this.appendTelemetry(
          "lifecycle",
          "microphone.track_ended",
          "Microphone audio track ended unexpectedly."
        );
        this.emitSnapshot();
      };
      track.onmute = () => {
        this.microphoneDiagnostics = {
          ...this.microphoneDiagnostics,
          trackMutedBySystem: true,
          inputLevel: 0,
        };
        this.appendTelemetry(
          "lifecycle",
          "microphone.system_muted",
          "Microphone track was muted by browser or operating system."
        );
        this.emitSnapshot();
      };
      track.onunmute = () => {
        this.microphoneDiagnostics = {
          ...this.microphoneDiagnostics,
          trackMutedBySystem: false,
        };
        this.appendTelemetry(
          "lifecycle",
          "microphone.system_unmuted",
          "Microphone track unmuted by browser or operating system."
        );
        this.emitSnapshot();
      };
    } catch {
      // Ignore listener attachment errors on minimal mock tracks
    }
  }

  private startMicrophoneLevelMonitor(stream: MediaStream): void {
    if (typeof window === "undefined") return;
    const isJsdom =
      typeof navigator !== "undefined" &&
      typeof navigator.userAgent === "string" &&
      navigator.userAgent.toLowerCase().includes("jsdom");
    if (isJsdom) return;

    const AudioCtx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext })
        .webkitAudioContext;
    if (!AudioCtx) return;

    try {
      const ctx = new AudioCtx();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      this.audioContext = ctx;

      const dataArray = new Uint8Array(analyser.fftSize);
      this.micMonitorTimer = setInterval(() => {
        if (!this.localStream || this.isMuted) {
          if (this.microphoneDiagnostics.inputLevel !== 0) {
            this.microphoneDiagnostics = {
              ...this.microphoneDiagnostics,
              inputLevel: 0,
            };
            this.emitSnapshot();
          }
          return;
        }
        analyser.getByteTimeDomainData(dataArray);
        let sumSq = 0;
        for (let i = 0; i < dataArray.length; i += 1) {
          const norm = (dataArray[i] - 128) / 128;
          sumSq += norm * norm;
        }
        const rms = Math.sqrt(sumSq / dataArray.length);
        const roundedLevel = Math.min(1, Math.round(rms * 100) / 100);
        const detectedNow = rms > 0.01;
        const firstDetection =
          detectedNow && !this.microphoneDiagnostics.hasDetectedAudioActivity;

        if (
          firstDetection ||
          Math.abs(roundedLevel - this.microphoneDiagnostics.inputLevel) >= 0.04
        ) {
          this.microphoneDiagnostics = {
            ...this.microphoneDiagnostics,
            inputLevel: roundedLevel,
            hasDetectedAudioActivity:
              this.microphoneDiagnostics.hasDetectedAudioActivity || detectedNow,
          };
          if (firstDetection) {
            this.appendTelemetry(
              "lifecycle",
              "microphone.signal_detected",
              "Non-zero microphone audio activity detected locally."
            );
          }
          this.emitSnapshot();
        }
      }, 250);
    } catch {
      // Non-fatal: diagnostic meter unavailable in restricted environments
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
      this.isOutputAudioBufferActive = false;
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
    if (this.isMuted) {
      this.isUserSpeaking = false;
    }
    if (this.localStream) {
      for (const track of this.localStream.getAudioTracks()) {
        track.enabled = !this.isMuted;
      }
    }
    this.microphoneDiagnostics = {
      ...this.microphoneDiagnostics,
      trackEnabled: !this.isMuted,
      inputLevel: this.isMuted ? 0 : this.microphoneDiagnostics.inputLevel,
    };
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
    this.isUserSpeaking = false;
    this.activeSession = null;
    this.activeResponseId = null;
    this.responseError = null;
    this.expiresAtIso = null;
    this.lastToolExecution = null;
    this.escalationNotice = null;
    this.microphoneDiagnostics = { ...DEFAULT_MIC_DIAGNOSTICS };
    this.playbackState = { ...DEFAULT_PLAYBACK_STATE };
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
        const sessionInfo =
          "session" in parsed && parsed.session ? parsed.session : null;
        const modelLabel = sessionInfo?.model ? ` (${sessionInfo.model})` : "";
        this.appendTelemetry(
          "inbound",
          parsed.type,
          `Realtime session configuration confirmed${modelLabel}.`
        );
        break;
      }

      case "input_audio_buffer.speech_started": {
        // Server-side VAD has interrupt_response=true, so avoid sending redundant response.cancel
        // that can trigger non-fatal response_cancel_not_active upstream errors.
        if (this.state === "speaking") {
          this.activeResponseId = null;
          this.isOutputAudioBufferActive = false;
        }
        this.responseError = null;
        this.isUserSpeaking = true;
        this.state = "listening";
        this.appendTelemetry(
          "inbound",
          parsed.type,
          "Caller speech activity detected by server VAD."
        );
        break;
      }

      case "input_audio_buffer.speech_stopped": {
        this.isUserSpeaking = false;
        this.state = "processing";
        this.appendTelemetry(
          "inbound",
          parsed.type,
          "Caller speech stopped; waiting for AI response."
        );
        break;
      }

      case "input_audio_buffer.committed": {
        this.isUserSpeaking = false;
        this.state = "processing";
        this.appendTelemetry(
          "inbound",
          parsed.type,
          "Caller audio buffer committed; processing response."
        );
        break;
      }

      case "input_audio_buffer.timeout_triggered": {
        this.isUserSpeaking = false;
        this.appendTelemetry(
          "inbound",
          parsed.type,
          "Input audio buffer idle timeout triggered."
        );
        break;
      }

      case "conversation.item.input_audio_transcription.completed": {
        this.appendTelemetry(
          "inbound",
          parsed.type,
          "Input audio transcription completed (transcript not stored)."
        );
        break;
      }

      case "conversation.item.input_audio_transcription.failed": {
        const transErr =
          "error" in parsed && parsed.error?.message
            ? String(parsed.error.message)
            : "Transcription failed.";
        this.appendTelemetry(
          "inbound",
          parsed.type,
          `Input audio transcription failed: ${transErr}`
        );
        break;
      }

      case "response.created": {
        const respId =
          "response" in parsed && parsed.response?.id
            ? String(parsed.response.id)
            : null;
        this.activeResponseId = respId;
        this.loggedAudioDeltaForResponseId = null;
        this.responseError = null;
        this.isUserSpeaking = false;
        if (this.state !== "speaking") {
          this.state = "processing";
        }
        this.appendTelemetry(
          "inbound",
          parsed.type,
          `AI receptionist preparing spoken response${respId ? ` (${respId})` : ""}.`
        );
        break;
      }

      case "response.output_item.added": {
        const itemType =
          "item" in parsed && parsed.item?.type
            ? String(parsed.item.type)
            : "item";
        const itemName =
          "item" in parsed && parsed.item?.name
            ? ` (${String(parsed.item.name)})`
            : "";
        if (itemType === "function_call") {
          this.state = "processing";
        }
        this.appendTelemetry(
          "inbound",
          parsed.type,
          `Response output item added: ${itemType}${itemName}.`
        );
        break;
      }

      case "response.content_part.added": {
        const partType =
          "part" in parsed && parsed.part?.type
            ? String(parsed.part.type)
            : "content";
        this.appendTelemetry(
          "inbound",
          parsed.type,
          `Response content part added (${partType}).`
        );
        break;
      }

      case "response.audio.delta":
      case "response.output_audio.delta": {
        this.state = "speaking";
        this.isUserSpeaking = false;
        const deltaRespKey = this.activeResponseId ?? "__active__";
        if (this.loggedAudioDeltaForResponseId !== deltaRespKey) {
          this.loggedAudioDeltaForResponseId = deltaRespKey;
          this.appendTelemetry(
            "inbound",
            parsed.type,
            "Streaming AI voice audio output."
          );
        }
        break;
      }

      case "output_audio_buffer.started": {
        this.isOutputAudioBufferActive = true;
        this.state = "speaking";
        this.isUserSpeaking = false;
        this.appendTelemetry(
          "inbound",
          parsed.type,
          "Remote AI audio playback started."
        );
        break;
      }

      case "response.audio.done":
      case "response.output_audio.done": {
        if (!this.isOutputAudioBufferActive && this.pendingToolCallCount === 0) {
          this.state = "listening";
        }
        this.appendTelemetry(
          "inbound",
          parsed.type,
          "AI voice audio generation finished."
        );
        break;
      }

      case "output_audio_buffer.stopped":
      case "output_audio_buffer.cleared": {
        this.isOutputAudioBufferActive = false;
        this.activeResponseId = null;
        if (this.pendingToolCallCount === 0) {
          this.state = "listening";
        }
        this.appendTelemetry(
          "inbound",
          parsed.type,
          "AI audio playback completed; listening for caller."
        );
        break;
      }

      case "response.done": {
        const resp =
          "response" in parsed && parsed.response ? parsed.response : null;
        const respStatus = resp?.status ? String(resp.status) : "completed";
        this.activeResponseId = null;
        this.loggedAudioDeltaForResponseId = null;

        if (respStatus === "failed") {
          const failCode = resp?.status_details?.error?.code
            ? String(resp.status_details.error.code)
            : "RESPONSE_FAILED";
          const failMessage = resp?.status_details?.error?.message
            ? String(resp.status_details.error.message)
            : "The AI failed to generate a voice response.";
          this.isOutputAudioBufferActive = false;
          this.responseError = {
            code: failCode,
            message: failMessage,
            timestamp: new Date().toISOString(),
          };
          this.state = "listening";
          this.appendTelemetry(
            "inbound",
            "response.done.failed",
            `AI response failed (${failCode}): ${failMessage}`
          );
        } else if (respStatus === "cancelled") {
          this.isOutputAudioBufferActive = false;
          this.state = "listening";
          this.appendTelemetry(
            "inbound",
            parsed.type,
            "AI response cancelled; listening for caller."
          );
        } else {
          if (
            !this.isOutputAudioBufferActive &&
            this.pendingToolCallCount === 0
          ) {
            this.state = "listening";
          }
          this.appendTelemetry(
            "inbound",
            parsed.type,
            `AI response turn ${respStatus}.`
          );
        }
        break;
      }

      case "response.cancelled": {
        this.activeResponseId = null;
        this.isOutputAudioBufferActive = false;
        this.loggedAudioDeltaForResponseId = null;
        this.state = "listening";
        this.appendTelemetry(
          "inbound",
          parsed.type,
          "AI voice turn cancelled; listening for caller."
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
        this.pendingToolCallCount += 1;
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
        const errCode =
          "error" in parsed && parsed.error?.code
            ? String(parsed.error.code)
            : "REALTIME_UPSTREAM_ERROR";
        const errMessage =
          "error" in parsed && parsed.error?.message
            ? String(parsed.error.message)
            : "Realtime voice session reported an upstream error.";

        // Non-fatal cancellation race when server VAD already interrupted the active turn
        if (errCode === "response_cancel_not_active") {
          this.appendTelemetry(
            "inbound",
            "error.non_fatal",
            `Ignored non-fatal cancellation notice: ${errMessage}`
          );
          break;
        }

        if (
          errCode === "conversation_already_has_active_response" ||
          errCode === "invalid_request_error"
        ) {
          this.responseError = {
            code: errCode,
            message: errMessage,
            timestamp: new Date().toISOString(),
          };
          this.appendTelemetry(
            "inbound",
            `error.${errCode}`,
            `Realtime response error: ${errMessage}`
          );
          break;
        }

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
    const startedAtMs = Date.now();
    try {
      if (!this.activeSession) {
        return;
      }

      let parsedArgs: Record<string, unknown> = {};
      let malformedArgsError: string | null = null;
      try {
        const candidate = JSON.parse(rawArguments || "{}") as unknown;
        if (candidate && typeof candidate === "object" && !Array.isArray(candidate)) {
          parsedArgs = candidate as Record<string, unknown>;
        } else {
          malformedArgsError = "Function arguments must be a JSON object.";
        }
      } catch {
        malformedArgsError = "Malformed JSON in function call arguments.";
      }

      const safeArgKeys = Object.keys(parsedArgs).filter(
        (k) =>
          ![
            "customer_name",
            "customer_phone",
            "customer_email",
            "patient_display_name",
            "patient_contact",
            "notes",
          ].includes(k)
      );

      let toolOutputPayload: Record<string, unknown>;

      if (malformedArgsError) {
        toolOutputPayload = {
          error: "invalid_tool_arguments",
          message: `${malformedArgsError} Do not claim the action succeeded.`,
        };
        this.lastToolExecution = {
          callId,
          toolName,
          status: "rejected",
          summary: `Tool ${toolName} rejected: ${malformedArgsError}`,
          timestamp: new Date().toISOString(),
        };
        this.appendTelemetry(
          "lifecycle",
          "tool.rejected",
          `Rejected '${toolName}' (${callId}): ${malformedArgsError}`
        );
      } else {
        const executeToolFn =
          this.adapters.executeVoiceTool ?? executeVoiceToolApi;
        const accessToken = this.lastConnectArgs?.accessToken ?? null;
        const publicAccessToken = this.lastConnectArgs?.payload.public_access_token;

        this.appendTelemetry(
          "outbound",
          "tool.backend_request",
          `Calling backend for '${toolName}' (${callId}; keys=[${safeArgKeys.join(", ")}]).`
        );

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

          const durationMs = Math.max(0, Date.now() - startedAtMs);
          toolOutputPayload = result.output;
          const outputMessage =
            typeof result.output?.message === "string"
              ? result.output.message
              : null;

          this.lastToolExecution = {
            callId,
            toolName: result.tool_name,
            status: result.status,
            summary:
              result.status === "succeeded"
                ? `Validated & executed ${result.tool_name} (${durationMs}ms)`
                : `Tool ${result.tool_name} ${result.status}${outputMessage ? `: ${outputMessage}` : ""} (${durationMs}ms)`,
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
            `Backend tool '${result.tool_name}' ${result.status} in ${durationMs}ms${outputMessage && result.status !== "succeeded" ? ` — ${outputMessage}` : ""}.`
          );
        } catch (err: unknown) {
          const durationMs = Math.max(0, Date.now() - startedAtMs);
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
            summary: `Tool ${toolName} failed (${durationMs}ms): ${message}`,
            timestamp: new Date().toISOString(),
          };
          this.appendTelemetry(
            "lifecycle",
            "tool.error",
            `Tool '${toolName}' failed on backend (${durationMs}ms): ${message}`
          );
        }
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
            `Returned validated tool output for '${toolName}' (${callId}) and triggered response.create.`
          );
        } catch {
          this.appendTelemetry(
            "lifecycle",
            "tool.send_error",
            `Failed to send function_call_output for '${toolName}' (${callId}) over oai-events.`
          );
        }
      }
    } finally {
      this.pendingToolCallCount = Math.max(0, this.pendingToolCallCount - 1);
      this.emitSnapshot();
    }
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

    if (this.micMonitorTimer) {
      clearInterval(this.micMonitorTimer);
      this.micMonitorTimer = null;
    }

    if (this.audioContext) {
      try {
        void this.audioContext.close();
      } catch {
        // Ignore AudioContext close errors
      }
      this.audioContext = null;
    }

    this.isOutputAudioBufferActive = false;
    this.pendingToolCallCount = 0;
    this.loggedAudioDeltaForResponseId = null;

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
          track.onended = null;
          track.onmute = null;
          track.onunmute = null;
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
        if (
          this.remoteAudioAttachedToDom &&
          typeof this.remoteAudioElement.remove === "function"
        ) {
          this.remoteAudioElement.remove();
        }
      } catch {
        // Ignore audio reset errors
      }
      this.remoteAudioElement = null;
      this.remoteAudioAttachedToDom = false;
    }

    if (this.peerConnection) {
      try {
        this.peerConnection.ontrack = null;
        this.peerConnection.onconnectionstatechange = null;
        this.peerConnection.oniceconnectionstatechange = null;
        this.peerConnection.close();
      } catch {
        // Ignore peer connection close errors
      }
      this.peerConnection = null;
    }
  }
}
