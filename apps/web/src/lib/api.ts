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
  if (configured && configured.length > 0) {
    const cleanUrl = configured.replace(/\/+$/, "");
    if (
      typeof window !== "undefined" &&
      window.location.port === "3001" &&
      cleanUrl.includes(":8000")
    ) {
      return cleanUrl.replace(":8000", ":8001");
    }
    return cleanUrl;
  }
  if (typeof window !== "undefined" && window.location.port === "3001") {
    return "http://localhost:8001";
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
