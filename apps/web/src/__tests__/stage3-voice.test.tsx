import React from "react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
  act,
} from "@testing-library/react";
import VoiceTestPage from "@/app/voice-test/page";
import { VoiceTestView } from "@/components/voice/VoiceTestView";
import {
  AuthOrganizationContext,
  type AuthOrganizationContextValue,
} from "@/context/AuthOrganizationContext";
import type {
  OrganizationSummary,
  VoiceSessionCreateResponseData,
} from "@/types/platform";
import type { Session, User } from "@supabase/supabase-js";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
  }),
}));

const sampleOrg: OrganizationSummary = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Aura Clinic Center",
  slug: "aura-clinic-center",
  industry: "clinic",
  membership_role: "owner",
  created_at: "2026-11-09T10:00:00Z",
  updated_at: "2026-11-09T10:00:00Z",
};

function buildMockAuthContext(): AuthOrganizationContextValue {
  const fakeUser = {
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    email: "operator@svario.ai",
  } as unknown as User;
  const fakeSession = {
    access_token: "test-jwt-token-stage3",
    user: fakeUser,
  } as unknown as Session;

  return {
    supabaseConfigured: true,
    isInitializing: false,
    isLoadingOrganizations: false,
    session: fakeSession,
    supabaseUser: fakeUser,
    verifiedBackendUser: null,
    backendAuthError: null,
    organizations: [sampleOrg],
    activeOrganization: sampleOrg,
    setActiveOrganizationId: vi.fn(),
    refreshOrganizations: vi.fn().mockResolvedValue(undefined),
    createOrganization: vi.fn().mockResolvedValue(sampleOrg),
    signOut: vi.fn().mockResolvedValue(undefined),
  };
}

function buildSampleSessionResponse(
  ttlSeconds = 120
): VoiceSessionCreateResponseData {
  return {
    session_id: "sess_stage3_test_901",
    organization_id: sampleOrg.id,
    business_id: "bbbbbbbb-1111-4111-8111-111111111111",
    industry: "clinic",
    access_mode: "organization_member",
    model: "gpt-4o-realtime-preview",
    voice: "alloy",
    webrtc_url: "https://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview",
    webrtc_calls_url: "https://api.openai.com/v1/realtime/calls",
    data_channel_label: "oai-events",
    client_secret: {
      value: "ek_short_lived_ephemeral_token_001",
      expires_at: new Date(Date.now() + ttlSeconds * 1000).toISOString(),
      ttl_seconds: ttlSeconds,
    },
    capabilities: {
      modalities: ["audio", "text"],
      barge_in_enabled: true,
      raw_audio_storage_enabled: false,
      transcript_storage_enabled: false,
      appointment_booking_enabled: false,
      industry_workflows_enabled: false,
    },
    assistant_context: {
      business_name: "Aura Clinic Center",
      assistant_name: "Svario Clinic Assistant",
      greeting: "Hello, welcome to Aura Clinic Center!",
      primary_language: "en",
      supported_languages: ["en", "hi", "hinglish"],
      personality: "warm",
      response_style: "balanced",
      assistant_enabled: true,
      administrative_only_guardrails: true,
      audio_persistence_enabled: false,
      transcript_persistence_enabled: false,
    },
  };
}

interface FakeMediaTrack {
  enabled: boolean;
  stop: ReturnType<typeof vi.fn>;
}

interface FakeDataChannel {
  label: string;
  readyState: RTCDataChannelState;
  onopen: (() => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  onerror: (() => void) | null;
  onclose: (() => void) | null;
  send: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
}

interface FakePeerConnection {
  connectionState: RTCPeerConnectionState;
  localDescription: RTCSessionDescriptionInit | null;
  remoteDescription: RTCSessionDescriptionInit | null;
  ontrack: ((ev: RTCTrackEvent) => void) | null;
  onconnectionstatechange: (() => void) | null;
  addTrack: ReturnType<typeof vi.fn>;
  createDataChannel: (label: string) => FakeDataChannel;
  createOffer: () => Promise<RTCSessionDescriptionInit>;
  setLocalDescription: (desc: RTCSessionDescriptionInit) => Promise<void>;
  setRemoteDescription: (desc: RTCSessionDescriptionInit) => Promise<void>;
  close: ReturnType<typeof vi.fn>;
  dataChannel: FakeDataChannel | null;
}

function createFakeMediaStream(): {
  stream: MediaStream;
  track: FakeMediaTrack;
} {
  const track: FakeMediaTrack = {
    enabled: true,
    stop: vi.fn(),
  };
  const stream = {
    getAudioTracks: () => [track as unknown as MediaStreamTrack],
    getTracks: () => [track as unknown as MediaStreamTrack],
  } as unknown as MediaStream;
  return { stream, track };
}

function createFakePeerConnection(): FakePeerConnection {
  const pc: FakePeerConnection = {
    connectionState: "connected",
    localDescription: null,
    remoteDescription: null,
    ontrack: null,
    onconnectionstatechange: null,
    addTrack: vi.fn(),
    dataChannel: null,
    createDataChannel(label: string) {
      const dc: FakeDataChannel = {
        label,
        readyState: "open",
        onopen: null,
        onmessage: null,
        onerror: null,
        onclose: null,
        send: vi.fn(),
        close: vi.fn(() => {
          dc.readyState = "closed";
        }),
      };
      this.dataChannel = dc;
      return dc;
    },
    async createOffer() {
      return { type: "offer", sdp: "v=0\r\no=- 123 1 IN IP4 127.0.0.1\r\n" };
    },
    async setLocalDescription(desc: RTCSessionDescriptionInit) {
      this.localDescription = desc;
    },
    async setRemoteDescription(desc: RTCSessionDescriptionInit) {
      this.remoteDescription = desc;
    },
    close: vi.fn(function (this: FakePeerConnection) {
      this.connectionState = "closed";
    }),
  };
  return pc;
}

describe("Stage 3 Shared Browser Voice Infrastructure", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it("1. renders the dedicated voice-test page with Svario voice orb, status indicators, and controls", () => {
    const authCtx = buildMockAuthContext();
    render(
      <AuthOrganizationContext.Provider value={authCtx}>
        <VoiceTestPage />
      </AuthOrganizationContext.Provider>
    );

    expect(
      screen.getByText(/Svario Voice Receptionist Test Lab/i)
    ).toBeDefined();
    expect(
      screen.getByTestId("voice-orb-waveform").getAttribute("data-voice-state")
    ).toBe("idle");
    expect(
      (screen.getByTestId("start-conversation-button") as HTMLButtonElement)
        .disabled
    ).toBe(false);
    expect(
      (screen.getByTestId("end-conversation-button") as HTMLButtonElement)
        .disabled
    ).toBe(true);
    expect(screen.getByTestId("mic-permission-status").textContent).toContain(
      "Ready to Request"
    );
  });

  it("2. handles microphone permission denied state cleanly", async () => {
    const authCtx = buildMockAuthContext();
    const deniedError = new Error("Permission denied by user");
    deniedError.name = "NotAllowedError";

    render(
      <AuthOrganizationContext.Provider value={authCtx}>
        <VoiceTestView
          testAdapters={{
            getUserMedia: vi.fn().mockRejectedValue(deniedError),
          }}
        />
      </AuthOrganizationContext.Provider>
    );

    fireEvent.click(screen.getByTestId("start-conversation-button"));

    await waitFor(() => {
      expect(
        screen
          .getByTestId("voice-orb-waveform")
          .getAttribute("data-voice-state")
      ).toBe("error");
    });

    expect(screen.getByTestId("mic-permission-status").textContent).toContain(
      "Permission Denied"
    );
    expect(screen.getByTestId("voice-error-banner").textContent).toContain(
      "MICROPHONE_PERMISSION_DENIED"
    );
  });

  it("3. transitions through connecting state while negotiating session and WebRTC SDP", async () => {
    const authCtx = buildMockAuthContext();
    const { stream } = createFakeMediaStream();

    let resolveSessionPromise!: (val: VoiceSessionCreateResponseData) => void;
    const pendingSessionPromise = new Promise<VoiceSessionCreateResponseData>(
      (resolve) => {
        resolveSessionPromise = resolve;
      }
    );

    render(
      <AuthOrganizationContext.Provider value={authCtx}>
        <VoiceTestView
          testAdapters={{
            getUserMedia: vi.fn().mockResolvedValue(stream),
            createVoiceSession: vi.fn().mockReturnValue(pendingSessionPromise),
            createPeerConnection: () =>
              createFakePeerConnection() as unknown as RTCPeerConnection,
            exchangeSdpOffer: vi.fn().mockResolvedValue("v=0\r\na=answer\r\n"),
          }}
        />
      </AuthOrganizationContext.Provider>
    );

    fireEvent.click(screen.getByTestId("start-conversation-button"));

    await waitFor(() => {
      expect(
        screen
          .getByTestId("voice-orb-waveform")
          .getAttribute("data-voice-state")
      ).toBe("connecting");
    });

    expect(screen.getByTestId("connecting-indicator").textContent).toContain(
      "Connecting..."
    );

    await act(async () => {
      resolveSessionPromise(buildSampleSessionResponse());
    });

    await waitFor(() => {
      expect(
        screen
          .getByTestId("voice-orb-waveform")
          .getAttribute("data-voice-state")
      ).toBe("listening");
    });
  });

  it("4. handles connection failure safely and cleans up captured microphone tracks", async () => {
    const authCtx = buildMockAuthContext();
    const { stream, track } = createFakeMediaStream();

    render(
      <AuthOrganizationContext.Provider value={authCtx}>
        <VoiceTestView
          testAdapters={{
            getUserMedia: vi.fn().mockResolvedValue(stream),
            createVoiceSession: vi
              .fn()
              .mockResolvedValue(buildSampleSessionResponse()),
            createPeerConnection: () =>
              createFakePeerConnection() as unknown as RTCPeerConnection,
            exchangeSdpOffer: vi
              .fn()
              .mockRejectedValue(
                new Error("WebRTC SDP negotiation failed with HTTP 502.")
              ),
          }}
        />
      </AuthOrganizationContext.Provider>
    );

    fireEvent.click(screen.getByTestId("start-conversation-button"));

    await waitFor(() => {
      expect(
        screen
          .getByTestId("voice-orb-waveform")
          .getAttribute("data-voice-state")
      ).toBe("error");
    });

    expect(screen.getByTestId("voice-error-banner").textContent).toContain(
      "SDP_NEGOTIATION_FAILED"
    );
    expect(track.stop).toHaveBeenCalledTimes(1);
  });

  it("5. cleans up microphone tracks and closes RTCPeerConnection on user disconnect", async () => {
    const authCtx = buildMockAuthContext();
    const { stream, track } = createFakeMediaStream();
    const fakePc = createFakePeerConnection();

    render(
      <AuthOrganizationContext.Provider value={authCtx}>
        <VoiceTestView
          testAdapters={{
            getUserMedia: vi.fn().mockResolvedValue(stream),
            createVoiceSession: vi
              .fn()
              .mockResolvedValue(buildSampleSessionResponse()),
            createPeerConnection: () => fakePc as unknown as RTCPeerConnection,
            exchangeSdpOffer: vi.fn().mockResolvedValue("v=0\r\na=answer\r\n"),
          }}
        />
      </AuthOrganizationContext.Provider>
    );

    fireEvent.click(screen.getByTestId("start-conversation-button"));

    await waitFor(() => {
      expect(
        screen
          .getByTestId("voice-orb-waveform")
          .getAttribute("data-voice-state")
      ).toBe("listening");
    });

    // Verify mute/unmute toggles track.enabled
    fireEvent.click(screen.getByTestId("mute-unmute-button"));
    expect(track.enabled).toBe(false);
    expect(screen.getByTestId("voice-muted-pill")).toBeDefined();

    // End conversation -> stops tracks & closes peerConnection
    fireEvent.click(screen.getByTestId("end-conversation-button"));

    await waitFor(() => {
      expect(
        screen
          .getByTestId("voice-orb-waveform")
          .getAttribute("data-voice-state")
      ).toBe("ended");
    });

    expect(track.stop).toHaveBeenCalledTimes(1);
    expect(fakePc.close).toHaveBeenCalledTimes(1);
  });

  it("6. handles ephemeral session expiration cleanly", async () => {
    vi.useFakeTimers();
    const authCtx = buildMockAuthContext();
    const { stream, track } = createFakeMediaStream();
    const fakePc = createFakePeerConnection();

    render(
      <AuthOrganizationContext.Provider value={authCtx}>
        <VoiceTestView
          testAdapters={{
            getUserMedia: vi.fn().mockResolvedValue(stream),
            createVoiceSession: vi
              .fn()
              .mockResolvedValue(buildSampleSessionResponse(5)),
            createPeerConnection: () => fakePc as unknown as RTCPeerConnection,
            exchangeSdpOffer: vi.fn().mockResolvedValue("v=0\r\na=answer\r\n"),
          }}
        />
      </AuthOrganizationContext.Provider>
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("start-conversation-button"));
    });

    expect(
      screen.getByTestId("voice-orb-waveform").getAttribute("data-voice-state")
    ).toBe("listening");

    // Advance timer past the 5-second ephemeral credential TTL
    await act(async () => {
      vi.advanceTimersByTime(5500);
    });

    expect(
      screen.getByTestId("voice-orb-waveform").getAttribute("data-voice-state")
    ).toBe("error");
    expect(screen.getByTestId("voice-error-banner").textContent).toContain(
      "SESSION_EXPIRED"
    );
    expect(track.stop).toHaveBeenCalledTimes(1);
    expect(fakePc.close).toHaveBeenCalledTimes(1);
  });

  it("7. reconnects without leaking RTCPeerConnection or MediaStreamTrack instances", async () => {
    const authCtx = buildMockAuthContext();
    const createdStreams: Array<{ stream: MediaStream; track: FakeMediaTrack }> =
      [];
    const createdPeerConnections: FakePeerConnection[] = [];

    render(
      <AuthOrganizationContext.Provider value={authCtx}>
        <VoiceTestView
          testAdapters={{
            getUserMedia: vi.fn().mockImplementation(async () => {
              const pair = createFakeMediaStream();
              createdStreams.push(pair);
              return pair.stream;
            }),
            createVoiceSession: vi
              .fn()
              .mockResolvedValue(buildSampleSessionResponse()),
            createPeerConnection: () => {
              const pc = createFakePeerConnection();
              createdPeerConnections.push(pc);
              return pc as unknown as RTCPeerConnection;
            },
            exchangeSdpOffer: vi.fn().mockResolvedValue("v=0\r\na=answer\r\n"),
          }}
        />
      </AuthOrganizationContext.Provider>
    );

    // First connection
    fireEvent.click(screen.getByTestId("start-conversation-button"));

    await waitFor(() => {
      expect(
        screen
          .getByTestId("voice-orb-waveform")
          .getAttribute("data-voice-state")
      ).toBe("listening");
    });

    expect(createdPeerConnections).toHaveLength(1);
    expect(createdStreams).toHaveLength(1);

    // Trigger Reconnect -> must close first PC and stop first track before creating second PC
    fireEvent.click(screen.getByTestId("reconnect-session-button"));

    await waitFor(() => {
      expect(createdPeerConnections).toHaveLength(2);
      expect(
        screen
          .getByTestId("voice-orb-waveform")
          .getAttribute("data-voice-state")
      ).toBe("listening");
    });

    expect(createdStreams[0].track.stop).toHaveBeenCalledTimes(1);
    expect(createdPeerConnections[0].close).toHaveBeenCalledTimes(1);
    expect(createdPeerConnections[1].close).not.toHaveBeenCalled();
  });

  it("8. transitions accurately through speech detection, thinking, AI speaking, barge-in, and listening", async () => {
    const authCtx = buildMockAuthContext();
    const { stream } = createFakeMediaStream();
    const fakePc = createFakePeerConnection();

    render(
      <AuthOrganizationContext.Provider value={authCtx}>
        <VoiceTestView
          testAdapters={{
            getUserMedia: vi.fn().mockResolvedValue(stream),
            createVoiceSession: vi
              .fn()
              .mockResolvedValue(buildSampleSessionResponse()),
            createPeerConnection: () => fakePc as unknown as RTCPeerConnection,
            exchangeSdpOffer: vi.fn().mockResolvedValue("v=0\r\na=answer\r\n"),
          }}
        />
      </AuthOrganizationContext.Provider>
    );

    fireEvent.click(screen.getByTestId("start-conversation-button"));

    await waitFor(() => {
      expect(fakePc.dataChannel).not.toBeNull();
    });

    const dc = fakePc.dataChannel!;
    expect(screen.getByTestId("listening-indicator").textContent).toContain("Listening");

    // 1. User begins speaking -> Listening / speech detected
    act(() => {
      dc.onmessage?.({
        data: JSON.stringify({ type: "input_audio_buffer.speech_started" }),
      } as MessageEvent);
    });
    expect(screen.getByTestId("listening-indicator").textContent).toContain(
      "Listening / speech detected"
    );

    // 2. User finishes speaking -> Thinking
    act(() => {
      dc.onmessage?.({
        data: JSON.stringify({ type: "input_audio_buffer.speech_stopped" }),
      } as MessageEvent);
    });
    expect(screen.getByTestId("speaking-indicator").textContent).toContain("Thinking");

    // 3. AI starts generating/playing audio -> AI Speaking
    act(() => {
      dc.onmessage?.({
        data: JSON.stringify({
          type: "response.created",
          response: { id: "resp_001" },
        }),
      } as MessageEvent);
      dc.onmessage?.({
        data: JSON.stringify({ type: "output_audio_buffer.started" }),
      } as MessageEvent);
      dc.onmessage?.({
        data: JSON.stringify({ type: "response.output_audio.delta" }),
      } as MessageEvent);
    });
    expect(screen.getByTestId("speaking-indicator").textContent).toContain("AI Speaking");

    // 4. Non-fatal response_cancel_not_active error does NOT tear down the session
    act(() => {
      dc.onmessage?.({
        data: JSON.stringify({
          type: "error",
          error: {
            code: "response_cancel_not_active",
            message: "Cancellation failed: no active response found",
          },
        }),
      } as MessageEvent);
    });
    expect(
      screen.getByTestId("voice-orb-waveform").getAttribute("data-voice-state")
    ).toBe("speaking");

    // 5. AI finishes playback -> Listening
    act(() => {
      dc.onmessage?.({
        data: JSON.stringify({ type: "output_audio_buffer.stopped" }),
      } as MessageEvent);
    });
    expect(screen.getByTestId("listening-indicator").textContent).toContain("Listening");
    expect(screen.getByTestId("voice-event-telemetry").textContent).toContain(
      "output_audio_buffer.stopped"
    );
  });

  it("9. surfaces AI response failures as Response Error instead of silently showing Silent", async () => {
    const authCtx = buildMockAuthContext();
    const { stream } = createFakeMediaStream();
    const fakePc = createFakePeerConnection();

    render(
      <AuthOrganizationContext.Provider value={authCtx}>
        <VoiceTestView
          testAdapters={{
            getUserMedia: vi.fn().mockResolvedValue(stream),
            createVoiceSession: vi
              .fn()
              .mockResolvedValue(buildSampleSessionResponse()),
            createPeerConnection: () => fakePc as unknown as RTCPeerConnection,
            exchangeSdpOffer: vi.fn().mockResolvedValue("v=0\r\na=answer\r\n"),
          }}
        />
      </AuthOrganizationContext.Provider>
    );

    fireEvent.click(screen.getByTestId("start-conversation-button"));

    await waitFor(() => {
      expect(fakePc.dataChannel).not.toBeNull();
    });

    const dc = fakePc.dataChannel!;
    act(() => {
      dc.onmessage?.({
        data: JSON.stringify({
          type: "response.done",
          response: {
            id: "resp_failed_01",
            status: "failed",
            status_details: {
              type: "failed",
              error: {
                code: "insufficient_quota",
                message: "You exceeded your current quota.",
              },
            },
          },
        }),
      } as MessageEvent);
    });

    expect(screen.getByTestId("speaking-indicator").textContent).toContain(
      "Response Error"
    );
    expect(screen.getByTestId("voice-response-error-banner").textContent).toContain(
      "You exceeded your current quota."
    );
  });

  it("10. exposes browser autoplay playback failure and recovers via Enable AI Audio button", async () => {
    const authCtx = buildMockAuthContext();
    const { stream } = createFakeMediaStream();
    const fakePc = createFakePeerConnection();
    const playMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("NotAllowedError: play() failed because user didn't interact"))
      .mockResolvedValueOnce(undefined);
    const fakeAudioEl = {
      autoplay: true,
      muted: false,
      volume: 1,
      srcObject: null as MediaStream | null,
      play: playMock,
      pause: vi.fn(),
      setAttribute: vi.fn(),
    } as unknown as HTMLAudioElement;

    render(
      <AuthOrganizationContext.Provider value={authCtx}>
        <VoiceTestView
          testAdapters={{
            getUserMedia: vi.fn().mockResolvedValue(stream),
            createVoiceSession: vi
              .fn()
              .mockResolvedValue(buildSampleSessionResponse()),
            createPeerConnection: () => fakePc as unknown as RTCPeerConnection,
            createAudioElement: () => fakeAudioEl,
            exchangeSdpOffer: vi.fn().mockResolvedValue("v=0\r\na=answer\r\n"),
          }}
        />
      </AuthOrganizationContext.Provider>
    );

    fireEvent.click(screen.getByTestId("start-conversation-button"));

    await waitFor(() => {
      expect(fakePc.ontrack).not.toBeNull();
    });

    // Simulate incoming remote AI audio track -> autoplay rejected
    await act(async () => {
      fakePc.ontrack?.({
        streams: [stream],
      } as unknown as RTCTrackEvent);
    });

    await waitFor(() => {
      expect(screen.getByTestId("voice-playback-warning-banner")).toBeDefined();
    });
    expect(screen.getByTestId("remote-playback-status").textContent).toContain(
      "Autoplay Blocked"
    );

    // Click user-initiated recovery button -> play() succeeds and warning disappears
    fireEvent.click(screen.getByTestId("resume-playback-button"));

    await waitFor(() => {
      expect(screen.queryByTestId("voice-playback-warning-banner")).toBeNull();
    });
    expect(playMock).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("remote-playback-status").textContent).toContain(
      "Active"
    );
  });
});
