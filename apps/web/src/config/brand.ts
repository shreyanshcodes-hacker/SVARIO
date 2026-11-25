import type { IndustryCardItem, SharedSubsystemItem } from "@/types/platform";

export const SVARIO_BRAND = {
  name: "SVARIO",
  tagline: "AI that speaks for your business.",
  style: "Premium futuristic",
  stageNumber: 2,
  stageTitle: "STAGE 2 — INDUSTRY SELECTION & BUSINESS ONBOARDING",
  version: "2.0",
  description:
    "Svario is a multi-industry AI Voice Agent Platform engineered for high-reliability inbound reception, domain-governed conversation routing, and real-time scheduling orchestration across Salons, Clinics, and Hospitals.",
  colors: {
    midnightNavy: "#0B1020",
    deepIndigo: "#171D33",
    electricViolet: "#7657F6",
    cyberTeal: "#36C6D3",
    cloudWhite: "#F5F7FC",
    silverMist: "#A7B0C4",
  },
} as const;

export const SVARIO_INDUSTRIES: readonly IndustryCardItem[] = [
  {
    id: "salons",
    name: "Salons",
    availability: "available",
    categoryLabel: "SALONS",
    headline: "High-Touch Hospitality & Stylist Desk Concierge",
    description:
      "Designed for hair, beauty, and grooming studios to handle inbound calls, answer service and pricing questions, check live availability, and book appointments automatically.",
    voicePersona: "Warm, brand-aligned hospitality concierge",
    plannedHighlights: [
      "Service catalog & pricing information",
      "Live stylist availability & automatic booking",
      "Appointment rescheduling & cancellation handling",
      "Public salon website with embedded AI receptionist",
    ],
    sharedSubsystems: ["Voice", "AI Policy", "Scheduling", "Notifications"],
  },
  {
    id: "clinics",
    name: "Clinics",
    availability: "coming_soon",
    categoryLabel: "CLINICS",
    headline: "Structured Patient Intake & Practitioner Desk Coordination",
    description:
      "Planned for outpatient, dental, dermatology, physiotherapy, and specialty clinics needing calm appointment coordination and front-desk call support.",
    voicePersona: "Empathetic, structured clinical coordinator",
    plannedHighlights: [],
    sharedSubsystems: ["Voice", "AI Policy", "Scheduling", "Notifications"],
  },
  {
    id: "hospitals",
    name: "Hospitals",
    availability: "coming_soon",
    categoryLabel: "HOSPITALS",
    headline: "24/7 Departmental Switchboard & Escalation Support",
    description:
      "Planned for multi-specialty hospitals and medical centers needing departmental inquiry routing, visiting hours guidance, and high-volume front-desk support.",
    voicePersona: "Calm, authoritative institutional switchboard operator",
    plannedHighlights: [],
    sharedSubsystems: ["Voice", "AI Policy", "Scheduling", "Notifications"],
  },
] as const;

export const SHARED_PLATFORM_SUBSYSTEMS: readonly SharedSubsystemItem[] = [
  {
    id: "voice",
    name: "Shared Voice Runtime",
    plannedStack: "OpenAI Realtime API (Planned)",
    description:
      "Low-latency bidirectional audio streaming, turn detection, and interruption handling shared across all verticals.",
  },
  {
    id: "ai",
    name: "Domain AI & Guardrail Engine",
    plannedStack: "Pydantic + Structured Policies",
    description:
      "Injects industry-specific personas, non-diagnostic clinical boundaries, and human-escalation triggers.",
  },
  {
    id: "scheduling",
    name: "Unified Scheduling Core",
    plannedStack: "Supabase PostgreSQL (Planned)",
    description:
      "Abstracts stylist chairs, clinic consultation rooms, and hospital OPD rosters behind a common slot contract.",
  },
  {
    id: "notifications",
    name: "Notification & Handoff Bus",
    plannedStack: "Supabase Realtime & Adapters (Planned)",
    description:
      "Dispatches structured call summaries, front-desk alerts, and confirmation events after every voice session.",
  },
] as const;
