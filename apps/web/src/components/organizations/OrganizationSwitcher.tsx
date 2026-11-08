"use client";

import React from "react";
import { useAuthOrganization } from "@/context/AuthOrganizationContext";

interface OrganizationSwitcherProps {
  onNewOrganizationClick: () => void;
}

export function OrganizationSwitcher({
  onNewOrganizationClick,
}: OrganizationSwitcherProps): React.JSX.Element | null {
  const {
    organizations,
    activeOrganization,
    setActiveOrganizationId,
  } = useAuthOrganization();

  if (organizations.length === 0 || !activeOrganization) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-2">
        <label
          htmlFor="active-org-select"
          className="font-mono text-xs uppercase tracking-wider text-[#A7B0C4]"
        >
          Active Org:
        </label>
        <select
          id="active-org-select"
          aria-label="Select Active Organization"
          value={activeOrganization.id}
          onChange={(e) => setActiveOrganizationId(e.target.value)}
          className="rounded-xl border border-[#7657F6]/50 bg-[#0B1020] px-3 py-1.5 text-xs font-semibold text-[#F5F7FC] focus:border-[#36C6D3] focus:outline-none"
        >
          {organizations.map((org) => (
            <option key={org.id} value={org.id}>
              {org.name} ({org.industry.toUpperCase()} • {org.membership_role})
            </option>
          ))}
        </select>
      </div>

      <button
        type="button"
        onClick={onNewOrganizationClick}
        className="rounded-xl border border-[#A7B0C4]/25 bg-[#171D33] px-3 py-1.5 text-xs font-semibold text-[#36C6D3] transition hover:border-[#36C6D3]/60"
      >
        + New Organization
      </button>
    </div>
  );
}
