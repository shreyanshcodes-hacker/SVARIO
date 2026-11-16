import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SalonDashboardView } from "@/components/dashboard/SalonDashboardView";
import type {
  SalonAppointment,
  SalonAvailabilityResponse,
  SalonService,
  SalonStaff,
} from "@/types/salon";

const { mockServices, mockStaff, mockAppointments, mockAvailability } = vi.hoisted(() => {
  const services: SalonService[] = [
    {
      id: "svc-001",
      organization_id: "org-1",
      business_id: "biz-1",
      name: "Classic Haircut & Styling",
      description: "Wash and precision haircut",
      category: "Hair",
      price: 650,
      currency: "INR",
      duration_minutes: 45,
      is_active: true,
      created_at: "2026-11-16T10:00:00Z",
      updated_at: "2026-11-16T10:00:00Z",
    },
    {
      id: "svc-002",
      organization_id: "org-1",
      business_id: "biz-1",
      name: "Deluxe Pedicure",
      description: "Foot scrub and polish",
      category: "Nails",
      price: 450,
      currency: "INR",
      duration_minutes: 30,
      is_active: false,
      created_at: "2026-11-16T10:00:00Z",
      updated_at: "2026-11-16T10:00:00Z",
    },
  ];

  const staff: SalonStaff[] = [
    {
      id: "st-001",
      organization_id: "org-1",
      business_id: "biz-1",
      full_name: "Elena Rostova",
      role_designation: "Senior Stylist",
      email: "elena@luxehair.com",
      phone: "+919876543210",
      is_active: true,
      assigned_service_ids: ["svc-001"],
      assigned_service_names: ["Classic Haircut & Styling"],
      working_hours: [
        {
          weekday: 1,
          is_off: false,
          start_time: "09:00",
          end_time: "18:00",
        },
      ],
      breaks: [],
      created_at: "2026-11-16T10:00:00Z",
      updated_at: "2026-11-16T10:00:00Z",
    },
  ];

  const todayStr = new Date().toISOString().split("T")[0];

  const appointments: SalonAppointment[] = [
    {
      id: "appt-001",
      organization_id: "org-1",
      business_id: "biz-1",
      booking_reference: "SV-SAL-TEST001",
      service_id: "svc-001",
      service_name: "Classic Haircut & Styling",
      service_duration_minutes: 45,
      service_price: 650,
      service_currency: "INR",
      staff_id: "st-001",
      staff_name: "Elena Rostova",
      staff_role: "Senior Stylist",
      customer_name: "Priya Sharma",
      customer_phone: "+919876543211",
      appointment_date: todayStr,
      start_time: "10:00",
      end_time: "10:45",
      start_at: "2026-11-16T10:00:00Z",
      end_at: "2026-11-16T10:45:00Z",
      timezone: "Asia/Kolkata",
      status: "confirmed",
      source: "dashboard",
      created_at: "2026-11-16T09:00:00Z",
      updated_at: "2026-11-16T09:00:00Z",
    },
  ];

  const availability: SalonAvailabilityResponse = {
    organization_id: "org-1",
    business_id: "biz-1",
    service_id: "svc-001",
    service_name: "Classic Haircut & Styling",
    duration_minutes: 45,
    price: 650,
    currency: "INR",
    requested_date: todayStr,
    timezone: "Asia/Kolkata",
    is_business_closed: false,
    available_slots: [
      {
        start_time: "10:00",
        end_time: "10:45",
        start_at: "2026-11-16T10:00:00Z",
        end_at: "2026-11-16T10:45:00Z",
        staff_id: "st-001",
        staff_name: "Elena Rostova",
        staff_role: "Senior Stylist",
      },
      {
        start_time: "11:00",
        end_time: "11:45",
        start_at: "2026-11-16T11:00:00Z",
        end_at: "2026-11-16T11:45:00Z",
        staff_id: "st-001",
        staff_name: "Elena Rostova",
        staff_role: "Senior Stylist",
      },
    ],
  };

  return {
    mockServices: services,
    mockStaff: staff,
    mockAppointments: appointments,
    mockAvailability: availability,
  };
});

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    fetchSalonServices: vi.fn().mockResolvedValue(mockServices),
    createSalonService: vi.fn().mockImplementation((_, __, ___, payload) =>
      Promise.resolve({
        id: "svc-new-001",
        organization_id: "org-1",
        business_id: "biz-1",
        ...payload,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
    ),
    updateSalonService: vi.fn().mockResolvedValue({ ...mockServices[0], is_active: false }),
    fetchSalonStaff: vi.fn().mockResolvedValue(mockStaff),
    createSalonStaff: vi.fn().mockImplementation((_, __, ___, payload) =>
      Promise.resolve({
        id: "st-new-002",
        organization_id: "org-1",
        business_id: "biz-1",
        ...payload,
        assigned_service_ids: [],
        assigned_service_names: [],
        working_hours: [],
        breaks: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
    ),
    assignSalonStaffServices: vi.fn().mockResolvedValue(mockStaff[0]),
    fetchSalonAppointments: vi.fn().mockResolvedValue(mockAppointments),
    createSalonAppointment: vi.fn().mockResolvedValue({
      ...mockAppointments[0],
      id: "appt-002",
      booking_reference: "SV-SAL-NEW002",
    }),
    rescheduleSalonAppointment: vi.fn().mockResolvedValue({
      ...mockAppointments[0],
      status: "rescheduled",
      start_time: "14:00",
      end_time: "14:45",
    }),
    cancelSalonAppointment: vi.fn().mockResolvedValue({
      ...mockAppointments[0],
      status: "cancelled",
      cancellation_reason: "Client conflict",
    }),
    fetchSalonAvailability: vi.fn().mockResolvedValue(mockAvailability),
  };
});

describe("Stage 5: SalonDashboardView Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders salon summary metrics and appointment calendar list", async () => {
    render(
      <SalonDashboardView
        accessToken="mock-token-xyz"
        organizationId="org-1"
        businessId="biz-1"
        isOwnerOrAdmin={true}
      />
    );

    // Verify header and metrics
    expect(screen.getByText("Stage 5 Salon Workflow Module")).toBeTruthy();
    expect(screen.getByText("Salon Operations & Appointment Desk")).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByText("SV-SAL-TEST001")).toBeTruthy();
      expect(screen.getByText("Priya Sharma")).toBeTruthy();
      expect(screen.getByText("Elena Rostova")).toBeTruthy();
    });
  });

  it("switches to Services tab and displays active and inactive services", async () => {
    render(
      <SalonDashboardView
        accessToken="mock-token-xyz"
        organizationId="org-1"
        businessId="biz-1"
        isOwnerOrAdmin={true}
      />
    );

    const servicesTab = screen.getByRole("button", { name: /Services Catalog/i });
    fireEvent.click(servicesTab);

    await waitFor(() => {
      expect(screen.getByText("Classic Haircut & Styling")).toBeTruthy();
      expect(screen.getByText("Deluxe Pedicure")).toBeTruthy();
      expect(screen.getByText("Active")).toBeTruthy();
      expect(screen.getByText("Inactive")).toBeTruthy();
    });
  });

  it("switches to Stylists tab and displays staff roster with assigned services", async () => {
    render(
      <SalonDashboardView
        accessToken="mock-token-xyz"
        organizationId="org-1"
        businessId="biz-1"
        isOwnerOrAdmin={true}
      />
    );

    const staffTab = screen.getByRole("button", { name: /Stylists & Staff/i });
    fireEvent.click(staffTab);

    await waitFor(() => {
      expect(screen.getByText("Elena Rostova")).toBeTruthy();
      expect(screen.getByText("Senior Stylist")).toBeTruthy();
      expect(screen.getByText("+919876543210 • elena@luxehair.com")).toBeTruthy();
    });
  });

  it("switches to Availability tab and computes non-conflicting slots", async () => {
    render(
      <SalonDashboardView
        accessToken="mock-token-xyz"
        organizationId="org-1"
        businessId="biz-1"
        isOwnerOrAdmin={true}
      />
    );

    const availTab = screen.getByRole("button", { name: /Live Slot Availability Engine/i });
    fireEvent.click(availTab);

    await waitFor(() => {
      expect(screen.getByText("Dynamic Appointment Availability Calculator")).toBeTruthy();
      expect(screen.getByText(/Found 2 available slots/i)).toBeTruthy();
      expect(screen.getByText("10:00 - 10:45")).toBeTruthy();
      expect(screen.getByText("11:00 - 11:45")).toBeTruthy();
    });
  });
});
