"use client";

import React, { useState } from "react";
import { useAuthOrganization } from "@/context/AuthOrganizationContext";
import type { OrganizationIndustryType } from "@/types/platform";

interface IndustryOption {
  value: OrganizationIndustryType;
  label: string;
  tagline: string;
}

const INDUSTRY_OPTIONS: readonly IndustryOption[] = [
  {
    value: "salon",
    label: "Salon",
    tagline: "Hair, beauty & grooming studios",
  },
  {
    value: "clinic",
    label: "Clinic",
    tagline: "Dental, dermatology & outpatient clinics",
  },
  {
    value: "hospital",
    label: "Hospital",
    tagline: "Multi-specialty hospitals & OPD switchboards",
  },
] as const;

interface OrganizationOnboardingFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

export function OrganizationOnboardingForm({
  onSuccess,
  onCancel,
}: OrganizationOnboardingFormProps): React.JSX.Element {
  const { createOrganization } = useAuthOrganization();
  const [name, setName] = useState<string>("");
  const [industry, setIndustry] = useState<OrganizationIndustryType>("salon");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    const trimmedName = name.trim();
    if (trimmedName.length < 2) {
      setErrorMessage(
        "Organization name must contain at least 2 characters."
      );
      return;
    }

    setIsSubmitting(true);
    try {
      await createOrganization({
        name: trimmedName,
        industry,
      });
      setName("");
      onSuccess?.();
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error
          ? err.message
          : "Failed to create organization through Svario API."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="rounded-2xl border border-[#7657F6]/40 bg-[#171D33]/90 p-6 shadow-[0_16px_44px_rgba(11,16,32,0.6)] sm:p-8">
      <div className="mb-6 space-y-1.5">
        <span className="font-mono text-xs font-semibold uppercase tracking-widest text-[#36C6D3]">
          ORGANIZATION SETUP • STAGE 1
        </span>
        <h2 className="text-2xl font-bold tracking-tight text-[#F5F7FC]">
          Create Your Organization
        </h2>
        <p className="text-sm text-[#A7B0C4]">
          Select your target industry vertical and organization name. Your
          account will be assigned the <strong className="text-[#F5F7FC]">owner</strong> role.
        </p>
      </div>

      <form onSubmit={(e) => void handleSubmit(e)} noValidate className="space-y-6">
        {errorMessage && (
          <div
            role="alert"
            className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-xs text-rose-200"
          >
            {errorMessage}
          </div>
        )}

        <div>
          <label
            htmlFor="org-name-input"
            className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]"
          >
            Organization Name
          </label>
          <input
            id="org-name-input"
            name="organizationName"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Lumiere Wellness Studio"
            className="mt-2 w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-4 py-2.5 text-sm text-[#F5F7FC] placeholder-[#A7B0C4]/50 focus:border-[#7657F6] focus:outline-none"
          />
        </div>

        <fieldset>
          <legend className="block text-xs font-semibold uppercase tracking-wider text-[#A7B0C4]">
            Select Industry Vertical
          </legend>
          <div className="mt-2.5 grid gap-3 sm:grid-cols-3">
            {INDUSTRY_OPTIONS.map((option) => {
              const selected = industry === option.value;
              return (
                <label
                  key={option.value}
                  className={`cursor-pointer rounded-xl border p-4 transition ${
                    selected
                      ? "border-[#7657F6] bg-[#7657F6]/20 shadow-[0_0_20px_rgba(118,87,246,0.25)]"
                      : "border-[#A7B0C4]/20 bg-[#0B1020]/80 hover:border-[#A7B0C4]/45"
                  }`}
                >
                  <input
                    type="radio"
                    name="industry"
                    value={option.value}
                    checked={selected}
                    onChange={() => setIndustry(option.value)}
                    className="sr-only"
                  />
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-[#F5F7FC]">
                      {option.label}
                    </span>
                    <span
                      className={`h-2.5 w-2.5 rounded-full ${
                        selected ? "bg-[#36C6D3]" : "bg-[#A7B0C4]/30"
                      }`}
                    />
                  </div>
                  <p className="mt-1.5 text-xs text-[#A7B0C4]">
                    {option.tagline}
                  </p>
                </label>
              );
            })}
          </div>
        </fieldset>

        <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-4 py-2.5 text-xs font-semibold text-[#A7B0C4] hover:text-[#F5F7FC]"
            >
              Cancel
            </button>
          )}
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-xl bg-[#7657F6] px-5 py-2.5 text-sm font-semibold text-[#F5F7FC] shadow-[0_0_24px_rgba(118,87,246,0.35)] transition hover:bg-[#7657F6]/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? "Creating Organization..." : "Create Organization"}
          </button>
        </div>
      </form>
    </div>
  );
}
