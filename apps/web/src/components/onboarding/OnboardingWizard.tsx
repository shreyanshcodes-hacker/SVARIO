"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createBusinessFaqApi,
  deleteBusinessFaqApi,
  fetchOnboardingBundle,
  updateAssistantSettingsApi,
  updateBusinessFaqApi,
  updateBusinessHoursApi,
  updateBusinessLanguagesApi,
  updateBusinessProfileApi,
  updateEscalationSettingsApi,
  updateOnboardingIndustry,
  updateOnboardingProgressApi,
} from "@/lib/api";
import type {
  AssistantPersonalityType,
  AssistantResponseStyleType,
  BusinessFaqData,
  EscalationMethodType,
  LanguageCodeType,
  OnboardingBundleData,
  OnboardingStepIdType,
  OrganizationIndustryType,
  WeekdayHoursItemData,
} from "@/types/platform";

export const ONBOARDING_STEPS: readonly {
  id: OnboardingStepIdType;
  number: number;
  label: string;
}[] = [
  { id: "industry", number: 1, label: "Industry Selection" },
  { id: "profile", number: 2, label: "Business Profile" },
  { id: "hours", number: 3, label: "Operating Hours" },
  { id: "languages", number: 4, label: "Languages" },
  { id: "assistant", number: 5, label: "Assistant Config" },
  { id: "faqs", number: 6, label: "Business FAQs" },
  { id: "escalation", number: 7, label: "Human Escalation" },
  { id: "review", number: 8, label: "Review & Complete" },
] as const;

const WEEKDAY_NAMES: readonly string[] = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
] as const;

const LANGUAGE_LABELS: Record<
  LanguageCodeType,
  { name: string; subtitle: string }
> = {
  en: {
    name: "English",
    subtitle: "Standard formal & conversational English (en)",
  },
  hi: {
    name: "Hindi",
    subtitle: "Standard conversational Hindi (hi)",
  },
  hinglish: {
    name: "Hinglish",
    subtitle: "Conversational Hindi-English blend (conversation preference, not a formal locale)",
  },
};

interface OnboardingWizardProps {
  accessToken: string;
  organizationId: string;
  initialBundle?: OnboardingBundleData | null;
  onOrganizationUpdated?: () => Promise<void>;
}

export function OnboardingWizard({
  accessToken,
  organizationId,
  initialBundle = null,
  onOrganizationUpdated,
}: OnboardingWizardProps): React.JSX.Element {
  const router = useRouter();
  const [bundle, setBundle] = useState<OnboardingBundleData | null>(
    initialBundle
  );
  const [isLoading, setIsLoading] = useState<boolean>(!initialBundle);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusToast, setStatusToast] = useState<string | null>(null);

  const [currentStep, setCurrentStep] =
    useState<OnboardingStepIdType>("industry");
  const [completedSteps, setCompletedSteps] = useState<OnboardingStepIdType[]>(
    []
  );

  // Step 1: Industry
  const [industry, setIndustry] = useState<OrganizationIndustryType>("salon");

  // Step 2: Business Profile
  const [displayName, setDisplayName] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [phone, setPhone] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [website, setWebsite] = useState<string>("");
  const [address, setAddress] = useState<string>("");
  const [city, setCity] = useState<string>("");
  const [stateRegion, setStateRegion] = useState<string>("");
  const [country, setCountry] = useState<string>("");
  const [postalCode, setPostalCode] = useState<string>("");
  const [timezone, setTimezone] = useState<string>("UTC");

  // Step 3: Business Hours
  const [schedule, setSchedule] = useState<WeekdayHoursItemData[]>([]);

  // Step 4: Languages
  const [primaryLanguage, setPrimaryLanguage] =
    useState<LanguageCodeType>("en");
  const [supportedLanguages, setSupportedLanguages] = useState<
    LanguageCodeType[]
  >(["en"]);

  // Step 5: Assistant Settings
  const [assistantName, setAssistantName] = useState<string>("");
  const [greeting, setGreeting] = useState<string>("");
  const [personality, setPersonality] =
    useState<AssistantPersonalityType>("professional");
  const [responseStyle, setResponseStyle] =
    useState<AssistantResponseStyleType>("balanced");
  const [assistantEnabled, setAssistantEnabled] = useState<boolean>(false);

  // Step 6: FAQs
  const [faqs, setFaqs] = useState<BusinessFaqData[]>([]);
  const [newQuestion, setNewQuestion] = useState<string>("");
  const [newAnswer, setNewAnswer] = useState<string>("");
  const [newCategory, setNewCategory] = useState<string>("general");
  const [newSortOrder, setNewSortOrder] = useState<number>(0);
  const [editingFaqId, setEditingFaqId] = useState<string | null>(null);
  const [editQuestion, setEditQuestion] = useState<string>("");
  const [editAnswer, setEditAnswer] = useState<string>("");
  const [editCategory, setEditCategory] = useState<string>("general");
  const [editSortOrder, setEditSortOrder] = useState<number>(0);

  // Step 7: Escalation
  const [escalationEnabled, setEscalationEnabled] = useState<boolean>(true);
  const [contactName, setContactName] = useState<string>("");
  const [contactEmail, setContactEmail] = useState<string>("");
  const [contactPhone, setContactPhone] = useState<string>("");
  const [preferredMethod, setPreferredMethod] =
    useState<EscalationMethodType>("phone");
  const [escalationInstructions, setEscalationInstructions] =
    useState<string>("");

  const hydrateFromBundle = useCallback((data: OnboardingBundleData) => {
    setBundle(data);
    setCurrentStep(data.progress.current_step);
    setCompletedSteps(data.progress.completed_steps);

    setIndustry(data.organization.industry);

    setDisplayName(data.profile.display_name);
    setDescription(data.profile.description ?? "");
    setPhone(data.profile.phone ?? "");
    setEmail(data.profile.email ?? "");
    setWebsite(data.profile.website ?? "");
    setAddress(data.profile.address ?? "");
    setCity(data.profile.city ?? "");
    setStateRegion(data.profile.state ?? "");
    setCountry(data.profile.country ?? "");
    setPostalCode(data.profile.postal_code ?? "");
    setTimezone(data.profile.timezone || "UTC");

    setSchedule(data.hours.schedule);

    setPrimaryLanguage(data.languages.primary_language);
    setSupportedLanguages(data.languages.supported_languages);

    setAssistantName(data.assistant.assistant_name);
    setGreeting(data.assistant.greeting);
    setPersonality(data.assistant.personality);
    setResponseStyle(data.assistant.response_style);
    setAssistantEnabled(data.assistant.enabled);

    setFaqs(data.faqs);

    setEscalationEnabled(data.escalation.enabled);
    setContactName(data.escalation.contact_name ?? "");
    setContactEmail(data.escalation.contact_email ?? "");
    setContactPhone(data.escalation.contact_phone ?? "");
    setPreferredMethod(data.escalation.preferred_method);
    setEscalationInstructions(data.escalation.escalation_instructions ?? "");
  }, []);

  useEffect(() => {
    if (initialBundle) {
      hydrateFromBundle(initialBundle);
      setIsLoading(false);
      return;
    }

    let active = true;
    setIsLoading(true);
    setErrorMessage(null);

    fetchOnboardingBundle(accessToken, organizationId)
      .then((data) => {
        if (!active) return;
        hydrateFromBundle(data);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setErrorMessage(
          err instanceof Error
            ? err.message
            : "Failed to load onboarding state."
        );
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [accessToken, organizationId, initialBundle, hydrateFromBundle]);

  const isReadOnlyStaff = bundle?.organization.membership_role === "staff";
  const isHealthcare = industry === "clinic" || industry === "hospital";

  const markStepDone = (step: OnboardingStepIdType): OnboardingStepIdType[] => {
    const next = completedSteps.includes(step)
      ? completedSteps
      : [...completedSteps, step];
    setCompletedSteps(next);
    return next;
  };

  const getStepIndex = (step: OnboardingStepIdType): number =>
    ONBOARDING_STEPS.findIndex((s) => s.id === step);

  const handlePreviousStep = () => {
    setErrorMessage(null);
    const idx = getStepIndex(currentStep);
    if (idx > 0) {
      setCurrentStep(ONBOARDING_STEPS[idx - 1].id);
    }
  };

  const saveCurrentStepData = async (): Promise<boolean> => {
    setErrorMessage(null);
    setStatusToast(null);

    if (isReadOnlyStaff) {
      setErrorMessage(
        "Read-only access: only organization owners or admins can modify onboarding settings."
      );
      return false;
    }

    setIsSaving(true);
    try {
      if (currentStep === "industry") {
        await updateOnboardingIndustry(accessToken, organizationId, industry);
        await onOrganizationUpdated?.();
        markStepDone("industry");
      } else if (currentStep === "profile") {
        if (displayName.trim().length < 2) {
          setErrorMessage("Business name must be at least 2 characters.");
          return false;
        }
        if (email.trim() && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
          setErrorMessage("Please enter a valid business email address.");
          return false;
        }
        if (
          phone.trim() &&
          !/^\+?[0-9][0-9\-\s()]{5,22}$/.test(phone.trim())
        ) {
          setErrorMessage("Please enter a valid phone number.");
          return false;
        }
        if (
          website.trim() &&
          !/^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(website.trim())
        ) {
          setErrorMessage(
            "Website must be a valid URL starting with http:// or https://."
          );
        }
        if (
          website.trim() &&
          !/^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(website.trim())
        ) {
          return false;
        }
        const savedProfile = await updateBusinessProfileApi(
          accessToken,
          organizationId,
          {
            display_name: displayName.trim(),
            description: description.trim() || null,
            phone: phone.trim() || null,
            email: email.trim() || null,
            website: website.trim() || null,
            address: address.trim() || null,
            city: city.trim() || null,
            state: stateRegion.trim() || null,
            country: country.trim() || null,
            postal_code: postalCode.trim() || null,
            timezone: timezone.trim() || "UTC",
          }
        );
        setDisplayName(savedProfile.display_name);
        markStepDone("profile");
      } else if (currentStep === "hours") {
        for (const day of schedule) {
          if (!day.is_closed) {
            if (!day.opens_at || !day.closes_at) {
              setErrorMessage(
                `${WEEKDAY_NAMES[day.weekday]}: Please specify both opening and closing times.`
              );
              return false;
            }
            if (day.opens_at === day.closes_at) {
              setErrorMessage(
                `${WEEKDAY_NAMES[day.weekday]}: Opening and closing times cannot be identical.`
              );
              return false;
            }
            if (!day.is_overnight && day.opens_at > day.closes_at) {
              setErrorMessage(
                `${WEEKDAY_NAMES[day.weekday]}: Closing time must be after opening time unless Overnight is enabled.`
              );
              return false;
            }
            if (day.is_overnight && day.opens_at < day.closes_at) {
              setErrorMessage(
                `${WEEKDAY_NAMES[day.weekday]}: Overnight shift requires opening time to be later in the day than next-day closing time.`
              );
              return false;
            }
          }
        }
        const savedHours = await updateBusinessHoursApi(
          accessToken,
          organizationId,
          {
            timezone: timezone.trim() || "UTC",
            schedule,
          }
        );
        setSchedule(savedHours.schedule);
        markStepDone("hours");
      } else if (currentStep === "languages") {
        const merged = Array.from(
          new Set<LanguageCodeType>([primaryLanguage, ...supportedLanguages])
        );
        const savedLangs = await updateBusinessLanguagesApi(
          accessToken,
          organizationId,
          {
            primary_language: primaryLanguage,
            supported_languages: merged,
          }
        );
        setPrimaryLanguage(savedLangs.primary_language);
        setSupportedLanguages(savedLangs.supported_languages);
        markStepDone("languages");
      } else if (currentStep === "assistant") {
        if (assistantName.trim().length < 2) {
          setErrorMessage(
            "Assistant display name must be at least 2 characters."
          );
          return false;
        }
        if (greeting.trim().length < 5) {
          setErrorMessage("Welcome greeting must be at least 5 characters.");
          return false;
        }
        await updateAssistantSettingsApi(accessToken, organizationId, {
          assistant_name: assistantName.trim(),
          greeting: greeting.trim(),
          personality,
          response_style: responseStyle,
          enabled: assistantEnabled,
        });
        markStepDone("assistant");
      } else if (currentStep === "faqs") {
        markStepDone("faqs");
      } else if (currentStep === "escalation") {
        if (escalationEnabled) {
          if (contactName.trim().length < 2) {
            setErrorMessage(
              "Contact person's name is required when human escalation is enabled."
            );
            return false;
          }
          if (preferredMethod === "phone" && !contactPhone.trim()) {
            setErrorMessage(
              "Contact phone is required when preferred method is Phone."
            );
            return false;
          }
          if (preferredMethod === "email" && !contactEmail.trim()) {
            setErrorMessage(
              "Contact email is required when preferred method is Email."
            );
            return false;
          }
          if (
            preferredMethod === "either" &&
            !contactPhone.trim() &&
            !contactEmail.trim()
          ) {
            setErrorMessage(
              "Provide at least a contact phone or email when escalation is enabled."
            );
            return false;
          }
        }
        await updateEscalationSettingsApi(accessToken, organizationId, {
          enabled: escalationEnabled,
          contact_name: contactName.trim() || null,
          contact_email: contactEmail.trim() || null,
          contact_phone: contactPhone.trim() || null,
          preferred_method: preferredMethod,
          escalation_instructions: escalationInstructions.trim() || null,
        });
        markStepDone("escalation");
      }
      return true;
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to save onboarding step."
      );
      return false;
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveAndNext = async () => {
    const ok = await saveCurrentStepData();
    if (!ok) return;
    const idx = getStepIndex(currentStep);
    if (idx < ONBOARDING_STEPS.length - 1) {
      const nextStepId = ONBOARDING_STEPS[idx + 1].id;
      const updatedCompleted = markStepDone(currentStep);
      setCurrentStep(nextStepId);
      try {
        await updateOnboardingProgressApi(accessToken, organizationId, {
          current_step: nextStepId,
          completed_steps: updatedCompleted,
          is_completed: false,
        });
      } catch {
        // Step data is already saved
      }
    }
  };

  const handleSaveAndContinueLater = async () => {
    const ok = await saveCurrentStepData();
    if (!ok) return;
    setIsSaving(true);
    try {
      const updatedCompleted = markStepDone(currentStep);
      await updateOnboardingProgressApi(accessToken, organizationId, {
        current_step: currentStep,
        completed_steps: updatedCompleted,
        is_completed: bundle?.progress.is_completed ?? false,
      });
      setStatusToast("Progress saved. Returning to dashboard...");
      router.push("/dashboard");
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to save progress."
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleCompleteOnboarding = async () => {
    setErrorMessage(null);
    setIsSaving(true);
    try {
      const allSteps: OnboardingStepIdType[] = [
        "industry",
        "profile",
        "hours",
        "languages",
        "assistant",
        "faqs",
        "escalation",
        "review",
      ];
      await updateOnboardingProgressApi(accessToken, organizationId, {
        current_step: "review",
        completed_steps: allSteps,
        is_completed: true,
      });
      router.push("/dashboard");
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error
          ? err.message
          : "Unable to complete onboarding."
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleAddFaq = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    if (newQuestion.trim().length < 3 || newAnswer.trim().length < 2) {
      setErrorMessage(
        "Please enter both a valid question (min 3 chars) and answer (min 2 chars)."
      );
      return;
    }
    setIsSaving(true);
    try {
      const created = await createBusinessFaqApi(accessToken, organizationId, {
        question: newQuestion.trim(),
        answer: newAnswer.trim(),
        category: newCategory.trim() || "general",
        is_active: true,
        sort_order: newSortOrder,
      });
      setFaqs((prev) =>
        [...prev, created].sort((a, b) => a.sort_order - b.sort_order)
      );
      setNewQuestion("");
      setNewAnswer("");
      setNewSortOrder((prev) => prev + 10);
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to add FAQ."
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveEditFaq = async (faqId: string) => {
    setErrorMessage(null);
    if (editQuestion.trim().length < 3 || editAnswer.trim().length < 2) {
      setErrorMessage("Question and answer cannot be empty.");
      return;
    }
    setIsSaving(true);
    try {
      const updated = await updateBusinessFaqApi(
        accessToken,
        organizationId,
        faqId,
        {
          question: editQuestion.trim(),
          answer: editAnswer.trim(),
          category: editCategory.trim() || "general",
          sort_order: editSortOrder,
        }
      );
      setFaqs((prev) =>
        prev
          .map((item) => (item.id === faqId ? updated : item))
          .sort((a, b) => a.sort_order - b.sort_order)
      );
      setEditingFaqId(null);
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to update FAQ."
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleFaqActive = async (faq: BusinessFaqData) => {
    setIsSaving(true);
    try {
      const updated = await updateBusinessFaqApi(
        accessToken,
        organizationId,
        faq.id,
        { is_active: !faq.is_active }
      );
      setFaqs((prev) =>
        prev.map((item) => (item.id === faq.id ? updated : item))
      );
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to update FAQ status."
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteFaq = async (faqId: string) => {
    setIsSaving(true);
    try {
      await deleteBusinessFaqApi(accessToken, organizationId, faqId);
      setFaqs((prev) => prev.filter((item) => item.id !== faqId));
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to delete FAQ."
      );
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div
        role="status"
        className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/80 p-8 text-center font-mono text-xs text-[#36C6D3]"
      >
        Loading Stage 2 business onboarding configuration...
      </div>
    );
  }

  const currentStepMeta =
    ONBOARDING_STEPS.find((s) => s.id === currentStep) ?? ONBOARDING_STEPS[0];

  return (
    <div className="space-y-8">
      {/* Step Progress Bar */}
      <div className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <span className="font-mono text-xs font-semibold uppercase tracking-widest text-[#36C6D3]">
              Step {currentStepMeta.number} of {ONBOARDING_STEPS.length} —{" "}
              {currentStepMeta.label}
            </span>
            <p className="mt-0.5 text-xs text-[#A7B0C4]">
              Organization:{" "}
              <strong className="text-[#F5F7FC]">
                {bundle?.organization.name}
              </strong>{" "}
              ({industry.toUpperCase()})
            </p>
          </div>
          <span className="font-mono text-xs text-[#A7B0C4]">
            {completedSteps.length} / {ONBOARDING_STEPS.length} steps saved
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
          {ONBOARDING_STEPS.map((step) => {
            const isCurrent = step.id === currentStep;
            const isDone = completedSteps.includes(step.id);
            return (
              <button
                key={step.id}
                type="button"
                onClick={() => {
                  setErrorMessage(null);
                  setCurrentStep(step.id);
                }}
                className={`flex flex-col items-start rounded-xl border p-2.5 text-left transition ${
                  isCurrent
                    ? "border-[#7657F6] bg-[#7657F6]/25 text-[#F5F7FC]"
                    : isDone
                      ? "border-[#36C6D3]/50 bg-[#0B1020]/80 text-[#36C6D3]"
                      : "border-[#A7B0C4]/15 bg-[#0B1020]/50 text-[#A7B0C4]"
                }`}
              >
                <span className="font-mono text-[10px] uppercase">
                  0{step.number} {isDone ? "✓" : ""}
                </span>
                <span className="mt-0.5 truncate text-xs font-semibold">
                  {step.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {isReadOnlyStaff && (
        <div
          role="note"
          className="rounded-xl border border-amber-400/40 bg-amber-500/10 px-4 py-3 text-xs text-amber-200"
        >
          Your role in this organization is <strong>staff</strong>. You can
          inspect onboarding settings, but only <strong>owner</strong> or{" "}
          <strong>admin</strong> members can modify configuration.
        </div>
      )}

      {errorMessage && (
        <div
          role="alert"
          className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-xs text-rose-200"
        >
          {errorMessage}
        </div>
      )}

      {statusToast && (
        <div
          role="status"
          className="rounded-xl border border-[#36C6D3]/40 bg-[#36C6D3]/10 px-4 py-3 text-xs text-[#36C6D3]"
        >
          {statusToast}
        </div>
      )}

      {/* Active Step Panel */}
      <div className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-6 sm:p-8">
        {/* STEP 1: INDUSTRY SELECTION */}
        {currentStep === "industry" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-[#F5F7FC]">
                1. Industry Selection & Domain Alignment
              </h2>
              <p className="mt-1 text-sm text-[#A7B0C4]">
                Confirm the industry vertical for{" "}
                <strong className="text-[#F5F7FC]">
                  {bundle?.organization.name}
                </strong>
                . This governs your onboarding workflow, FAQ templates, and
                healthcare administrative safeguards.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              {(
                [
                  {
                    id: "salon" as const,
                    title: "Salon",
                    desc: "Hair, beauty, spa & grooming studios. Focuses on service inquiries, hours, and front-desk reception.",
                  },
                  {
                    id: "clinic" as const,
                    title: "Clinic",
                    desc: "Dental, dermatology & outpatient clinics. Administrative reception only with non-diagnostic safeguards.",
                  },
                  {
                    id: "hospital" as const,
                    title: "Hospital",
                    desc: "Multi-specialty hospitals & OPD switchboards. Administrative routing & emergency escalation directives.",
                  },
                ] as const
              ).map((option) => {
                const selected = industry === option.id;
                return (
                  <label
                    key={option.id}
                    className={`cursor-pointer rounded-2xl border p-5 transition ${
                      selected
                        ? "border-[#7657F6] bg-[#7657F6]/20 shadow-[0_0_24px_rgba(118,87,246,0.25)]"
                        : "border-[#A7B0C4]/20 bg-[#0B1020]/80 hover:border-[#A7B0C4]/45"
                    }`}
                  >
                    <input
                      type="radio"
                      name="onboarding-industry"
                      value={option.id}
                      checked={selected}
                      disabled={isReadOnlyStaff}
                      onChange={() => setIndustry(option.id)}
                      className="sr-only"
                    />
                    <div className="flex items-center justify-between">
                      <span className="text-base font-bold text-[#F5F7FC]">
                        {option.title}
                      </span>
                      <span
                        className={`h-3 w-3 rounded-full ${
                          selected ? "bg-[#36C6D3]" : "bg-[#A7B0C4]/30"
                        }`}
                      />
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-[#A7B0C4]">
                      {option.desc}
                    </p>
                  </label>
                );
              })}
            </div>
          </div>
        )}

        {/* STEP 2: BUSINESS PROFILE */}
        {currentStep === "profile" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-[#F5F7FC]">
                2. Business Profile
              </h2>
              <p className="mt-1 text-sm text-[#A7B0C4]">
                Configure the public identity, contact coordinates, and address
                for your {industry} reception desk.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label
                  htmlFor="profile-display-name"
                  className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                >
                  Business Name *
                </label>
                <input
                  id="profile-display-name"
                  type="text"
                  required
                  disabled={isReadOnlyStaff}
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="e.g., Lumiere Hair & Spa Studio"
                  className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                />
              </div>

              <div className="sm:col-span-2">
                <label
                  htmlFor="profile-description"
                  className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                >
                  Business Description
                </label>
                <textarea
                  id="profile-description"
                  rows={3}
                  disabled={isReadOnlyStaff}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Brief overview of your business, specialities, or services..."
                  className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                />
              </div>

              <div>
                <label
                  htmlFor="profile-phone"
                  className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                >
                  Phone
                </label>
                <input
                  id="profile-phone"
                  type="tel"
                  disabled={isReadOnlyStaff}
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+91 98765 43210"
                  className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                />
              </div>

              <div>
                <label
                  htmlFor="profile-email"
                  className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                >
                  Email
                </label>
                <input
                  id="profile-email"
                  type="email"
                  disabled={isReadOnlyStaff}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="reception@business.com"
                  className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                />
              </div>

              <div>
                <label
                  htmlFor="profile-website"
                  className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                >
                  Website URL
                </label>
                <input
                  id="profile-website"
                  type="url"
                  disabled={isReadOnlyStaff}
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                  placeholder="https://example.com"
                  className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                />
              </div>

              <div>
                <label
                  htmlFor="profile-timezone"
                  className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                >
                  Timezone *
                </label>
                <input
                  id="profile-timezone"
                  type="text"
                  required
                  disabled={isReadOnlyStaff}
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  placeholder="Asia/Kolkata or UTC"
                  className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                />
              </div>

              <div className="sm:col-span-2">
                <label
                  htmlFor="profile-address"
                  className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                >
                  Street Address
                </label>
                <input
                  id="profile-address"
                  type="text"
                  disabled={isReadOnlyStaff}
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="Building, street, and landmark"
                  className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                />
              </div>

              <div>
                <label
                  htmlFor="profile-city"
                  className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                >
                  City
                </label>
                <input
                  id="profile-city"
                  type="text"
                  disabled={isReadOnlyStaff}
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="Mumbai"
                  className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                />
              </div>

              <div>
                <label
                  htmlFor="profile-state"
                  className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                >
                  State / Province
                </label>
                <input
                  id="profile-state"
                  type="text"
                  disabled={isReadOnlyStaff}
                  value={stateRegion}
                  onChange={(e) => setStateRegion(e.target.value)}
                  placeholder="Maharashtra"
                  className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                />
              </div>

              <div>
                <label
                  htmlFor="profile-country"
                  className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                >
                  Country
                </label>
                <input
                  id="profile-country"
                  type="text"
                  disabled={isReadOnlyStaff}
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  placeholder="India"
                  className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                />
              </div>

              <div>
                <label
                  htmlFor="profile-postal-code"
                  className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                >
                  Postal Code
                </label>
                <input
                  id="profile-postal-code"
                  type="text"
                  disabled={isReadOnlyStaff}
                  value={postalCode}
                  onChange={(e) => setPostalCode(e.target.value)}
                  placeholder="400050"
                  className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                />
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: BUSINESS HOURS */}
        {currentStep === "hours" && (
          <div className="space-y-6">
            <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
              <div>
                <h2 className="text-xl font-bold text-[#F5F7FC]">
                  3. Weekly Operating Hours
                </h2>
                <p className="mt-1 text-sm text-[#A7B0C4]">
                  Set open/closed status and operating hours for each day of the
                  week.
                </p>
              </div>
              <div className="font-mono text-xs text-[#36C6D3]">
                Timezone: {timezone}
              </div>
            </div>

            <div className="space-y-3">
              {schedule.map((item, idx) => (
                <div
                  key={item.weekday}
                  className="flex flex-col gap-3 rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/80 p-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex items-center gap-3">
                    <input
                      id={`day-open-${item.weekday}`}
                      type="checkbox"
                      checked={!item.is_closed}
                      disabled={isReadOnlyStaff}
                      onChange={(e) => {
                        const isOpen = e.target.checked;
                        setSchedule((prev) =>
                          prev.map((row, i) =>
                            i === idx
                              ? {
                                  ...row,
                                  is_closed: !isOpen,
                                  opens_at: isOpen
                                    ? row.opens_at ?? "09:00"
                                    : null,
                                  closes_at: isOpen
                                    ? row.closes_at ?? "18:00"
                                    : null,
                                  is_overnight: isOpen
                                    ? row.is_overnight
                                    : false,
                                }
                              : row
                          )
                        );
                      }}
                      className="h-4 w-4 rounded border-[#A7B0C4]/40 accent-[#7657F6]"
                    />
                    <label
                      htmlFor={`day-open-${item.weekday}`}
                      className="w-28 text-sm font-semibold text-[#F5F7FC]"
                    >
                      {WEEKDAY_NAMES[item.weekday]}
                    </label>
                    <span
                      className={`rounded px-2 py-0.5 font-mono text-[10px] uppercase ${
                        item.is_closed
                          ? "bg-rose-500/15 text-rose-300"
                          : "bg-[#36C6D3]/15 text-[#36C6D3]"
                      }`}
                    >
                      {item.is_closed ? "Closed" : "Open"}
                    </span>
                  </div>

                  {!item.is_closed && (
                    <div className="flex flex-wrap items-center gap-3">
                      <div className="flex items-center gap-1.5">
                        <label
                          htmlFor={`opens-${item.weekday}`}
                          className="font-mono text-xs text-[#A7B0C4]"
                        >
                          Opens:
                        </label>
                        <input
                          id={`opens-${item.weekday}`}
                          type="time"
                          disabled={isReadOnlyStaff}
                          value={item.opens_at ?? "09:00"}
                          onChange={(e) =>
                            setSchedule((prev) =>
                              prev.map((row, i) =>
                                i === idx
                                  ? { ...row, opens_at: e.target.value }
                                  : row
                              )
                            )
                          }
                          className="rounded-lg border border-[#A7B0C4]/25 bg-[#171D33] px-2.5 py-1 text-xs text-[#F5F7FC]"
                        />
                      </div>

                      <div className="flex items-center gap-1.5">
                        <label
                          htmlFor={`closes-${item.weekday}`}
                          className="font-mono text-xs text-[#A7B0C4]"
                        >
                          Closes:
                        </label>
                        <input
                          id={`closes-${item.weekday}`}
                          type="time"
                          disabled={isReadOnlyStaff}
                          value={item.closes_at ?? "18:00"}
                          onChange={(e) =>
                            setSchedule((prev) =>
                              prev.map((row, i) =>
                                i === idx
                                  ? { ...row, closes_at: e.target.value }
                                  : row
                              )
                            )
                          }
                          className="rounded-lg border border-[#A7B0C4]/25 bg-[#171D33] px-2.5 py-1 text-xs text-[#F5F7FC]"
                        />
                      </div>

                      <label className="inline-flex items-center gap-1.5 font-mono text-xs text-[#A7B0C4]">
                        <input
                          type="checkbox"
                          disabled={isReadOnlyStaff}
                          checked={item.is_overnight}
                          onChange={(e) =>
                            setSchedule((prev) =>
                              prev.map((row, i) =>
                                i === idx
                                  ? { ...row, is_overnight: e.target.checked }
                                  : row
                              )
                            )
                          }
                          className="accent-[#7657F6]"
                        />
                        Overnight
                      </label>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* STEP 4: LANGUAGES */}
        {currentStep === "languages" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-[#F5F7FC]">
                4. Language Preferences
              </h2>
              <p className="mt-1 text-sm text-[#A7B0C4]">
                Select the primary language and additional supported languages
                for your reception desk. Note: <strong>Hinglish</strong> is
                supported as a natural conversational preference rather than a
                formal ISO locale.
              </p>
            </div>

            <div>
              <label
                htmlFor="primary-language-select"
                className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
              >
                Primary Language
              </label>
              <select
                id="primary-language-select"
                disabled={isReadOnlyStaff}
                value={primaryLanguage}
                onChange={(e) => {
                  const nextPrimary = e.target.value as LanguageCodeType;
                  setPrimaryLanguage(nextPrimary);
                  if (!supportedLanguages.includes(nextPrimary)) {
                    setSupportedLanguages((prev) => [...prev, nextPrimary]);
                  }
                }}
                className="mt-1.5 w-full max-w-sm rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
              >
                <option value="en">English (en)</option>
                <option value="hi">Hindi (hi)</option>
                <option value="hinglish">
                  Hinglish (Conversational Preference)
                </option>
              </select>
            </div>

            <div className="space-y-3">
              <div className="text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]">
                Supported Languages
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                {(["en", "hi", "hinglish"] as const).map((code) => {
                  const isPrimary = primaryLanguage === code;
                  const isChecked =
                    isPrimary || supportedLanguages.includes(code);
                  return (
                    <label
                      key={code}
                      className={`flex cursor-pointer flex-col justify-between rounded-xl border p-4 ${
                        isChecked
                          ? "border-[#36C6D3]/60 bg-[#0B1020]"
                          : "border-[#A7B0C4]/15 bg-[#0B1020]/50"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-bold text-[#F5F7FC]">
                          {LANGUAGE_LABELS[code].name}
                        </span>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          disabled={isPrimary || isReadOnlyStaff}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSupportedLanguages((prev) =>
                                prev.includes(code) ? prev : [...prev, code]
                              );
                            } else {
                              setSupportedLanguages((prev) =>
                                prev.filter((c) => c !== code)
                              );
                            }
                          }}
                          className="accent-[#36C6D3]"
                        />
                      </div>
                      <p className="mt-2 text-xs text-[#A7B0C4]">
                        {LANGUAGE_LABELS[code].subtitle}
                      </p>
                      {isPrimary && (
                        <span className="mt-2 inline-block font-mono text-[10px] uppercase text-[#36C6D3]">
                          ★ Primary Language
                        </span>
                      )}
                    </label>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* STEP 5: ASSISTANT CONFIGURATION */}
        {currentStep === "assistant" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-[#F5F7FC]">
                5. Assistant Configuration
              </h2>
              <p className="mt-1 text-sm text-[#A7B0C4]">
                Configure your AI receptionist&apos;s display name, welcome
                greeting, personality, and response style.{" "}
                <span className="font-mono text-xs text-[#36C6D3]">
                  (Stage 2 stores configuration only; OpenAI Realtime voice
                  streaming connects in Stage 3.)
                </span>
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label
                  htmlFor="assistant-name-input"
                  className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                >
                  Assistant Display Name *
                </label>
                <input
                  id="assistant-name-input"
                  type="text"
                  disabled={isReadOnlyStaff}
                  value={assistantName}
                  onChange={(e) => setAssistantName(e.target.value)}
                  placeholder="e.g., Svario Front Desk Concierge"
                  className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                />
              </div>

              <div className="sm:col-span-2">
                <label
                  htmlFor="assistant-greeting-input"
                  className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                >
                  Welcome Greeting *
                </label>
                <textarea
                  id="assistant-greeting-input"
                  rows={3}
                  disabled={isReadOnlyStaff}
                  value={greeting}
                  onChange={(e) => setGreeting(e.target.value)}
                  placeholder="Hello! Thank you for calling. How may I assist you today?"
                  className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                />
              </div>

              <div>
                <label
                  htmlFor="assistant-personality-select"
                  className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                >
                  Personality
                </label>
                <select
                  id="assistant-personality-select"
                  disabled={isReadOnlyStaff}
                  value={personality}
                  onChange={(e) =>
                    setPersonality(e.target.value as AssistantPersonalityType)
                  }
                  className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                >
                  <option value="professional">Professional</option>
                  <option value="friendly">Friendly</option>
                  <option value="warm">Warm</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="assistant-style-select"
                  className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                >
                  Response Style
                </label>
                <select
                  id="assistant-style-select"
                  disabled={isReadOnlyStaff}
                  value={responseStyle}
                  onChange={(e) =>
                    setResponseStyle(
                      e.target.value as AssistantResponseStyleType
                    )
                  }
                  className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                >
                  <option value="concise">Concise</option>
                  <option value="balanced">Balanced</option>
                  <option value="detailed">Detailed</option>
                </select>
              </div>

              <div className="sm:col-span-2">
                <label className="inline-flex cursor-pointer items-center gap-3 rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-4 py-3">
                  <input
                    type="checkbox"
                    disabled={isReadOnlyStaff}
                    checked={assistantEnabled}
                    onChange={(e) => setAssistantEnabled(e.target.checked)}
                    className="h-4 w-4 accent-[#36C6D3]"
                  />
                  <span className="text-sm font-medium text-[#F5F7FC]">
                    Mark Assistant Configuration as Enabled Ready
                  </span>
                </label>
              </div>
            </div>
          </div>
        )}

        {/* STEP 6: BUSINESS FAQS */}
        {currentStep === "faqs" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-[#F5F7FC]">
                6. Business FAQ Management
              </h2>
              <p className="mt-1 text-sm text-[#A7B0C4]">
                Add, edit, sort, and activate/deactivate frequently asked
                questions for your {industry}. Starter examples below are
                editable templates only—always provide your real business
                details.
              </p>
            </div>

            {/* Industry Starter Examples */}
            {bundle?.faq_templates && bundle.faq_templates.length > 0 && (
              <div className="rounded-xl border border-[#7657F6]/35 bg-[#0B1020]/90 p-4">
                <div className="font-mono text-xs font-semibold uppercase tracking-wider text-[#36C6D3]">
                  Editable {industry.toUpperCase()} Starter Question Templates
                </div>
                <p className="mt-1 text-xs text-[#A7B0C4]">
                  Click a template below to pre-fill the question field, then
                  write your organization&apos;s accurate answer before saving:
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {bundle.faq_templates.map((tpl) => (
                    <button
                      key={tpl.question}
                      type="button"
                      disabled={isReadOnlyStaff}
                      onClick={() => {
                        setNewQuestion(tpl.question);
                        setNewCategory(tpl.category);
                        setNewAnswer("");
                      }}
                      className="rounded-lg border border-[#7657F6]/45 bg-[#171D33] px-3 py-1.5 text-xs text-[#F5F7FC] transition hover:border-[#36C6D3]"
                    >
                      + &ldquo;{tpl.question}&rdquo;
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Add FAQ Form */}
            {!isReadOnlyStaff && (
              <form
                onSubmit={(e) => void handleAddFaq(e)}
                className="space-y-4 rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020]/70 p-4"
              >
                <div className="font-mono text-xs font-semibold uppercase tracking-wider text-[#F5F7FC]">
                  Add New FAQ Entry
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="sm:col-span-2">
                    <label
                      htmlFor="new-faq-question"
                      className="block text-xs text-[#A7B0C4]"
                    >
                      Question *
                    </label>
                    <input
                      id="new-faq-question"
                      type="text"
                      value={newQuestion}
                      onChange={(e) => setNewQuestion(e.target.value)}
                      placeholder="e.g., What are your opening hours?"
                      className="mt-1 w-full rounded-lg border border-[#A7B0C4]/25 bg-[#171D33] px-3 py-2 text-xs text-[#F5F7FC]"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label
                        htmlFor="new-faq-category"
                        className="block text-xs text-[#A7B0C4]"
                      >
                        Category
                      </label>
                      <input
                        id="new-faq-category"
                        type="text"
                        value={newCategory}
                        onChange={(e) => setNewCategory(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[#A7B0C4]/25 bg-[#171D33] px-3 py-2 text-xs text-[#F5F7FC]"
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="new-faq-sort"
                        className="block text-xs text-[#A7B0C4]"
                      >
                        Sort Order
                      </label>
                      <input
                        id="new-faq-sort"
                        type="number"
                        min={0}
                        value={newSortOrder}
                        onChange={(e) =>
                          setNewSortOrder(Number(e.target.value) || 0)
                        }
                        className="mt-1 w-full rounded-lg border border-[#A7B0C4]/25 bg-[#171D33] px-3 py-2 text-xs text-[#F5F7FC]"
                      />
                    </div>
                  </div>
                  <div className="sm:col-span-3">
                    <label
                      htmlFor="new-faq-answer"
                      className="block text-xs text-[#A7B0C4]"
                    >
                      Answer *
                    </label>
                    <textarea
                      id="new-faq-answer"
                      rows={2}
                      value={newAnswer}
                      onChange={(e) => setNewAnswer(e.target.value)}
                      placeholder="Write your accurate business answer..."
                      className="mt-1 w-full rounded-lg border border-[#A7B0C4]/25 bg-[#171D33] px-3 py-2 text-xs text-[#F5F7FC]"
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="rounded-xl bg-[#7657F6] px-4 py-2 text-xs font-semibold text-[#F5F7FC] hover:bg-[#7657F6]/90 disabled:opacity-50"
                >
                  Add FAQ
                </button>
              </form>
            )}

            {/* Existing FAQs List */}
            <div className="space-y-3">
              {faqs.length === 0 ? (
                <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/50 p-6 text-center text-xs text-[#A7B0C4]">
                  No FAQs configured yet. Add an FAQ above or select an
                  industry starter template.
                </div>
              ) : (
                faqs.map((faq) => (
                  <div
                    key={faq.id}
                    className="rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020]/85 p-4"
                  >
                    {editingFaqId === faq.id ? (
                      <div className="space-y-3">
                        <input
                          type="text"
                          value={editQuestion}
                          onChange={(e) => setEditQuestion(e.target.value)}
                          className="w-full rounded-lg border border-[#A7B0C4]/25 bg-[#171D33] px-3 py-1.5 text-xs text-[#F5F7FC]"
                        />
                        <textarea
                          rows={2}
                          value={editAnswer}
                          onChange={(e) => setEditAnswer(e.target.value)}
                          className="w-full rounded-lg border border-[#A7B0C4]/25 bg-[#171D33] px-3 py-1.5 text-xs text-[#F5F7FC]"
                        />
                        <div className="flex flex-wrap items-center gap-2">
                          <input
                            type="text"
                            value={editCategory}
                            onChange={(e) => setEditCategory(e.target.value)}
                            className="w-32 rounded-lg border border-[#A7B0C4]/25 bg-[#171D33] px-2.5 py-1 text-xs text-[#F5F7FC]"
                          />
                          <input
                            type="number"
                            value={editSortOrder}
                            onChange={(e) =>
                              setEditSortOrder(Number(e.target.value) || 0)
                            }
                            className="w-24 rounded-lg border border-[#A7B0C4]/25 bg-[#171D33] px-2.5 py-1 text-xs text-[#F5F7FC]"
                          />
                          <button
                            type="button"
                            onClick={() => void handleSaveEditFaq(faq.id)}
                            className="rounded-lg bg-[#36C6D3] px-3 py-1 text-xs font-semibold text-[#0B1020]"
                          >
                            Save
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingFaqId(null)}
                            className="rounded-lg border border-[#A7B0C4]/30 px-3 py-1 text-xs text-[#A7B0C4]"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded bg-[#171D33] px-2 py-0.5 font-mono text-[10px] uppercase text-[#36C6D3]">
                              {faq.category}
                            </span>
                            <span className="font-mono text-[10px] text-[#A7B0C4]">
                              Order: {faq.sort_order}
                            </span>
                            <span
                              className={`rounded px-2 py-0.5 font-mono text-[10px] ${
                                faq.is_active
                                  ? "bg-[#36C6D3]/15 text-[#36C6D3]"
                                  : "bg-amber-500/15 text-amber-300"
                              }`}
                            >
                              {faq.is_active ? "Active" : "Inactive"}
                            </span>
                          </div>
                          <h4 className="mt-1.5 text-sm font-semibold text-[#F5F7FC]">
                            {faq.question}
                          </h4>
                          <p className="mt-1 text-xs text-[#A7B0C4]">
                            {faq.answer}
                          </p>
                        </div>

                        {!isReadOnlyStaff && (
                          <div className="flex shrink-0 flex-wrap items-center gap-2">
                            <button
                              type="button"
                              onClick={() => void handleToggleFaqActive(faq)}
                              className="rounded-lg border border-[#A7B0C4]/25 px-2.5 py-1 text-[11px] text-[#F5F7FC]"
                            >
                              {faq.is_active ? "Deactivate" : "Activate"}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setEditingFaqId(faq.id);
                                setEditQuestion(faq.question);
                                setEditAnswer(faq.answer);
                                setEditCategory(faq.category);
                                setEditSortOrder(faq.sort_order);
                              }}
                              className="rounded-lg border border-[#7657F6]/50 px-2.5 py-1 text-[11px] text-[#36C6D3]"
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleDeleteFaq(faq.id)}
                              className="rounded-lg border border-rose-400/40 px-2.5 py-1 text-[11px] text-rose-300"
                            >
                              Delete
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* STEP 7: HUMAN ESCALATION */}
        {currentStep === "escalation" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-[#F5F7FC]">
                7. Human Escalation & Safeguards
              </h2>
              <p className="mt-1 text-sm text-[#A7B0C4]">
                Configure how and when your reception workflow should escalate
                conversations to a human administrator or front-desk coordinator.
              </p>
            </div>

            {isHealthcare && (
              <div
                role="region"
                aria-label="Healthcare Administrative Safeguards"
                className="rounded-xl border border-amber-400/45 bg-amber-500/10 p-4 text-xs leading-relaxed text-amber-100"
              >
                <div className="font-mono font-semibold uppercase tracking-wider text-amber-300">
                  Mandatory Healthcare & Administrative Safeguards ({industry.toUpperCase()})
                </div>
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  <li>
                    Clinics and hospitals on Svario operate strictly as{" "}
                    <strong>administrative reception systems only</strong>.
                  </li>
                  <li>
                    <strong>No medical diagnosis</strong>,{" "}
                    <strong>no prescriptions</strong>,{" "}
                    <strong>no treatment recommendations</strong>, and{" "}
                    <strong>no clinical decision-making</strong>.
                  </li>
                  <li>
                    Emergency-related requests must be directed immediately to
                    appropriate local emergency services or the hospital&apos;s
                    emergency channel.
                  </li>
                  <li>Do not collect unnecessary patient medical information.</li>
                </ul>
              </div>
            )}

            <div className="space-y-4">
              <label className="inline-flex cursor-pointer items-center gap-3 rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-4 py-3">
                <input
                  type="checkbox"
                  disabled={isReadOnlyStaff}
                  checked={escalationEnabled}
                  onChange={(e) => setEscalationEnabled(e.target.checked)}
                  className="h-4 w-4 accent-[#36C6D3]"
                />
                <span className="text-sm font-semibold text-[#F5F7FC]">
                  Enable Human Escalation Handoff
                </span>
              </label>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor="esc-contact-name"
                    className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                  >
                    Contact Person Name {escalationEnabled ? "*" : ""}
                  </label>
                  <input
                    id="esc-contact-name"
                    type="text"
                    disabled={isReadOnlyStaff}
                    value={contactName}
                    onChange={(e) => setContactName(e.target.value)}
                    placeholder="e.g., Front Desk Duty Manager"
                    className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                  />
                </div>

                <div>
                  <label
                    htmlFor="esc-preferred-method"
                    className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                  >
                    Preferred Contact Method
                  </label>
                  <select
                    id="esc-preferred-method"
                    disabled={isReadOnlyStaff}
                    value={preferredMethod}
                    onChange={(e) =>
                      setPreferredMethod(e.target.value as EscalationMethodType)
                    }
                    className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                  >
                    <option value="phone">Phone</option>
                    <option value="email">Email</option>
                    <option value="either">Either Phone or Email</option>
                  </select>
                </div>

                <div>
                  <label
                    htmlFor="esc-contact-phone"
                    className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                  >
                    Contact Phone
                  </label>
                  <input
                    id="esc-contact-phone"
                    type="tel"
                    disabled={isReadOnlyStaff}
                    value={contactPhone}
                    onChange={(e) => setContactPhone(e.target.value)}
                    placeholder="+91 98765 43210"
                    className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                  />
                </div>

                <div>
                  <label
                    htmlFor="esc-contact-email"
                    className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                  >
                    Contact Email
                  </label>
                  <input
                    id="esc-contact-email"
                    type="email"
                    disabled={isReadOnlyStaff}
                    value={contactEmail}
                    onChange={(e) => setContactEmail(e.target.value)}
                    placeholder="escalation@organization.com"
                    className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                  />
                </div>

                <div className="sm:col-span-2">
                  <label
                    htmlFor="esc-instructions"
                    className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
                  >
                    Escalation Instructions
                  </label>
                  <textarea
                    id="esc-instructions"
                    rows={3}
                    disabled={isReadOnlyStaff}
                    value={escalationInstructions}
                    onChange={(e) => setEscalationInstructions(e.target.value)}
                    placeholder="Specify when callers should be transferred to the human reception desk..."
                    className="mt-1.5 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2.5 text-sm text-[#F5F7FC]"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 8: REVIEW AND COMPLETION */}
        {currentStep === "review" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-[#F5F7FC]">
                8. Review & Complete Onboarding
              </h2>
              <p className="mt-1 text-sm text-[#A7B0C4]">
                Verify your organization&apos;s onboarding configuration below,
                then click <strong>Complete Onboarding</strong> to finalize and
                return to your dashboard.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/80 p-4">
                <div className="font-mono text-[10px] uppercase tracking-wider text-[#36C6D3]">
                  Industry & Business Profile
                </div>
                <div className="mt-1 text-base font-bold text-[#F5F7FC]">
                  {displayName || bundle?.organization.name}
                </div>
                <div className="mt-1 text-xs text-[#A7B0C4]">
                  Industry:{" "}
                  <strong className="uppercase text-[#F5F7FC]">
                    {industry}
                  </strong>{" "}
                  • Timezone: {timezone}
                </div>
                <div className="mt-1 text-xs text-[#A7B0C4]">
                  Phone: {phone || "Not set"} • Email: {email || "Not set"}
                </div>
                <div className="mt-1 text-xs text-[#A7B0C4]">
                  Location:{" "}
                  {[address, city, stateRegion, country, postalCode]
                    .filter(Boolean)
                    .join(", ") || "Not set"}
                </div>
              </div>

              <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/80 p-4">
                <div className="font-mono text-[10px] uppercase tracking-wider text-[#36C6D3]">
                  Languages & Assistant
                </div>
                <div className="mt-1 text-base font-bold text-[#F5F7FC]">
                  {assistantName}
                </div>
                <div className="mt-1 text-xs text-[#A7B0C4]">
                  Primary Language:{" "}
                  <strong className="uppercase text-[#F5F7FC]">
                    {primaryLanguage}
                  </strong>{" "}
                  • Supported: {supportedLanguages.join(", ").toUpperCase()}
                </div>
                <div className="mt-1 text-xs text-[#A7B0C4]">
                  Personality: {personality} • Response Style: {responseStyle} •
                  Status: {assistantEnabled ? "Enabled" : "Disabled"}
                </div>
              </div>

              <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/80 p-4">
                <div className="font-mono text-[10px] uppercase tracking-wider text-[#36C6D3]">
                  Operating Hours & FAQs
                </div>
                <div className="mt-1 text-xs text-[#F5F7FC]">
                  Open Days:{" "}
                  {schedule.filter((d) => !d.is_closed).length} / 7 days
                  configured
                </div>
                <div className="mt-1 text-xs text-[#A7B0C4]">
                  Active FAQs:{" "}
                  {faqs.filter((f) => f.is_active).length} active ({faqs.length}{" "}
                  total)
                </div>
              </div>

              <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/80 p-4">
                <div className="font-mono text-[10px] uppercase tracking-wider text-[#36C6D3]">
                  Human Escalation
                </div>
                <div className="mt-1 text-xs text-[#F5F7FC]">
                  Status: {escalationEnabled ? "Enabled" : "Disabled"}
                </div>
                {escalationEnabled && (
                  <div className="mt-1 text-xs text-[#A7B0C4]">
                    Contact: {contactName || "—"} ({preferredMethod}) •{" "}
                    {contactPhone || contactEmail || "—"}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Wizard Navigation Footer */}
        <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-[#A7B0C4]/15 pt-6">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handlePreviousStep}
              disabled={currentStep === "industry" || isSaving}
              className="rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-4 py-2 text-xs font-semibold text-[#F5F7FC] transition hover:border-[#7657F6]/60 disabled:cursor-not-allowed disabled:opacity-40"
            >
              ← Back
            </button>

            {!isReadOnlyStaff && (
              <button
                type="button"
                onClick={() => void handleSaveAndContinueLater()}
                disabled={isSaving}
                className="rounded-xl border border-[#36C6D3]/45 bg-[#36C6D3]/10 px-4 py-2 text-xs font-semibold text-[#36C6D3] transition hover:bg-[#36C6D3]/20 disabled:opacity-40"
              >
                Save & Continue Later
              </button>
            )}
          </div>

          <div className="flex items-center gap-3">
            {currentStep !== "review" ? (
              <button
                type="button"
                onClick={() => void handleSaveAndNext()}
                disabled={isSaving}
                className="rounded-xl bg-[#7657F6] px-5 py-2.5 text-xs font-semibold text-[#F5F7FC] shadow-[0_0_20px_rgba(118,87,246,0.3)] transition hover:bg-[#7657F6]/90 disabled:opacity-50"
              >
                {isSaving ? "Saving..." : "Save & Next →"}
              </button>
            ) : (
              !isReadOnlyStaff && (
                <button
                  type="button"
                  onClick={() => void handleCompleteOnboarding()}
                  disabled={isSaving}
                  className="rounded-xl bg-[#36C6D3] px-6 py-2.5 text-xs font-bold text-[#0B1020] shadow-[0_0_24px_rgba(54,198,211,0.35)] transition hover:bg-[#36C6D3]/90 disabled:opacity-50"
                >
                  {isSaving ? "Completing..." : "Complete Onboarding ✓"}
                </button>
              )
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
