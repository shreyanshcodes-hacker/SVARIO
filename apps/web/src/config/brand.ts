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
    categoryLabel: "INDUSTRY VERTICAL 01",
    headline: "High-Touch Hospitality & Stylist Desk Concierge",
    description:
      "Designed for hair, beauty, and grooming studios to handle peak-hour inbound calls, treatment duration inquiries, stylist tier preferences, and front-desk call overflow.",
    voicePersona: "Warm, brand-aligned hospitality concierge",
    plannedHighlights: [
      "Service catalog & package duration guidance",
      "Stylist & specialist tier preference boundaries",
      "Peak-hour call overflow & deposit policy answers",
      "Rescheduling & cancellation window handling",
    ],
    sharedSubsystems: ["Voice", "AI Policy", "Scheduling", "Notifications"],
  },
  {
    id: "clinics",
    name: "Clinics",
    categoryLabel: "INDUSTRY VERTICAL 02",
    headline: "Structured Patient Intake & Practitioner Desk Coordination",
    description:
      "Tailored for outpatient, dental, dermatology, physiotherapy, and specialty clinics requiring calm patient intake, pre-visit preparation guidance, and non-diagnostic safety guardrails.",
    voicePersona: "Empathetic, structured clinical coordinator",
    plannedHighlights: [
      "New patient vs. follow-up visit classification",
      "Practitioner specialty & clinic hours routing",
      "Pre-appointment preparation instruction delivery",
      "Urgent symptom detection & human handoff boundary",
    ],
    sharedSubsystems: ["Voice", "AI Policy", "Scheduling", "Notifications"],
  },
  {
    id: "hospitals",
    name: "Hospitals",
    categoryLabel: "INDUSTRY VERTICAL 03",
    headline: "24/7 Departmental Switchboard & Escalation Guardrails",
    description:
      "Built for multi-specialty hospitals and medical centers to navigate high-concurrency OPD inquiries, department directories, visiting hours, and zero-delay emergency escalation.",
    voicePersona: "Calm, authoritative institutional switchboard operator",
    plannedHighlights: [
      "Multi-department OPD & specialist directory routing",
      "Red-flag detection & immediate live operator transfer",
      "Visiting hours, admission desk & diagnostics FAQs",
      "High-concurrency front-desk call triage boundaries",
    ],
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
