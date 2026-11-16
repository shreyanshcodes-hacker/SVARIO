import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ClinicDashboardView } from "@/components/dashboard/ClinicDashboardView";

const mocks = vi.hoisted(() => ({
  departments: [
    {
      id: "dept-1",
      organization_id: "org-1",
      business_id: "biz-1",
      name: "General Medicine",
      description: "Primary outpatient care",
      is_active: true,
      created_at: "2026-11-16T08:00:00Z",
      updated_at: "2026-11-16T08:00:00Z",
    },
  ],
  specialities: [
    {
      id: "spec-1",
      organization_id: "org-1",
      business_id: "biz-1",
      name: "Internal Medicine",
      description: null,
      is_active: true,
      created_at: "2026-11-16T08:00:00Z",
      updated_at: "2026-11-16T08:00:00Z",
    },
  ],
  consultationTypes: [
    {
      id: "ct-1",
      organization_id: "org-1",
      business_id: "biz-1",
      name: "Standard Consultation",
      description: null,
      duration_minutes: 30,
      consultation_mode: "in_person" as const,
      fee_amount: "800.00",
      currency_code: "INR",
      is_active: true,
      created_at: "2026-11-16T08:00:00Z",
      updated_at: "2026-11-16T08:00:00Z",
    },
  ],
  doctors: [
    {
      id: "doc-1",
      organization_id: "org-1",
      business_id: "biz-1",
      display_name: "Dr. Meera Nair",
      professional_title: "MD, General Physician",
      public_bio: null,
      languages: ["en", "hi"],
      is_active: true,
      department_ids: ["dept-1"],
      speciality_ids: ["spec-1"],
      consultation_type_ids: ["ct-1"],
      created_at: "2026-11-16T08:00:00Z",
      updated_at: "2026-11-16T08:00:00Z",
    },
  ],
  appointments: [
    {
      id: "appt-1",
      organization_id: "org-1",
      business_id: "biz-1",
      booking_reference: "CLN-1234ABCD",
      doctor_id: "doc-1",
      doctor_name: "Dr. Meera Nair",
      consultation_type_id: "ct-1",
      consultation_type_name: "Standard Consultation",
      department_id: "dept-1",
      patient_display_name: "Rohan Sharma",
      patient_contact: "+919999888877",
      starts_at: "2026-11-24T09:00:00+05:30",
      ends_at: "2026-11-24T09:30:00+05:30",
      timezone: "Asia/Kolkata",
      status: "confirmed" as const,
      source: "dashboard" as const,
      cancellation_reason: null,
      cancelled_at: null,
      created_at: "2026-11-16T08:00:00Z",
      updated_at: "2026-11-16T08:00:00Z",
    },
  ],
  cancelClinicAppointment: vi.fn(),
  fetchClinicDepartments: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  fetchClinicDepartments: (...args: unknown[]) => mocks.fetchClinicDepartments(...args),
  createClinicDepartment: vi.fn(),
  updateClinicDepartment: vi.fn(),
  fetchClinicSpecialities: vi.fn(async () => mocks.specialities),
  createClinicSpeciality: vi.fn(),
  fetchClinicConsultationTypes: vi.fn(async () => mocks.consultationTypes),
  createClinicConsultationType: vi.fn(),
  fetchClinicDoctors: vi.fn(async () => mocks.doctors),
  createClinicDoctor: vi.fn(),
  updateClinicDoctor: vi.fn(),
  upsertClinicDoctorWorkingHours: vi.fn(),
  fetchClinicAvailability: vi.fn(async () => ({
    organization_id: "org-1",
    business_id: "biz-1",
    target_date: "2026-11-24",
    timezone: "Asia/Kolkata",
    consultation_type_id: "ct-1",
    duration_minutes: 30,
    slots: [
      {
        doctor_id: "doc-1",
        doctor_name: "Dr. Meera Nair",
        consultation_type_id: "ct-1",
        starts_at: "2026-11-24T10:00:00+05:30",
        ends_at: "2026-11-24T10:30:00+05:30",
        timezone: "Asia/Kolkata",
      },
    ],
  })),
  fetchClinicAppointments: vi.fn(async () => mocks.appointments),
  createClinicAppointment: vi.fn(),
  rescheduleClinicAppointment: vi.fn(),
  cancelClinicAppointment: (...args: unknown[]) => mocks.cancelClinicAppointment(...args),
}));

describe("Stage 6 — ClinicDashboardView", () => {
  beforeEach(() => {
    mocks.fetchClinicDepartments.mockResolvedValue(mocks.departments);
    mocks.cancelClinicAppointment.mockResolvedValue({
      ...mocks.appointments[0],
      status: "cancelled",
    });
  });

  it("renders clinic KPIs, masks patient contact, and handles appointment cancellation confirmation", async () => {
    render(
      <ClinicDashboardView
        accessToken="token-123"
        organizationId="org-1"
        businessId="biz-1"
        isOwnerOrAdmin={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("CLN-1234ABCD")).toBeTruthy();
    });

    // Masks full phone number
    expect(screen.getByText(/••••8877/)).toBeTruthy();
    expect(screen.queryByText(/\+919999888877/)).toBeNull();

    // Cancel flow requires confirmation
    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.getByText("Confirm Cancel")).toBeTruthy();
    fireEvent.click(screen.getByText("Confirm Cancel"));

    await waitFor(() => {
      expect(mocks.cancelClinicAppointment).toHaveBeenCalledTimes(1);
    });
  });

  it("navigates across Doctors, Consultation Types, and Schedules & Availability tabs", async () => {
    render(
      <ClinicDashboardView
        accessToken="token-123"
        organizationId="org-1"
        businessId="biz-1"
        isOwnerOrAdmin={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("CLN-1234ABCD")).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: "Doctors" }));
    expect(screen.getByText("Dr. Meera Nair")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Consultation Types" }));
    expect(screen.getByText("Standard Consultation")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Schedules & Availability" }));
    fireEvent.click(screen.getByRole("button", { name: "Check Slots" }));

    await waitFor(() => {
      expect(screen.getByText(/2026-11-24T10:00:00/)).toBeTruthy();
    });
  });

  it("renders error banner when clinic API fails", async () => {
    mocks.fetchClinicDepartments.mockRejectedValueOnce(new Error("Clinic API unavailable"));

    render(
      <ClinicDashboardView
        accessToken="token-123"
        organizationId="org-1"
        businessId="biz-1"
        isOwnerOrAdmin={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("Clinic API unavailable");
    });
  });
});
