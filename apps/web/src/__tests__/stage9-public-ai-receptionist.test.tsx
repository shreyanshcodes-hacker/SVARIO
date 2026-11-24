import React from "react";
import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { PublicBookingWebsiteRenderer } from "@/components/booking-website/PublicBookingWebsiteRenderer";
import { resolveReceptionistTemplateTheme } from "@/components/booking-website/receptionist/template-theme-adapter";
import type { WebRtcEnvironmentAdapters } from "@/lib/voice/webrtcClient";
import {
  APPROVED_TEMPLATE_IDS,
  type BookingWebsiteTemplateId,
  type PublicBookingWebsiteData,
} from "@/types/website";

function makePublicWebsiteData(
  templateId: BookingWebsiteTemplateId,
  overrides: Partial<PublicBookingWebsiteData> = {}
): PublicBookingWebsiteData {
  return {
    slug: "riya-women-salon",
    template_id: templateId,
    published_at: "2026-11-24T12:00:00Z",
    headline: "Luxury Hair & Botanical Care",
    tagline: "Tailored salon rituals in Mumbai.",
    logo_url: null,
    cover_image_url: null,
    primary_color: "#7657F6",
    secondary_color: "#36C6D3",
    accent_color: "#D4AF37",
    background_color: "#0B1020",
    text_color: "#F5F7FC",
    theme: "dark",
    font_family: "inter",
    button_style: "rounded",
    social_instagram: null,
    social_facebook: null,
    social_whatsapp: null,
    show_services: true,
    show_hours: true,
    show_ai_receptionist: true,
    business: {
      display_name: "Riya Women Salon",
      description: "Modern women's beauty studio",
      phone: "+919876543210",
      email: "hello@riyasalon.example",
      address: "14 Linking Road",
      city: "Mumbai",
      state: "MH",
      country: "India",
      timezone: "Asia/Kolkata",
    },
    hours: [
      { weekday: 1, is_closed: false, opens_at: "10:00", closes_at: "20:00", is_overnight: false },
    ],
    services: [
      {
        id: "svc-1",
        name: "Basic Haircut",
        category: "Hair",
        description: "Precision cut & blow dry",
        duration_minutes: 30,
        price: 299,
        currency: "INR",
      },
    ],
    receptionist: {
      enabled: true,
      assistant_name: "Riya AI Receptionist",
      greeting: "Hello! Ask me about services, prices, or availability.",
    },
    ...overrides,
  };
}

describe("Stage 3 — Template-Aware Public AI Receptionist Integration", () => {
  afterEach(() => {
    cleanup();
  });

  it.each(APPROVED_TEMPLATE_IDS)(
    "adapts receptionist styling automatically for template '%s' without altering the template",
    (templateId) => {
      const data = makePublicWebsiteData(templateId);
      const theme = resolveReceptionistTemplateTheme(data);
      expect(theme.templateId).toBe(templateId);

      render(<PublicBookingWebsiteRenderer data={data} />);

      // Existing locked template still renders intact
      expect(screen.getByTestId(`template-${templateId}`)).toBeTruthy();

      // Receptionist launcher inherits the exact template theme
      const launcher = screen.getByTestId("public-ai-receptionist-launcher");
      expect(launcher.getAttribute("data-template-theme")).toBe(templateId);

      // Opening the panel preserves template theme and closes cleanly
      fireEvent.click(launcher);
      const panel = screen.getByTestId("public-ai-receptionist-panel");
      expect(panel.getAttribute("data-template-theme")).toBe(templateId);
      expect(panel.textContent).toContain("Riya AI Receptionist");

      fireEvent.click(screen.getByTestId("close-ai-receptionist-button"));
      expect(screen.queryByTestId("public-ai-receptionist-panel")).toBeNull();
    }
  );

  it("hides receptionist entry point when disabled on the salon website", () => {
    const disabledData = makePublicWebsiteData("minimal_elegance", {
      show_ai_receptionist: false,
      receptionist: { enabled: false, assistant_name: null, greeting: null },
    });
    render(<PublicBookingWebsiteRenderer data={disabledData} />);
    expect(screen.queryByTestId("public-ai-receptionist-launcher")).toBeNull();
  });

  it("reuses the locked SvarioWebRtcVoiceClient for connect, mute, and disconnect", async () => {
    const track = {
      enabled: true,
      readyState: "live",
      muted: false,
      stop: vi.fn(),
    } as unknown as MediaStreamTrack;
    const stream = {
      getTracks: () => [track],
      getAudioTracks: () => [track],
    } as unknown as MediaStream;

    const fakeChannel = {
      readyState: "open",
      send: vi.fn(),
      close: vi.fn(),
      onopen: null as (() => void) | null,
      onmessage: null as ((ev: MessageEvent) => void) | null,
      onerror: null as (() => void) | null,
      onclose: null as (() => void) | null,
    };

    const fakePc = {
      connectionState: "connected",
      iceConnectionState: "connected",
      addTrack: vi.fn(),
      createDataChannel: vi.fn(() => {
        setTimeout(() => fakeChannel.onopen?.(), 0);
        return fakeChannel;
      }),
      createOffer: vi.fn(async () => ({ type: "offer", sdp: "v=0-offer" })),
      setLocalDescription: vi.fn(async () => undefined),
      setRemoteDescription: vi.fn(async () => undefined),
      close: vi.fn(),
      ontrack: null,
      onconnectionstatechange: null,
      oniceconnectionstatechange: null,
    } as unknown as RTCPeerConnection;

    const createVoiceSession = vi.fn(async () => ({
      session_id: "sess_public_test_1",
      organization_id: "public-slug-session",
      business_id: "public-slug-session",
      industry: "salon" as const,
      access_mode: "public_visitor" as const,
      model: "gpt-realtime",
      voice: "alloy",
      webrtc_url: "https://api.openai.com/v1/realtime/calls",
      webrtc_calls_url: "https://api.openai.com/v1/realtime/calls",
      data_channel_label: "oai-events",
      client_secret: {
        value: "ek_ephemeral_123",
        expires_at: new Date(Date.now() + 120_000).toISOString(),
        ttl_seconds: 120,
      },
      capabilities: {
        modalities: ["audio", "text"],
        barge_in_enabled: true,
        raw_audio_storage_enabled: false,
        transcript_storage_enabled: false,
        appointment_booking_enabled: true,
        industry_workflows_enabled: true,
      },
      assistant_context: {
        business_name: "Riya Women Salon",
        assistant_name: "Riya AI Receptionist",
        greeting: "Hello!",
        primary_language: "en" as const,
        supported_languages: ["en" as const],
        personality: "warm" as const,
        response_style: "balanced" as const,
        assistant_enabled: true,
        administrative_only_guardrails: false,
        audio_persistence_enabled: false,
        transcript_persistence_enabled: false,
      },
    }));

    const adapters: WebRtcEnvironmentAdapters = {
      getUserMedia: vi.fn(async () => stream),
      createPeerConnection: vi.fn(() => fakePc),
      createAudioElement: vi.fn(() => ({ play: vi.fn(async () => undefined) }) as unknown as HTMLAudioElement),
      createVoiceSession,
      exchangeSdpOffer: vi.fn(async () => "v=0-answer"),
    };

    render(
      <PublicBookingWebsiteRenderer
        data={makePublicWebsiteData("blush_beauty")}
        voiceAdapters={adapters}
      />
    );

    fireEvent.click(screen.getByTestId("public-ai-receptionist-launcher"));
    fireEvent.click(screen.getByTestId("start-public-voice-button"));

    await waitFor(() => {
      expect(createVoiceSession).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId("mute-public-voice-button")).toBeTruthy();
    });

    // Mute toggle uses locked SvarioWebRtcVoiceClient
    fireEvent.click(screen.getByTestId("mute-public-voice-button"));
    expect(track.enabled).toBe(false);
    expect(screen.getByTestId("mute-public-voice-button").textContent).toContain("Unmute");

    // Disconnect cleans up session
    fireEvent.click(screen.getByTestId("disconnect-public-voice-button"));
    await waitFor(() => {
      expect(screen.getByTestId("start-public-voice-button")).toBeTruthy();
    });
  });
});
