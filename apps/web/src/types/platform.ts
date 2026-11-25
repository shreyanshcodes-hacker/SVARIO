export interface HealthCheckResponse {
  status: string;
  service: string;
  stage: number;
}

export type ConnectionState = "checking" | "connected" | "unreachable";

export interface BackendConnectionStatus {
  state: ConnectionState;
  endpoint: string;
  data: HealthCheckResponse | null;
  latencyMs: number | null;
  checkedAt: string | null;
  errorMessage: string | null;
}

export type IndustryId = "salons" | "clinics" | "hospitals";

export type OrganizationIndustryType = "salon" | "clinic" | "hospital";

export type OrganizationRoleType = "owner" | "admin" | "staff";

export type LanguageCodeType = "en" | "hi" | "hinglish";

export type AssistantPersonalityType = "professional" | "friendly" | "warm";

export type AssistantResponseStyleType = "concise" | "balanced" | "detailed";

export type EscalationMethodType = "phone" | "email" | "either";

export type OnboardingStepIdType =
  | "industry"
  | "profile"
  | "hours"
  | "languages"
  | "assistant"
  | "faqs"
  | "escalation"
  | "review";

export interface IndustryCardItem {
  id: IndustryId;
  name: string;
  availability: "available" | "coming_soon";
  categoryLabel: string;
  headline: string;
  description: string;
  voicePersona: string;
  plannedHighlights: readonly string[];
  sharedSubsystems: readonly string[];
}

export interface SharedSubsystemItem {
  id: string;
  name: string;
  plannedStack: string;
  description: string;
}

export interface VerifiedBackendUser {
  id: string;
  email: string | null;
  role: string;
  session_id: string | null;
  full_name: string | null;
  email_verified: boolean;
  issuer: string;
  audience: string;
}

export interface OrganizationSummary {
  id: string;
  name: string;
  slug: string;
  industry: OrganizationIndustryType;
  membership_role: OrganizationRoleType;
  created_at: string;
  updated_at: string;
}

export interface OrganizationDetail extends OrganizationSummary {
  member_count: number;
}

export interface OrganizationMember {
  id: string;
  organization_id: string;
  user_id: string;
  role: OrganizationRoleType;
  full_name: string | null;
  created_at: string;
}

export interface CreateOrganizationPayload {
  name: string;
  industry: OrganizationIndustryType;
  slug?: string;
  timezone?: string;
}

export interface BusinessProfileData {
  id: string;
  organization_id: string;
  business_id: string;
  display_name: string;
  description: string | null;
  phone: string | null;
  email: string | null;
  website: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  timezone: string;
  created_at: string;
  updated_at: string;
}

export interface BusinessProfileUpdatePayload {
  display_name: string;
  description?: string | null;
  phone?: string | null;
  email?: string | null;
  website?: string | null;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  postal_code?: string | null;
  timezone: string;
}

export interface WeekdayHoursItemData {
  weekday: number;
  is_closed: boolean;
  opens_at: string | null;
  closes_at: string | null;
  is_overnight: boolean;
}

export interface BusinessHoursData {
  organization_id: string;
  business_id: string;
  timezone: string;
  schedule: WeekdayHoursItemData[];
}

export interface BusinessLanguageEntryData {
  id: string;
  organization_id: string;
  business_id: string;
  language_code: LanguageCodeType;
  is_primary: boolean;
  created_at: string;
}

export interface BusinessLanguagesData {
  organization_id: string;
  business_id: string;
  primary_language: LanguageCodeType;
  supported_languages: LanguageCodeType[];
  entries: BusinessLanguageEntryData[];
}

export interface AssistantSettingsData {
  id: string;
  organization_id: string;
  business_id: string;
  assistant_name: string;
  greeting: string;
  personality: AssistantPersonalityType;
  response_style: AssistantResponseStyleType;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface AssistantSettingsUpdatePayload {
  assistant_name: string;
  greeting: string;
  personality: AssistantPersonalityType;
  response_style: AssistantResponseStyleType;
  enabled: boolean;
}

export interface BusinessFaqData {
  id: string;
  organization_id: string;
  business_id: string;
  question: string;
  answer: string;
  category: string;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface BusinessFaqCreatePayload {
  question: string;
  answer: string;
  category: string;
  is_active: boolean;
  sort_order: number;
}

export interface BusinessFaqUpdatePayload {
  question?: string;
  answer?: string;
  category?: string;
  is_active?: boolean;
  sort_order?: number;
}

export interface FaqTemplateExampleData {
  industry: OrganizationIndustryType;
  question: string;
  answer_placeholder: string;
  category: string;
}

export interface EscalationSettingsData {
  id: string;
  organization_id: string;
  business_id: string;
  enabled: boolean;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  preferred_method: EscalationMethodType;
  escalation_instructions: string | null;
  created_at: string;
  updated_at: string;
}

export interface EscalationSettingsUpdatePayload {
  enabled: boolean;
  contact_name?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  preferred_method: EscalationMethodType;
  escalation_instructions?: string | null;
}

export interface HealthcareSafeguardNoticeData {
  applies_to_healthcare: boolean;
  administrative_only: boolean;
  prohibited_actions: string[];
  emergency_directive: string;
}

export interface OnboardingProgressData {
  id: string;
  organization_id: string;
  business_id: string;
  current_step: OnboardingStepIdType;
  completed_steps: OnboardingStepIdType[];
  is_completed: boolean;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OnboardingProgressUpdatePayload {
  current_step: OnboardingStepIdType;
  completed_steps: OnboardingStepIdType[];
  is_completed: boolean;
}

export interface OnboardingBundleData {
  organization: OrganizationDetail;
  business_id: string;
  profile: BusinessProfileData;
  hours: BusinessHoursData;
  languages: BusinessLanguagesData;
  assistant: AssistantSettingsData;
  faqs: BusinessFaqData[];
  faq_templates: FaqTemplateExampleData[];
  escalation: EscalationSettingsData;
  healthcare_safeguards: HealthcareSafeguardNoticeData;
  progress: OnboardingProgressData;
}

// --- Stage 3: Shared Browser Voice Infrastructure Types ---

export type VoiceAccessModeType = "organization_member" | "public_visitor";

export type RealtimeVoicePresetType =
  | "alloy"
  | "ash"
  | "ballad"
  | "coral"
  | "echo"
  | "sage"
  | "shimmer"
  | "verse"
  | "marin"
  | "cedar";

export interface VoiceSessionCreatePayload {
  organization_id: string;
  business_id?: string;
  access_mode?: VoiceAccessModeType;
  public_access_token?: string;
  voice_override?: RealtimeVoicePresetType;
}

export interface EphemeralClientSecretData {
  value: string;
  expires_at: string;
  ttl_seconds: number;
}

export interface VoiceSessionCapabilitiesData {
  modalities: string[];
  barge_in_enabled: boolean;
  raw_audio_storage_enabled: boolean;
  transcript_storage_enabled: boolean;
  appointment_booking_enabled: boolean;
  industry_workflows_enabled: boolean;
}

export interface SafeVoiceAssistantContextData {
  business_name: string;
  assistant_name: string;
  greeting: string;
  primary_language: LanguageCodeType;
  supported_languages: LanguageCodeType[];
  personality: AssistantPersonalityType;
  response_style: AssistantResponseStyleType;
  assistant_enabled: boolean;
  administrative_only_guardrails: boolean;
  audio_persistence_enabled: boolean;
  transcript_persistence_enabled: boolean;
}

export interface VoiceSessionCreateResponseData {
  session_id: string;
  organization_id: string;
  business_id: string;
  industry: OrganizationIndustryType;
  access_mode: VoiceAccessModeType;
  model: string;
  voice: string;
  webrtc_url: string;
  webrtc_calls_url: string;
  data_channel_label: string;
  client_secret: EphemeralClientSecretData;
  capabilities: VoiceSessionCapabilitiesData;
  assistant_context: SafeVoiceAssistantContextData;
}

export interface PublicVoiceTokenResponseData {
  organization_id: string;
  business_id: string;
  industry: OrganizationIndustryType;
  public_access_token: string;
  expires_at: string;
  ttl_seconds: number;
}

// --- Stage 4: AI Agent & Conversational Intelligence Types ---

export type AgentToolNameType =
  | "get_business_profile"
  | "get_business_hours"
  | "search_business_knowledge"
  | "save_conversation_summary"
  | "request_human_escalation"
  | "get_salon_services"
  | "get_salon_staff"
  | "check_salon_availability"
  | "create_salon_appointment"
  | "reschedule_salon_appointment"
  | "cancel_salon_appointment"
  | "get_clinic_information"
  | "get_clinic_departments"
  | "get_clinic_specialities"
  | "get_clinic_doctors"
  | "get_clinic_consultation_types"
  | "check_clinic_availability"
  | "create_clinic_appointment"
  | "reschedule_clinic_appointment"
  | "cancel_clinic_appointment"
  | "request_clinic_human_escalation";

export interface VoiceToolExecutionPayload {
  session_id: string;
  organization_id: string;
  business_id?: string;
  access_mode?: VoiceAccessModeType;
  public_access_token?: string;
  call_id: string;
  tool_name: AgentToolNameType;
  arguments: Record<string, unknown>;
}

export interface VoiceToolExecutionResponseData {
  session_id: string;
  call_id: string;
  tool_name: AgentToolNameType;
  status: "succeeded" | "rejected" | "error";
  output: Record<string, unknown>;
  escalation_triggered: boolean;
  escalation_reference: string | null;
  detected_language: LanguageCodeType;
}
