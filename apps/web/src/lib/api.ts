import type {
  AssistantSettingsData,
  AssistantSettingsUpdatePayload,
  BusinessFaqCreatePayload,
  BusinessFaqData,
  BusinessFaqUpdatePayload,
  BusinessHoursData,
  BusinessLanguagesData,
  BusinessProfileData,
  BusinessProfileUpdatePayload,
  CreateOrganizationPayload,
  EscalationSettingsData,
  EscalationSettingsUpdatePayload,
  HealthCheckResponse,
  LanguageCodeType,
  OnboardingBundleData,
  OnboardingProgressData,
  OnboardingProgressUpdatePayload,
  OrganizationDetail,
  OrganizationIndustryType,
  OrganizationMember,
  OrganizationSummary,
  PublicVoiceTokenResponseData,
  VerifiedBackendUser,
  VoiceSessionCreatePayload,
  VoiceSessionCreateResponseData,
  VoiceToolExecutionPayload,
  VoiceToolExecutionResponseData,
  WeekdayHoursItemData,
} from "@/types/platform";

export function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (typeof window !== "undefined") {
    // If configured is an explicit non-local URL (production Render/Vercel)
    if (
      configured &&
      configured.length > 0 &&
      !configured.includes("localhost") &&
      !configured.includes("127.0.0.1")
    ) {
      return configured.replace(/\/+$/, "");
    }

    const isPort3001 = window.location.port === "3001";
    const apiPort = isPort3001 ? "8001" : "8000";
    const currentHost = window.location.hostname || "localhost";
    const currentProtocol = window.location.protocol === "https:" ? "https:" : "http:";

    // Match browser's active host (localhost, 127.0.0.1, or LAN IP) to prevent CORS/loopback resolution issues
    return `${currentProtocol}//${currentHost}:${apiPort}`;
  }

  if (configured && configured.length > 0) {
    return configured.replace(/\/+$/, "");
  }
  return "http://localhost:8000";
}

function buildAuthHeaders(accessToken: string): HeadersInit {
  return {
    Accept: "application/json",
    "Content-Type": "application/json",
    Authorization: `Bearer ${accessToken}`,
  };
}

async function parseApiError(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null) {
      if (
        "details" in body &&
        Array.isArray((body as { details: unknown }).details) &&
        (body as { details: Array<{ msg?: string }> }).details.length > 0
      ) {
        const firstMsg = (body as { details: Array<{ msg?: string }> }).details[0]?.msg;
        if (firstMsg) return firstMsg;
      }
      if ("message" in body && typeof (body as { message: unknown }).message === "string") {
        return (body as { message: string }).message;
      }
      if ("detail" in body && typeof (body as { detail: unknown }).detail === "string") {
        return (body as { detail: string }).detail;
      }
    }
  } catch {
    // Fallback to HTTP status text below
  }
  return `Request failed with HTTP ${response.status}`;
}

export async function fetchBackendHealth(
  signal?: AbortSignal
): Promise<{ payload: HealthCheckResponse; latencyMs: number; endpoint: string }> {
  const baseUrl = getApiBaseUrl();
  const endpoint = `${baseUrl}/health`;
  const startedAt = performance.now();

  const response = await fetch(endpoint, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    cache: "no-store",
    signal,
  });

  const latencyMs = Math.round(performance.now() - startedAt);

  if (!response.ok) {
    throw new Error(`HTTP ${response.status} from ${endpoint}`);
  }

  const raw: unknown = await response.json();
  if (
    typeof raw !== "object" ||
    raw === null ||
    !("status" in raw) ||
    !("service" in raw) ||
    !("stage" in raw)
  ) {
    throw new Error("Invalid health response schema from backend");
  }

  const typed = raw as HealthCheckResponse;
  return {
    payload: {
      status: String(typed.status),
      service: String(typed.service),
      stage: Number(typed.stage),
    },
    latencyMs,
    endpoint,
  };
}

export async function fetchVerifiedAuthMe(
  accessToken: string
): Promise<VerifiedBackendUser> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/me`, {
    method: "GET",
    headers: buildAuthHeaders(accessToken),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as VerifiedBackendUser;
}

export async function fetchUserOrganizations(
  accessToken: string
): Promise<OrganizationSummary[]> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/organizations`, {
    method: "GET",
    headers: buildAuthHeaders(accessToken),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as OrganizationSummary[];
}

export async function fetchOrganizationDetail(
  accessToken: string,
  organizationId: string
): Promise<OrganizationDetail> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}`,
    {
      method: "GET",
      headers: buildAuthHeaders(accessToken),
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as OrganizationDetail;
}

export async function createOrganizationApi(
  accessToken: string,
  payload: CreateOrganizationPayload
): Promise<OrganizationSummary> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/organizations`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as OrganizationSummary;
}

export async function fetchOrganizationMembers(
  accessToken: string,
  organizationId: string
): Promise<OrganizationMember[]> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/members`,
    {
      method: "GET",
      headers: buildAuthHeaders(accessToken),
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as OrganizationMember[];
}

// --- Stage 2: Organization-Scoped Onboarding APIs ---

export async function fetchOnboardingBundle(
  accessToken: string,
  organizationId: string
): Promise<OnboardingBundleData> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/onboarding`,
    {
      method: "GET",
      headers: buildAuthHeaders(accessToken),
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as OnboardingBundleData;
}

export async function updateOnboardingIndustry(
  accessToken: string,
  organizationId: string,
  industry: OrganizationIndustryType
): Promise<OrganizationDetail> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/onboarding/industry`,
    {
      method: "PUT",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify({ industry }),
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as OrganizationDetail;
}

export async function updateBusinessProfileApi(
  accessToken: string,
  organizationId: string,
  payload: BusinessProfileUpdatePayload
): Promise<BusinessProfileData> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/onboarding/profile`,
    {
      method: "PUT",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as BusinessProfileData;
}

export async function updateBusinessHoursApi(
  accessToken: string,
  organizationId: string,
  payload: { timezone: string; schedule: WeekdayHoursItemData[] }
): Promise<BusinessHoursData> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/onboarding/hours`,
    {
      method: "PUT",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as BusinessHoursData;
}

export async function updateBusinessLanguagesApi(
  accessToken: string,
  organizationId: string,
  payload: {
    primary_language: LanguageCodeType;
    supported_languages: LanguageCodeType[];
  }
): Promise<BusinessLanguagesData> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/onboarding/languages`,
    {
      method: "PUT",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as BusinessLanguagesData;
}

export async function updateAssistantSettingsApi(
  accessToken: string,
  organizationId: string,
  payload: AssistantSettingsUpdatePayload
): Promise<AssistantSettingsData> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/onboarding/assistant`,
    {
      method: "PUT",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as AssistantSettingsData;
}

export async function createBusinessFaqApi(
  accessToken: string,
  organizationId: string,
  payload: BusinessFaqCreatePayload
): Promise<BusinessFaqData> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/onboarding/faqs`,
    {
      method: "POST",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as BusinessFaqData;
}

export async function updateBusinessFaqApi(
  accessToken: string,
  organizationId: string,
  faqId: string,
  payload: BusinessFaqUpdatePayload
): Promise<BusinessFaqData> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/onboarding/faqs/${encodeURIComponent(faqId)}`,
    {
      method: "PUT",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as BusinessFaqData;
}

export async function deleteBusinessFaqApi(
  accessToken: string,
  organizationId: string,
  faqId: string
): Promise<void> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/onboarding/faqs/${encodeURIComponent(faqId)}`,
    {
      method: "DELETE",
      headers: buildAuthHeaders(accessToken),
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
}

export async function updateEscalationSettingsApi(
  accessToken: string,
  organizationId: string,
  payload: EscalationSettingsUpdatePayload
): Promise<EscalationSettingsData> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/onboarding/escalation`,
    {
      method: "PUT",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as EscalationSettingsData;
}

export async function updateOnboardingProgressApi(
  accessToken: string,
  organizationId: string,
  payload: OnboardingProgressUpdatePayload
): Promise<OnboardingProgressData> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/onboarding/progress`,
    {
      method: "PUT",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as OnboardingProgressData;
}

// --- Stage 3: Shared Browser Voice Session APIs ---

export async function createVoiceSessionApi(
  payload: VoiceSessionCreatePayload,
  accessToken?: string | null
): Promise<VoiceSessionCreateResponseData> {
  const headers: HeadersInit = accessToken
    ? buildAuthHeaders(accessToken)
    : {
        Accept: "application/json",
        "Content-Type": "application/json",
      };

  const response = await fetch(`${getApiBaseUrl()}/api/v1/voice/sessions`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as VoiceSessionCreateResponseData;
}

export async function createPublicVoiceTokenApi(
  accessToken: string,
  organizationId: string,
  ttlSeconds = 3600
): Promise<PublicVoiceTokenResponseData> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/voice/public-token`,
    {
      method: "POST",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify({ ttl_seconds: ttlSeconds }),
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as PublicVoiceTokenResponseData;
}

export async function executeVoiceToolApi(
  payload: VoiceToolExecutionPayload,
  accessToken?: string | null
): Promise<VoiceToolExecutionResponseData> {
  const headers: HeadersInit = accessToken
    ? buildAuthHeaders(accessToken)
    : {
        Accept: "application/json",
        "Content-Type": "application/json",
      };

  const response = await fetch(`${getApiBaseUrl()}/api/v1/voice/tools/execute`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as VoiceToolExecutionResponseData;
}

// =============================================================================
// Stage 5: Salon Workflow Module API Client
// =============================================================================
import type {
  SalonAppointment,
  SalonAvailabilityResponse,
  SalonCreateAppointmentPayload,
  SalonService,
  SalonServiceCreatePayload,
  SalonStaff,
  SalonStaffCreatePayload,
} from "@/types/salon";

export async function fetchSalonServices(
  accessToken: string,
  organizationId: string,
  businessId: string,
  isActive?: boolean
): Promise<SalonService[]> {
  const query = isActive !== undefined ? `?is_active=${isActive}` : "";
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/salons/${encodeURIComponent(businessId)}/services${query}`,
    {
      headers: buildAuthHeaders(accessToken),
      cache: "no-store",
    }
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  return (await response.json()) as SalonService[];
}

export async function createSalonService(
  accessToken: string,
  organizationId: string,
  businessId: string,
  payload: SalonServiceCreatePayload
): Promise<SalonService> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/salons/${encodeURIComponent(businessId)}/services`,
    {
      method: "POST",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  return (await response.json()) as SalonService;
}

export async function updateSalonService(
  accessToken: string,
  organizationId: string,
  businessId: string,
  serviceId: string,
  payload: Partial<SalonServiceCreatePayload>
): Promise<SalonService> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/salons/${encodeURIComponent(businessId)}/services/${encodeURIComponent(serviceId)}`,
    {
      method: "PATCH",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  return (await response.json()) as SalonService;
}

export async function deleteSalonService(
  accessToken: string,
  organizationId: string,
  businessId: string,
  serviceId: string
): Promise<void> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/salons/${encodeURIComponent(businessId)}/services/${encodeURIComponent(serviceId)}`,
    {
      method: "DELETE",
      headers: buildAuthHeaders(accessToken),
    }
  );
  if (!response.ok) throw new Error(await parseApiError(response));
}

export async function fetchSalonStaff(
  accessToken: string,
  organizationId: string,
  businessId: string,
  serviceId?: string,
  isActive?: boolean
): Promise<SalonStaff[]> {
  const params = new URLSearchParams();
  if (serviceId) params.set("service_id", serviceId);
  if (isActive !== undefined) params.set("is_active", String(isActive));
  const query = params.toString() ? `?${params.toString()}` : "";

  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/salons/${encodeURIComponent(businessId)}/staff${query}`,
    {
      headers: buildAuthHeaders(accessToken),
      cache: "no-store",
    }
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  return (await response.json()) as SalonStaff[];
}

export async function createSalonStaff(
  accessToken: string,
  organizationId: string,
  businessId: string,
  payload: SalonStaffCreatePayload
): Promise<SalonStaff> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/salons/${encodeURIComponent(businessId)}/staff`,
    {
      method: "POST",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  return (await response.json()) as SalonStaff;
}

export async function assignSalonStaffServices(
  accessToken: string,
  organizationId: string,
  businessId: string,
  staffId: string,
  serviceIds: string[]
): Promise<SalonStaff> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/salons/${encodeURIComponent(businessId)}/staff/${encodeURIComponent(staffId)}/services`,
    {
      method: "PUT",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify({ service_ids: serviceIds }),
    }
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  return (await response.json()) as SalonStaff;
}

export async function fetchSalonAvailability(
  accessToken: string,
  organizationId: string,
  businessId: string,
  serviceId: string,
  dateStr: string,
  staffId?: string
): Promise<SalonAvailabilityResponse> {
  const params = new URLSearchParams({
    service_id: serviceId,
    requested_date: dateStr,
  });
  if (staffId) params.set("staff_id", staffId);

  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/salons/${encodeURIComponent(businessId)}/availability?${params.toString()}`,
    {
      headers: buildAuthHeaders(accessToken),
      cache: "no-store",
    }
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  return (await response.json()) as SalonAvailabilityResponse;
}

export async function fetchSalonAppointments(
  accessToken: string,
  organizationId: string,
  businessId: string,
  dateStr?: string,
  staffId?: string
): Promise<SalonAppointment[]> {
  const params = new URLSearchParams();
  if (dateStr) params.set("appointment_date", dateStr);
  if (staffId) params.set("staff_id", staffId);
  const query = params.toString() ? `?${params.toString()}` : "";

  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/salons/${encodeURIComponent(businessId)}/appointments${query}`,
    {
      headers: buildAuthHeaders(accessToken),
      cache: "no-store",
    }
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  return (await response.json()) as SalonAppointment[];
}

export async function createSalonAppointment(
  accessToken: string,
  organizationId: string,
  businessId: string,
  payload: SalonCreateAppointmentPayload
): Promise<SalonAppointment> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/salons/${encodeURIComponent(businessId)}/appointments`,
    {
      method: "POST",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  return (await response.json()) as SalonAppointment;
}

export async function rescheduleSalonAppointment(
  accessToken: string,
  organizationId: string,
  businessId: string,
  appointmentId: string,
  payload: { appointment_date: string; start_time: string; notes?: string }
): Promise<SalonAppointment> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/salons/${encodeURIComponent(businessId)}/appointments/${encodeURIComponent(appointmentId)}/reschedule`,
    {
      method: "POST",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  return (await response.json()) as SalonAppointment;
}

export async function cancelSalonAppointment(
  accessToken: string,
  organizationId: string,
  businessId: string,
  appointmentId: string,
  cancellationReason?: string
): Promise<SalonAppointment> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/salons/${encodeURIComponent(businessId)}/appointments/${encodeURIComponent(appointmentId)}/cancel`,
    {
      method: "POST",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify({ cancellation_reason: cancellationReason }),
    }
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  return (await response.json()) as SalonAppointment;
}

// ============================================================================
// Stage 6 Clinic Workflow Client APIs
// ============================================================================

import type {
  ClinicAppointment,
  ClinicAvailabilityResponse,
  ClinicConsultationType,
  ClinicDepartment,
  ClinicDoctor,
  ClinicSpeciality,
  ConsultationMode,
  DoctorWorkingHours,
} from "@/types/clinic";

function clinicBase(organizationId: string, businessId: string): string {
  return `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/clinics/${encodeURIComponent(businessId)}`;
}

export async function fetchClinicDepartments(
  accessToken: string,
  organizationId: string,
  businessId: string
): Promise<ClinicDepartment[]> {
  const res = await fetch(`${clinicBase(organizationId, businessId)}/departments`, {
    headers: buildAuthHeaders(accessToken),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClinicDepartment[];
}

export async function createClinicDepartment(
  accessToken: string,
  organizationId: string,
  businessId: string,
  payload: { name: string; description?: string | null; is_active?: boolean }
): Promise<ClinicDepartment> {
  const res = await fetch(`${clinicBase(organizationId, businessId)}/departments`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClinicDepartment;
}

export async function updateClinicDepartment(
  accessToken: string,
  organizationId: string,
  businessId: string,
  departmentId: string,
  payload: { name?: string; description?: string | null; is_active?: boolean }
): Promise<ClinicDepartment> {
  const res = await fetch(
    `${clinicBase(organizationId, businessId)}/departments/${encodeURIComponent(departmentId)}`,
    {
      method: "PATCH",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClinicDepartment;
}

export async function fetchClinicSpecialities(
  accessToken: string,
  organizationId: string,
  businessId: string
): Promise<ClinicSpeciality[]> {
  const res = await fetch(`${clinicBase(organizationId, businessId)}/specialities`, {
    headers: buildAuthHeaders(accessToken),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClinicSpeciality[];
}

export async function createClinicSpeciality(
  accessToken: string,
  organizationId: string,
  businessId: string,
  payload: { name: string; description?: string | null; is_active?: boolean }
): Promise<ClinicSpeciality> {
  const res = await fetch(`${clinicBase(organizationId, businessId)}/specialities`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClinicSpeciality;
}

export async function fetchClinicConsultationTypes(
  accessToken: string,
  organizationId: string,
  businessId: string
): Promise<ClinicConsultationType[]> {
  const res = await fetch(`${clinicBase(organizationId, businessId)}/consultation-types`, {
    headers: buildAuthHeaders(accessToken),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClinicConsultationType[];
}

export async function createClinicConsultationType(
  accessToken: string,
  organizationId: string,
  businessId: string,
  payload: {
    name: string;
    description?: string | null;
    duration_minutes: number;
    consultation_mode: ConsultationMode;
    fee_amount?: number | null;
    currency_code?: string | null;
    is_active?: boolean;
  }
): Promise<ClinicConsultationType> {
  const res = await fetch(`${clinicBase(organizationId, businessId)}/consultation-types`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClinicConsultationType;
}

export async function fetchClinicDoctors(
  accessToken: string,
  organizationId: string,
  businessId: string
): Promise<ClinicDoctor[]> {
  const res = await fetch(`${clinicBase(organizationId, businessId)}/doctors`, {
    headers: buildAuthHeaders(accessToken),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClinicDoctor[];
}

export async function createClinicDoctor(
  accessToken: string,
  organizationId: string,
  businessId: string,
  payload: {
    display_name: string;
    professional_title?: string | null;
    public_bio?: string | null;
    languages?: string[];
    department_ids?: string[];
    speciality_ids?: string[];
    consultation_type_ids?: string[];
  }
): Promise<ClinicDoctor> {
  const res = await fetch(`${clinicBase(organizationId, businessId)}/doctors`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClinicDoctor;
}

export async function updateClinicDoctor(
  accessToken: string,
  organizationId: string,
  businessId: string,
  doctorId: string,
  payload: { display_name?: string; professional_title?: string | null; is_active?: boolean }
): Promise<ClinicDoctor> {
  const res = await fetch(
    `${clinicBase(organizationId, businessId)}/doctors/${encodeURIComponent(doctorId)}`,
    {
      method: "PATCH",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClinicDoctor;
}

export async function upsertClinicDoctorWorkingHours(
  accessToken: string,
  organizationId: string,
  businessId: string,
  doctorId: string,
  items: Array<{
    day_of_week: number;
    start_time: string | null;
    end_time: string | null;
    is_active: boolean;
  }>
): Promise<DoctorWorkingHours[]> {
  const res = await fetch(
    `${clinicBase(organizationId, businessId)}/doctors/${encodeURIComponent(doctorId)}/working-hours`,
    {
      method: "PUT",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify({ items }),
    }
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as DoctorWorkingHours[];
}

export async function fetchClinicAvailability(
  accessToken: string,
  organizationId: string,
  businessId: string,
  params: {
    consultation_type_id: string;
    target_date: string;
    doctor_id?: string;
    department_id?: string;
  }
): Promise<ClinicAvailabilityResponse> {
  const q = new URLSearchParams({
    consultation_type_id: params.consultation_type_id,
    target_date: params.target_date,
  });
  if (params.doctor_id) q.set("doctor_id", params.doctor_id);
  if (params.department_id) q.set("department_id", params.department_id);
  const res = await fetch(
    `${clinicBase(organizationId, businessId)}/availability?${q.toString()}`,
    {
      headers: buildAuthHeaders(accessToken),
      cache: "no-store",
    }
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClinicAvailabilityResponse;
}

export async function fetchClinicAppointments(
  accessToken: string,
  organizationId: string,
  businessId: string,
  params?: { doctor_id?: string; target_date?: string }
): Promise<ClinicAppointment[]> {
  const q = new URLSearchParams();
  if (params?.doctor_id) q.set("doctor_id", params.doctor_id);
  if (params?.target_date) q.set("target_date", params.target_date);
  const qs = q.toString() ? `?${q.toString()}` : "";
  const res = await fetch(`${clinicBase(organizationId, businessId)}/appointments${qs}`, {
    headers: buildAuthHeaders(accessToken),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClinicAppointment[];
}

export async function createClinicAppointment(
  accessToken: string,
  organizationId: string,
  businessId: string,
  payload: {
    doctor_id: string;
    consultation_type_id: string;
    department_id?: string | null;
    patient_display_name: string;
    patient_contact: string;
    starts_at: string;
    idempotency_key?: string;
  }
): Promise<ClinicAppointment> {
  const res = await fetch(`${clinicBase(organizationId, businessId)}/appointments`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClinicAppointment;
}

export async function rescheduleClinicAppointment(
  accessToken: string,
  organizationId: string,
  businessId: string,
  appointmentId: string,
  payload: { new_starts_at: string; new_doctor_id?: string | null }
): Promise<ClinicAppointment> {
  const res = await fetch(
    `${clinicBase(organizationId, businessId)}/appointments/${encodeURIComponent(appointmentId)}/reschedule`,
    {
      method: "POST",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify(payload),
    }
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClinicAppointment;
}

export async function cancelClinicAppointment(
  accessToken: string,
  organizationId: string,
  businessId: string,
  appointmentId: string,
  reason?: string
): Promise<ClinicAppointment> {
  const res = await fetch(
    `${clinicBase(organizationId, businessId)}/appointments/${encodeURIComponent(appointmentId)}/cancel`,
    {
      method: "POST",
      headers: buildAuthHeaders(accessToken),
      body: JSON.stringify({ reason }),
    }
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClinicAppointment;
}

// ============================================================================
// White-Label Booking Website Engine (Stage 1 Dashboard Foundation)
// ============================================================================

import type {
  BookingWebsiteConfig,
  BookingWebsiteDraftUpdatePayload,
  BrandAssetUploadResult,
  PublicBookingWebsiteData,
  SlugAvailabilityResult,
} from "@/types/website";

function websiteBase(organizationId: string): string {
  return `${getApiBaseUrl()}/api/v1/organizations/${encodeURIComponent(organizationId)}/booking-website`;
}

export async function fetchBookingWebsiteConfig(
  accessToken: string,
  organizationId: string
): Promise<BookingWebsiteConfig> {
  const res = await fetch(websiteBase(organizationId), {
    method: "GET",
    headers: buildAuthHeaders(accessToken),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as BookingWebsiteConfig;
}

export async function saveBookingWebsiteDraft(
  accessToken: string,
  organizationId: string,
  payload: BookingWebsiteDraftUpdatePayload
): Promise<BookingWebsiteConfig> {
  const res = await fetch(websiteBase(organizationId), {
    method: "PUT",
    headers: buildAuthHeaders(accessToken),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as BookingWebsiteConfig;
}

export async function checkBookingWebsiteSlug(
  accessToken: string,
  organizationId: string,
  slug: string
): Promise<SlugAvailabilityResult> {
  const q = new URLSearchParams({ slug });
  const res = await fetch(`${websiteBase(organizationId)}/slug-availability?${q.toString()}`, {
    method: "GET",
    headers: buildAuthHeaders(accessToken),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as SlugAvailabilityResult;
}

export async function uploadBookingWebsiteAsset(
  accessToken: string,
  organizationId: string,
  assetType: "logo" | "cover",
  file: File
): Promise<BrandAssetUploadResult> {
  const res = await fetch(`${websiteBase(organizationId)}/assets/${encodeURIComponent(assetType)}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": file.type || "application/octet-stream",
    },
    body: file,
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as BrandAssetUploadResult;
}

export async function publishBookingWebsite(
  accessToken: string,
  organizationId: string
): Promise<BookingWebsiteConfig> {
  const res = await fetch(`${websiteBase(organizationId)}/publish`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as BookingWebsiteConfig;
}

export async function unpublishBookingWebsite(
  accessToken: string,
  organizationId: string
): Promise<BookingWebsiteConfig> {
  const res = await fetch(`${websiteBase(organizationId)}/unpublish`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as BookingWebsiteConfig;
}

export async function fetchPublicBookingWebsite(
  slug: string
): Promise<PublicBookingWebsiteData | null> {
  const apiBase = getApiBaseUrl();
  const res = await fetch(
    `${apiBase}/api/v1/public/websites/${encodeURIComponent(slug)}`,
    {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    }
  );
  if (res.status === 404) {
    return null;
  }
  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }
  const data = (await res.json()) as PublicBookingWebsiteData;
  const resolveUrl = (url: string | null): string | null => {
    if (!url) return null;
    if (url.startsWith("http://") || url.startsWith("https://")) return url;
    return `${apiBase}${url}`;
  };
  return {
    ...data,
    logo_url: resolveUrl(data.logo_url),
    cover_image_url: resolveUrl(data.cover_image_url),
  };
}

export interface PublicWebsiteVoiceSessionData {
  session_id: string;
  slug: string;
  visitor_session_token: string;
  model: string;
  voice: string;
  webrtc_url: string;
  webrtc_calls_url: string;
  data_channel_label: string;
  client_secret: {
    value: string;
    expires_at: string;
    ttl_seconds: number;
  };
  capabilities: {
    modalities: string[];
    barge_in_enabled: boolean;
    raw_audio_storage_enabled: boolean;
    transcript_storage_enabled: boolean;
    appointment_booking_enabled: boolean;
    industry_workflows_enabled: boolean;
  };
  assistant_context: VoiceSessionCreateResponseData["assistant_context"];
}

export async function createPublicWebsiteVoiceSessionApi(
  slug: string,
  voiceOverride?: string
): Promise<PublicWebsiteVoiceSessionData> {
  const res = await fetch(
    `${getApiBaseUrl()}/api/v1/public/websites/${encodeURIComponent(slug)}/voice/sessions`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(voiceOverride ? { voice_override: voiceOverride } : {}),
      cache: "no-store",
    }
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as PublicWebsiteVoiceSessionData;
}

export async function executePublicWebsiteVoiceToolApi(
  slug: string,
  payload: {
    session_id: string;
    call_id: string;
    tool_name: string;
    arguments: Record<string, unknown>;
    visitor_session_token: string;
  }
): Promise<VoiceToolExecutionResponseData> {
  const res = await fetch(
    `${getApiBaseUrl()}/api/v1/public/websites/${encodeURIComponent(slug)}/voice/tools/execute`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      cache: "no-store",
    }
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as VoiceToolExecutionResponseData;
}
