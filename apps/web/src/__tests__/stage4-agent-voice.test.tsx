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
import { VoiceTestView } from "@/components/voice/VoiceTestView";
import {
  AuthOrganizationContext,
  type AuthOrganizationContextValue,
} from "@/context/AuthOrganizationContext";
import type {
  OrganizationSummary,
  VoiceSessionCreateResponseData,
  VoiceToolExecutionPayload,
  VoiceToolExecutionResponseData,
} from "@/types/platform";
import type { Session, User } from "@supabase/supabase-js";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
  }),
}));

const sampleOrg: OrganizationSummary = {
  id: "22222222-2222-4222-8222-222222222222",
  name: "Pulse Heart Clinic",
  slug: "pulse-heart-clinic",
  industry: "clinic",
  membership_role: "owner",
  created_at: "2026-11-10T10:00:00Z",
  updated_at: "2026-11-10T10:00:00Z",
};

function buildMockAuthContext(): AuthOrganizationContextValue {
  const fakeUser = {
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    email: "operator@svario.ai",
  } as unknown as User;
  const fakeSession = {
    access_token: "test-jwt-token-stage4",
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

function buildSampleSessionResponse(): VoiceSessionCreateResponseData {
  return {
    session_id: "sess_stage4_test_101",
    organization_id: sampleOrg.id,
    business_id: "bbbbbbbb-2222-4222-8222-222222222222",
    industry: "clinic",
    access_mode: "organization_member",
    model: "gpt-realtime",
    voice: "alloy",
    webrtc_url: "https://api.openai.com/v1/realtime/calls",
    webrtc_calls_url: "https://api.openai.com/v1/realtime/calls",
    data_channel_label: "oai-events",
    client_secret: {
      value: "ek_short_lived_stage4_token_001",
      expires_at: new Date(Date.now() + 120 * 1000).toISOString(),
      ttl_seconds: 120,
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
      business_name: "Pulse Heart Clinic",
      assistant_name: "Pulse Clinic Receptionist",
      greeting: "Hello, welcome to Pulse Heart Clinic!",
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

function createFakeWebRtcHarness() {
  const dataChannels: FakeDataChannel[] = [];
  const toolExecutions: VoiceToolExecutionPayload[] = [];

  const getUserMedia = vi.fn().mockImplementation(async () => {
    const track = {
      enabled: true,
      stop: vi.fn(),
    };
    return {
      getAudioTracks: () => [track],
      getTracks: () => [track],
    } as unknown as MediaStream;
  });

  const createPeerConnection = vi.fn().mockImplementation(() => {
    return {
      connectionState: "connected" as RTCPeerConnectionState,
      ontrack: null,
      onconnectionstatechange: null,
      localDescription: { type: "offer", sdp: "v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\n" },
      addTrack: vi.fn(),
      createDataChannel: vi.fn((label: string) => {
        const dc: FakeDataChannel = {
          label,
          readyState: "open",
          onopen: null,
          onmessage: null,
          onerror: null,
          onclose: null,
          send: vi.fn(),
          close: vi.fn(),
        };
        dataChannels.push(dc);
        return dc as unknown as RTCDataChannel;
      }),
      createOffer: vi.fn().mockResolvedValue({
        type: "offer",
        sdp: "v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\n",
      }),
      setLocalDescription: vi.fn().mockResolvedValue(undefined),
      setRemoteDescription: vi.fn().mockResolvedValue(undefined),
      close: vi.fn(),
    } as unknown as RTCPeerConnection;
  });

  const createVoiceSession = vi
    .fn()
    .mockResolvedValue(buildSampleSessionResponse());

  const exchangeSdpOffer = vi
    .fn()
    .mockResolvedValue("v=0\r\no=- 2 2 IN IP4 127.0.0.1\r\n");

  const executeVoiceTool = vi
    .fn()
    .mockImplementation(
      async (
        payload: VoiceToolExecutionPayload
      ): Promise<VoiceToolExecutionResponseData> => {
        toolExecutions.push(payload);
        if (payload.tool_name === "request_human_escalation") {
          return {
            session_id: payload.session_id,
            call_id: payload.call_id,
            tool_name: "request_human_escalation",
            status: "succeeded",
            output: {
              accepted: true,
              escalation_reference: "ESC-STAGE401",
              status: "pending_human_review",
              notification_delivered: false,
              customer_message_directive:
                "Escalation request ESC-STAGE401 has been recorded with status 'pending_human_review'. Do NOT claim a person has already been contacted live.",
            },
            escalation_triggered: true,
            escalation_reference: "ESC-STAGE401",
            detected_language: "en",
          };
        }
        return {
          session_id: payload.session_id,
          call_id: payload.call_id,
          tool_name: payload.tool_name,
          status: "succeeded",
          output: {
            has_verified_answer: true,
            matches: [
              {
                source_type: "business_faq",
                record_id: "faq-001",
                category: "specialities",
                question_or_topic: "Available clinic specialities",
                verified_answer: "We provide Cardiology and Dermatology consultations.",
                relevance_score: 0.92,
              },
            ],
          },
          escalation_triggered: false,
          escalation_reference: null,
          detected_language: "en",
        };
      }
    );

  return {
    dataChannels,
    toolExecutions,
    adapters: {
      getUserMedia,
      createPeerConnection,
      createVoiceSession,
      exchangeSdpOffer,
      executeVoiceTool,
    },
  };
}

describe("Stage 4 — Realtime Agent Tool Calling, Escalation UI & Language Selector", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("executes backend tools on response.function_call_arguments.done and returns function_call_output over oai-events", async () => {
    const harness = createFakeWebRtcHarness();
    const authCtx = buildMockAuthContext();

    render(
      <AuthOrganizationContext.Provider value={authCtx}>
        <VoiceTestView testAdapters={harness.adapters} />
      </AuthOrganizationContext.Provider>
    );

    fireEvent.click(screen.getByTestId("start-conversation-button"));

    await waitFor(() => {
      expect(harness.dataChannels.length).toBe(1);
    });

    const dc = harness.dataChannels[0];
    act(() => {
      dc.onmessage?.({
        data: JSON.stringify({
          type: "response.function_call_arguments.done",
          call_id: "call_knowledge_99",
          name: "search_business_knowledge",
          arguments: JSON.stringify({ query: "cardiology specialities" }),
        }),
      } as MessageEvent);
    });

    await waitFor(() => {
      expect(harness.toolExecutions.length).toBe(1);
    });

    expect(harness.toolExecutions[0].tool_name).toBe("search_business_knowledge");
    expect(harness.toolExecutions[0].call_id).toBe("call_knowledge_99");

    // Verify client sent function_call_output and response.create over oai-events
    await waitFor(() => {
      expect(dc.send).toHaveBeenCalledTimes(2);
    });

    const firstSent = JSON.parse(dc.send.mock.calls[0][0] as string) as {
      type: string;
      item: { type: string; call_id: string; output: string };
    };
    const secondSent = JSON.parse(dc.send.mock.calls[1][0] as string) as {
      type: string;
    };

    expect(firstSent.type).toBe("conversation.item.create");
    expect(firstSent.item.type).toBe("function_call_output");
    expect(firstSent.item.call_id).toBe("call_knowledge_99");
    expect(firstSent.item.output).toContain("Cardiology");
    expect(secondSent.type).toBe("response.create");

    // Verify UI badge shows last executed tool
    const badge = screen.getByTestId("last-tool-execution-badge");
    expect(badge.textContent).toContain("search_business_knowledge");
    expect(badge.textContent?.toLowerCase()).toContain("succeeded");
  });

  it("displays the human escalation status banner when request_human_escalation succeeds", async () => {
    const harness = createFakeWebRtcHarness();
    const authCtx = buildMockAuthContext();

    render(
      <AuthOrganizationContext.Provider value={authCtx}>
        <VoiceTestView testAdapters={harness.adapters} />
      </AuthOrganizationContext.Provider>
    );

    fireEvent.click(screen.getByTestId("start-conversation-button"));

    await waitFor(() => {
      expect(harness.dataChannels.length).toBe(1);
    });

    const dc = harness.dataChannels[0];
    act(() => {
      dc.onmessage?.({
        data: JSON.stringify({
          type: "response.function_call_arguments.done",
          call_id: "call_esc_77",
          name: "request_human_escalation",
          arguments: JSON.stringify({
            reason: "Clinical question",
            summary: "Patient asked for prescription advice",
            urgency: "clinical_staff",
          }),
        }),
      } as MessageEvent);
    });

    await waitFor(() => {
      expect(screen.getByTestId("human-escalation-banner")).toBeDefined();
    });

    const banner = screen.getByTestId("human-escalation-banner");
    expect(banner.textContent).toContain("ESC-STAGE401");
    expect(banner.textContent).toContain("pending_human_review");
    expect(banner.textContent).toContain(
      "Do NOT claim a person has already been contacted live"
    );
  });

  it("allows selecting English, Hindi, or Hinglish and sends a language update over oai-events", async () => {
    const harness = createFakeWebRtcHarness();
    const authCtx = buildMockAuthContext();

    render(
      <AuthOrganizationContext.Provider value={authCtx}>
        <VoiceTestView testAdapters={harness.adapters} />
      </AuthOrganizationContext.Provider>
    );

    fireEvent.click(screen.getByTestId("start-conversation-button"));

    await waitFor(() => {
      expect(harness.dataChannels.length).toBe(1);
    });

    const langSelect = screen.getByTestId(
      "voice-language-select"
    ) as HTMLSelectElement;
    expect(langSelect.value).toBe("en");

    fireEvent.change(langSelect, { target: { value: "hinglish" } });
    expect(langSelect.value).toBe("hinglish");

    const dc = harness.dataChannels[0];
    expect(dc.send).toHaveBeenCalledTimes(1);
    const sentPayload = JSON.parse(dc.send.mock.calls[0][0] as string) as {
      type: string;
      item: { content: Array<{ text: string }> };
    };
    expect(sentPayload.type).toBe("conversation.item.create");
    expect(sentPayload.item.content[0].text).toContain("Hinglish");
  });

  it("handles salon tool execution errors and malformed arguments cleanly while preserving call_id", async () => {
    const harness = createFakeWebRtcHarness();
    harness.adapters.executeVoiceTool = vi
      .fn()
      .mockRejectedValueOnce(new Error("Slot already booked for stylist."));
    const authCtx = buildMockAuthContext();

    render(
      <AuthOrganizationContext.Provider value={authCtx}>
        <VoiceTestView testAdapters={harness.adapters} />
      </AuthOrganizationContext.Provider>
    );

    fireEvent.click(screen.getByTestId("start-conversation-button"));

    await waitFor(() => {
      expect(harness.dataChannels.length).toBe(1);
    });

    const dc = harness.dataChannels[0];

    // 1. Backend error returned cleanly with original call_id
    act(() => {
      dc.onmessage?.({
        data: JSON.stringify({
          type: "response.function_call_arguments.done",
          call_id: "call_salon_err_42",
          name: "create_salon_appointment",
          arguments: JSON.stringify({
            service_id: "svc-1",
            appointment_date: "2026-11-25",
            start_time: "16:00",
            customer_name: "Asha",
            customer_phone: "9876543210",
          }),
        }),
      } as MessageEvent);
    });

    await waitFor(() => {
      expect(dc.send).toHaveBeenCalledTimes(2);
    });

    const errItem = JSON.parse(dc.send.mock.calls[0][0] as string) as {
      type: string;
      item: { call_id: string; output: string };
    };
    const errRespCreate = JSON.parse(dc.send.mock.calls[1][0] as string) as {
      type: string;
    };
    expect(errItem.item.call_id).toBe("call_salon_err_42");
    expect(errItem.item.output).toContain("Slot already booked for stylist.");
    expect(errItem.item.output).toContain("Do not claim the action succeeded");
    expect(errRespCreate.type).toBe("response.create");

    // 2. Malformed JSON arguments rejected safely without calling backend
    act(() => {
      dc.onmessage?.({
        data: JSON.stringify({
          type: "response.function_call_arguments.done",
          call_id: "call_malformed_99",
          name: "get_salon_services",
          arguments: "{bad-json",
        }),
      } as MessageEvent);
    });

    await waitFor(() => {
      expect(dc.send).toHaveBeenCalledTimes(4);
    });
    const malformedItem = JSON.parse(dc.send.mock.calls[2][0] as string) as {
      item: { call_id: string; output: string };
    };
    expect(malformedItem.item.call_id).toBe("call_malformed_99");
    expect(malformedItem.item.output).toContain("invalid_tool_arguments");
  });
});
