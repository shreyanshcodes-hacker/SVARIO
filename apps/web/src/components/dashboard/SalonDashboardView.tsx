"use client";

import React, { useCallback, useEffect, useState } from "react";
import type {
  SalonAppointment,
  SalonAvailabilitySlot,
  SalonCreateAppointmentPayload,
  SalonService,
  SalonServiceCreatePayload,
  SalonStaff,
  SalonStaffCreatePayload,
} from "@/types/salon";
import {
  assignSalonStaffServices,
  cancelSalonAppointment,
  createSalonAppointment,
  createSalonService,
  createSalonStaff,
  fetchSalonAppointments,
  fetchSalonAvailability,
  fetchSalonServices,
  fetchSalonStaff,
  rescheduleSalonAppointment,
  updateSalonService,
} from "@/lib/api";
import { SectionContentSkeleton } from "@/components/ui/LoadingSkeleton";

interface SalonDashboardViewProps {
  accessToken: string;
  organizationId: string;
  businessId: string;
  isOwnerOrAdmin: boolean;
}

type ActiveTab = "services" | "staff" | "appointments" | "availability";

export function SalonDashboardView({
  accessToken,
  organizationId,
  businessId,
  isOwnerOrAdmin,
}: SalonDashboardViewProps): React.JSX.Element {
  const [activeTab, setActiveTab] = useState<ActiveTab>("appointments");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Domain data
  const [services, setServices] = useState<SalonService[]>([]);
  const [staffList, setStaffList] = useState<SalonStaff[]>([]);
  const [appointments, setAppointments] = useState<SalonAppointment[]>([]);

  // Selected date for appointments/availability
  const [selectedDate, setSelectedDate] = useState<string>(() => {
    return new Date().toISOString().split("T")[0];
  });

  // Availability preview state
  const [availServiceId, setAvailServiceId] = useState<string>("");
  const [availSlots, setAvailSlots] = useState<SalonAvailabilitySlot[]>([]);
  const [loadingAvail, setLoadingAvail] = useState<boolean>(false);
  const [availClosedReason, setAvailClosedReason] = useState<string | null>(null);

  // New Service Form Modal state
  const [showAddService, setShowAddService] = useState<boolean>(false);
  const [newServiceName, setNewServiceName] = useState("");
  const [newServiceCategory, setNewServiceCategory] = useState("Hair");
  const [newServiceDuration, setNewServiceDuration] = useState("45");
  const [newServicePrice, setNewServicePrice] = useState("500");
  const [submittingService, setSubmittingService] = useState(false);

  // New Staff Form Modal state
  const [showAddStaff, setShowAddStaff] = useState<boolean>(false);
  const [newStaffName, setNewStaffName] = useState("");
  const [newStaffRole, setNewStaffRole] = useState("Stylist");
  const [newStaffEmail, setNewStaffEmail] = useState("");
  const [newStaffPhone, setNewStaffPhone] = useState("");
  const [submittingStaff, setSubmittingStaff] = useState(false);

  // New Appointment Modal state
  const [showBookModal, setShowBookModal] = useState<boolean>(false);
  const [bookServiceId, setBookServiceId] = useState<string>("");
  const [bookStaffId, setBookStaffId] = useState<string>("");
  const [bookStartTime, setBookStartTime] = useState<string>("10:00");
  const [bookCustomerName, setBookCustomerName] = useState<string>("");
  const [bookCustomerPhone, setBookCustomerPhone] = useState<string>("");
  const [submittingBooking, setSubmittingBooking] = useState<boolean>(false);

  // Reschedule / Cancel Modal state
  const [actionAppt, setActionAppt] = useState<SalonAppointment | null>(null);
  const [rescheduleDate, setRescheduleDate] = useState<string>("");
  const [rescheduleTime, setRescheduleTime] = useState<string>("");
  const [cancelReason, setCancelReason] = useState<string>("");

  const refreshAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [svcRes, staffRes, apptRes] = await Promise.all([
        fetchSalonServices(accessToken, organizationId, businessId),
        fetchSalonStaff(accessToken, organizationId, businessId),
        fetchSalonAppointments(accessToken, organizationId, businessId, selectedDate),
      ]);
      setServices(svcRes);
      setStaffList(staffRes);
      setAppointments(apptRes);
      if (svcRes.length > 0 && !availServiceId) {
        setAvailServiceId(svcRes[0].id);
        setBookServiceId(svcRes[0].id);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load salon data.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, organizationId, businessId, selectedDate, availServiceId]);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  // Load availability when service or date changes
  const runAvailabilityCheck = useCallback(async () => {
    if (!availServiceId || !selectedDate) return;
    setLoadingAvail(true);
    setAvailClosedReason(null);
    try {
      const res = await fetchSalonAvailability(
        accessToken,
        organizationId,
        businessId,
        availServiceId,
        selectedDate
      );
      if (res.is_business_closed) {
        setAvailClosedReason(res.closure_reason || "Salon is closed on this date.");
        setAvailSlots([]);
      } else {
        setAvailSlots(res.available_slots);
      }
    } catch (err) {
      setAvailClosedReason(
        err instanceof Error ? err.message : "Unable to compute availability."
      );
      setAvailSlots([]);
    } finally {
      setLoadingAvail(false);
    }
  }, [accessToken, organizationId, businessId, availServiceId, selectedDate]);

  useEffect(() => {
    if (activeTab === "availability" && availServiceId && selectedDate) {
      void runAvailabilityCheck();
    }
  }, [activeTab, availServiceId, selectedDate, runAvailabilityCheck]);

  // Handle service create
  const handleCreateService = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newServiceName.trim()) return;
    setSubmittingService(true);
    setError(null);
    try {
      const payload: SalonServiceCreatePayload = {
        name: newServiceName.trim(),
        category: newServiceCategory.trim() || "Hair",
        duration_minutes: parseInt(newServiceDuration, 10) || 45,
        price: parseFloat(newServicePrice) || 500,
        currency: "INR",
        is_active: true,
      };
      await createSalonService(accessToken, organizationId, businessId, payload);
      setNotice(`Service '${payload.name}' created successfully.`);
      setShowAddService(false);
      setNewServiceName("");
      await refreshAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create service.");
    } finally {
      setSubmittingService(false);
    }
  };

  // Handle staff create
  const handleCreateStaff = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStaffName.trim()) return;
    setSubmittingStaff(true);
    setError(null);
    try {
      const payload: SalonStaffCreatePayload = {
        full_name: newStaffName.trim(),
        role_designation: newStaffRole.trim() || "Stylist",
        email: newStaffEmail.trim() || undefined,
        phone: newStaffPhone.trim() || undefined,
        is_active: true,
      };
      await createSalonStaff(accessToken, organizationId, businessId, payload);
      setNotice(`Staff member '${payload.full_name}' added successfully.`);
      setShowAddStaff(false);
      setNewStaffName("");
      setNewStaffEmail("");
      setNewStaffPhone("");
      await refreshAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add staff.");
    } finally {
      setSubmittingStaff(false);
    }
  };

  // Handle staff service toggle
  const handleToggleStaffService = async (
    staffId: string,
    serviceId: string,
    currentAssigned: string[]
  ) => {
    if (!isOwnerOrAdmin) return;
    const isAssigned = currentAssigned.includes(serviceId);
    const newServiceIds = isAssigned
      ? currentAssigned.filter((id) => id !== serviceId)
      : [...currentAssigned, serviceId];
    try {
      await assignSalonStaffServices(accessToken, organizationId, businessId, staffId, newServiceIds);
      setNotice("Staff service assignment updated.");
      await refreshAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update assignments.");
    }
  };

  // Handle appointment booking
  const handleBookAppointment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bookServiceId || !bookCustomerName.trim() || !bookCustomerPhone.trim()) return;
    setSubmittingBooking(true);
    setError(null);
    try {
      const payload: SalonCreateAppointmentPayload = {
        service_id: bookServiceId,
        staff_id: bookStaffId || undefined,
        appointment_date: selectedDate,
        start_time: bookStartTime,
        customer_name: bookCustomerName.trim(),
        customer_phone: bookCustomerPhone.trim(),
        idempotency_key: `dash_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      };
      const created = await createSalonAppointment(accessToken, organizationId, businessId, payload);
      setNotice(`Appointment booked successfully! Reference: ${created.booking_reference}`);
      setShowBookModal(false);
      setBookCustomerName("");
      setBookCustomerPhone("");
      await refreshAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to book appointment.");
    } finally {
      setSubmittingBooking(false);
    }
  };

  // Handle reschedule
  const handleReschedule = async () => {
    if (!actionAppt || !rescheduleDate || !rescheduleTime) return;
    setError(null);
    try {
      await rescheduleSalonAppointment(
        accessToken,
        organizationId,
        businessId,
        actionAppt.id,
        {
          appointment_date: rescheduleDate,
          start_time: rescheduleTime,
          notes: "Rescheduled from salon dashboard",
        }
      );
      setNotice(`Appointment ${actionAppt.booking_reference} rescheduled to ${rescheduleDate} at ${rescheduleTime}.`);
      setActionAppt(null);
      await refreshAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Reschedule failed.");
    }
  };

  // Handle cancel
  const handleCancel = async () => {
    if (!actionAppt) return;
    setError(null);
    try {
      await cancelSalonAppointment(
        accessToken,
        organizationId,
        businessId,
        actionAppt.id,
        cancelReason || "Cancelled by receptionist"
      );
      setNotice(`Appointment ${actionAppt.booking_reference} was cancelled.`);
      setActionAppt(null);
      setCancelReason("");
      await refreshAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Cancellation failed.");
    }
  };

  const statusBadge = (status: SalonAppointment["status"]) => {
    switch (status) {
      case "confirmed":
        return "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
      case "rescheduled":
        return "bg-amber-500/20 text-amber-300 border-amber-500/40";
      case "cancelled":
        return "bg-rose-500/20 text-rose-300 border-rose-500/40";
      case "completed":
        return "bg-blue-500/20 text-blue-300 border-blue-500/40";
      default:
        return "bg-gray-500/20 text-gray-300 border-gray-500/40";
    }
  };

  return (
    <section className="mt-8 space-y-6">
      {/* Module Header & Summary */}
      <div className="flex flex-col gap-4 rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/90 p-6 backdrop-blur-md lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold uppercase tracking-widest text-[#7657F6]">
              Salon Operations
            </span>
            <span className="rounded-full border border-emerald-400/50 bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] text-emerald-300">
              Live
            </span>
          </div>
          <h2 className="mt-1 text-2xl font-bold text-[#F5F7FC]">
            Salon Operations & Appointment Desk
          </h2>
          <p className="mt-1 text-xs text-[#A7B0C4]">
            Manage services, stylist rosters, weekly breaks, and real-time appointment availability.
          </p>
        </div>

        {/* Quick metrics */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-4 py-2 text-center">
            <div className="text-xs text-[#A7B0C4]">Services</div>
            <div className="font-mono text-lg font-bold text-[#36C6D3]">{services.length}</div>
          </div>
          <div className="rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-4 py-2 text-center">
            <div className="text-xs text-[#A7B0C4]">Stylists</div>
            <div className="font-mono text-lg font-bold text-[#7657F6]">{staffList.length}</div>
          </div>
          <div className="rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-4 py-2 text-center">
            <div className="text-xs text-[#A7B0C4]">Bookings</div>
            <div className="font-mono text-lg font-bold text-emerald-400">{appointments.length}</div>
          </div>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/15 p-4 text-xs text-rose-200">
          <strong>Notice:</strong> {error}
        </div>
      )}
      {notice && (
        <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/15 p-4 text-xs text-emerald-200 flex items-center justify-between">
          <span>{notice}</span>
          <button
            type="button"
            onClick={() => setNotice(null)}
            className="text-xs underline hover:text-white"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Tabs bar */}
      <div className="flex flex-wrap items-center gap-2 border-b border-[#A7B0C4]/15 pb-4">
        <button
          type="button"
          onClick={() => setActiveTab("appointments")}
          className={`rounded-xl px-4 py-2 text-xs font-semibold transition ${
            activeTab === "appointments"
              ? "bg-[#7657F6] text-white shadow-[0_0_15px_rgba(118,87,246,0.4)]"
              : "border border-[#A7B0C4]/20 bg-[#171D33]/60 text-[#A7B0C4] hover:text-[#F5F7FC]"
          }`}
        >
          📅 Appointments & Calendar ({appointments.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("services")}
          className={`rounded-xl px-4 py-2 text-xs font-semibold transition ${
            activeTab === "services"
              ? "bg-[#7657F6] text-white shadow-[0_0_15px_rgba(118,87,246,0.4)]"
              : "border border-[#A7B0C4]/20 bg-[#171D33]/60 text-[#A7B0C4] hover:text-[#F5F7FC]"
          }`}
        >
          ✂️ Services Catalog ({services.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("staff")}
          className={`rounded-xl px-4 py-2 text-xs font-semibold transition ${
            activeTab === "staff"
              ? "bg-[#7657F6] text-white shadow-[0_0_15px_rgba(118,87,246,0.4)]"
              : "border border-[#A7B0C4]/20 bg-[#171D33]/60 text-[#A7B0C4] hover:text-[#F5F7FC]"
          }`}
        >
          👥 Stylists & Staff ({staffList.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("availability")}
          className={`rounded-xl px-4 py-2 text-xs font-semibold transition ${
            activeTab === "availability"
              ? "bg-[#7657F6] text-white shadow-[0_0_15px_rgba(118,87,246,0.4)]"
              : "border border-[#A7B0C4]/20 bg-[#171D33]/60 text-[#A7B0C4] hover:text-[#F5F7FC]"
          }`}
        >
          ⚡ Live Slot Availability Engine
        </button>
      </div>

      {loading && (
        <SectionContentSkeleton label="Loading salon records..." rows={4} />
      )}

      {/* TAB 1: APPOINTMENTS */}
      {!loading && activeTab === "appointments" && (
        <div className="space-y-4">
          <div className="flex flex-col gap-3 rounded-xl border border-[#A7B0C4]/15 bg-[#171D33]/70 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <label htmlFor="salon-date-filter" className="text-xs text-[#A7B0C4]">
                Filter Date:
              </label>
              <input
                id="salon-date-filter"
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="rounded-lg border border-[#A7B0C4]/25 bg-[#0B1020] px-3 py-1.5 font-mono text-xs text-[#F5F7FC]"
              />
              <button
                type="button"
                onClick={() => void refreshAll()}
                className="rounded-lg border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-1.5 text-xs text-[#A7B0C4] hover:text-[#F5F7FC]"
              >
                Refresh
              </button>
            </div>

            <button
              type="button"
              onClick={() => setShowBookModal(true)}
              className="inline-flex items-center gap-2 rounded-xl bg-[#36C6D3] px-4 py-2 text-xs font-bold text-[#0B1020] transition hover:bg-[#2eb1bc]"
            >
              + Book New Appointment
            </button>
          </div>

          {appointments.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[#A7B0C4]/20 bg-[#171D33]/40 p-8 text-center text-xs text-[#A7B0C4]">
              No appointments scheduled for {selectedDate}. Use &quot;+ Book New Appointment&quot; above to schedule one.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/80">
              <table className="w-full text-left text-xs text-[#F5F7FC]">
                <thead className="border-b border-[#A7B0C4]/15 bg-[#0B1020]/90 font-mono text-[11px] uppercase tracking-wider text-[#A7B0C4]">
                  <tr>
                    <th className="p-4">Reference</th>
                    <th className="p-4">Time</th>
                    <th className="p-4">Customer</th>
                    <th className="p-4">Service</th>
                    <th className="p-4">Stylist</th>
                    <th className="p-4">Status</th>
                    <th className="p-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#A7B0C4]/10">
                  {appointments.map((appt) => (
                    <tr key={appt.id} className="hover:bg-[#0B1020]/50 transition">
                      <td className="p-4 font-mono font-semibold text-[#36C6D3]">
                        {appt.booking_reference}
                      </td>
                      <td className="p-4 font-mono">
                        {appt.start_time} - {appt.end_time}
                      </td>
                      <td className="p-4">
                        <div className="font-semibold">{appt.customer_name}</div>
                        <div className="text-[11px] text-[#A7B0C4]">{appt.customer_phone}</div>
                      </td>
                      <td className="p-4">
                        <div>{appt.service_name}</div>
                        <div className="font-mono text-[11px] text-[#A7B0C4]">
                          {appt.service_duration_minutes} min • {appt.service_currency} {appt.service_price}
                        </div>
                      </td>
                      <td className="p-4">
                        <div className="font-medium text-[#7657F6]">{appt.staff_name}</div>
                        <div className="text-[10px] text-[#A7B0C4]">{appt.staff_role}</div>
                      </td>
                      <td className="p-4">
                        <span
                          className={`inline-block rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-semibold uppercase ${statusBadge(
                            appt.status
                          )}`}
                        >
                          {appt.status}
                        </span>
                      </td>
                      <td className="p-4 text-right">
                        {appt.status === "confirmed" || appt.status === "rescheduled" ? (
                          <div className="inline-flex gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                setActionAppt(appt);
                                setRescheduleDate(appt.appointment_date);
                                setRescheduleTime(appt.start_time);
                              }}
                              className="rounded-lg border border-amber-400/40 bg-amber-500/10 px-2 py-1 text-[11px] text-amber-300 hover:bg-amber-500/20"
                            >
                              Reschedule
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setActionAppt(appt);
                                setCancelReason("");
                              }}
                              className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-2 py-1 text-[11px] text-rose-300 hover:bg-rose-500/20"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <span className="font-mono text-[11px] text-[#A7B0C4]">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: SERVICES */}
      {!loading && activeTab === "services" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-[#A7B0C4]">
              Active salon service catalog. Inactive services are hidden from public customer booking.
            </p>
            {isOwnerOrAdmin && (
              <button
                type="button"
                onClick={() => setShowAddService(true)}
                className="rounded-xl bg-[#7657F6] px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#6546e6]"
              >
                + Add Salon Service
              </button>
            )}
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {services.map((svc) => (
              <div
                key={svc.id}
                className="flex flex-col justify-between rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/80 p-5"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded bg-[#0B1020] px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-[#36C6D3]">
                      {svc.category}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 font-mono text-[10px] ${
                        svc.is_active
                          ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                          : "bg-gray-500/20 text-gray-400 border border-gray-500/30"
                      }`}
                    >
                      {svc.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>

                  <h3 className="mt-3 text-base font-bold text-[#F5F7FC]">{svc.name}</h3>
                  {svc.description && (
                    <p className="mt-1 text-xs text-[#A7B0C4] line-clamp-2">{svc.description}</p>
                  )}
                </div>

                <div className="mt-4 border-t border-[#A7B0C4]/15 pt-3 flex items-center justify-between">
                  <div className="font-mono text-sm font-bold text-[#36C6D3]">
                    {svc.currency} {svc.price.toFixed(2)}
                  </div>
                  <div className="font-mono text-xs text-[#A7B0C4]">
                    ⏱️ {svc.duration_minutes} mins
                  </div>
                </div>

                {isOwnerOrAdmin && (
                  <div className="mt-3 pt-2 border-t border-[#A7B0C4]/10 flex justify-end">
                    <button
                      type="button"
                      onClick={async () => {
                        await updateSalonService(accessToken, organizationId, businessId, svc.id, {
                          is_active: !svc.is_active,
                        });
                        await refreshAll();
                      }}
                      className="text-[11px] text-[#A7B0C4] underline hover:text-[#F5F7FC]"
                    >
                      Toggle {svc.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 3: STAFF */}
      {!loading && activeTab === "staff" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-[#A7B0C4]">
              Stylist roster & assignments. Assign services to stylists so the AI receptionist can book them.
            </p>
            {isOwnerOrAdmin && (
              <button
                type="button"
                onClick={() => setShowAddStaff(true)}
                className="rounded-xl bg-[#7657F6] px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#6546e6]"
              >
                + Add Stylist Profile
              </button>
            )}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {staffList.map((st) => (
              <div
                key={st.id}
                className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/80 p-5 space-y-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-base font-bold text-[#F5F7FC]">{st.full_name}</h3>
                    <div className="text-xs font-medium text-[#7657F6]">{st.role_designation}</div>
                    <div className="mt-1 font-mono text-[11px] text-[#A7B0C4]">
                      {st.phone || "No phone"} • {st.email || "No email"}
                    </div>
                  </div>
                  <span
                    className={`rounded-full px-2 py-0.5 font-mono text-[10px] ${
                      st.is_active
                        ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                        : "bg-gray-500/20 text-gray-400"
                    }`}
                  >
                    {st.is_active ? "Active" : "Inactive"}
                  </span>
                </div>

                {/* Assigned Services */}
                <div>
                  <div className="text-[11px] uppercase tracking-wider font-mono text-[#A7B0C4] mb-1.5">
                    Assigned Services:
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {services.map((svc) => {
                      const isAssigned = st.assigned_service_ids.includes(svc.id);
                      return (
                        <button
                          key={svc.id}
                          type="button"
                          disabled={!isOwnerOrAdmin}
                          onClick={() =>
                            void handleToggleStaffService(st.id, svc.id, st.assigned_service_ids)
                          }
                          className={`rounded-lg px-2 py-1 text-[11px] font-mono transition ${
                            isAssigned
                              ? "bg-[#36C6D3]/20 border border-[#36C6D3]/60 text-[#36C6D3]"
                              : "bg-[#0B1020]/60 border border-[#A7B0C4]/20 text-[#A7B0C4]/60 hover:text-[#A7B0C4]"
                          } ${!isOwnerOrAdmin ? "cursor-default" : "cursor-pointer"}`}
                        >
                          {isAssigned ? "✓ " : "+ "}
                          {svc.name}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: LIVE AVAILABILITY ENGINE */}
      {!loading && activeTab === "availability" && (
        <div className="rounded-2xl border border-[#A7B0C4]/20 bg-[#171D33]/80 p-6 space-y-6">
          <div>
            <h3 className="text-lg font-bold text-[#F5F7FC]">
              Dynamic Appointment Availability Calculator
            </h3>
            <p className="text-xs text-[#A7B0C4]">
              Simulate the exact slots that the AI receptionist and customers see in real time, respecting regular hours, stylist shifts, breaks, and existing bookings.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4 border-b border-[#A7B0C4]/15 pb-4">
            <div>
              <label htmlFor="avail-service-select" className="block text-[11px] font-mono text-[#A7B0C4] mb-1">
                Target Service:
              </label>
              <select
                id="avail-service-select"
                value={availServiceId}
                onChange={(e) => setAvailServiceId(e.target.value)}
                className="rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2 text-xs text-[#F5F7FC]"
              >
                {services.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.duration_minutes} mins)
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="avail-date-input" className="block text-[11px] font-mono text-[#A7B0C4] mb-1">
                Requested Date:
              </label>
              <input
                id="avail-date-input"
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2 font-mono text-xs text-[#F5F7FC]"
              />
            </div>

            <div className="self-end">
              <button
                type="button"
                onClick={() => void runAvailabilityCheck()}
                disabled={loadingAvail}
                className="rounded-xl bg-[#36C6D3] px-4 py-2 text-xs font-bold text-[#0B1020] transition hover:bg-[#2eb1bc]"
              >
                {loadingAvail ? "Calculating..." : "Compute Available Slots"}
              </button>
            </div>
          </div>

          {loadingAvail ? (
            <div className="p-8 text-center font-mono text-xs text-[#36C6D3]">
              Computing non-conflicting time slots...
            </div>
          ) : availClosedReason ? (
            <div className="rounded-xl border border-amber-400/30 bg-amber-500/10 p-5 text-center text-xs text-amber-200">
              ⚠️ {availClosedReason}
            </div>
          ) : availSlots.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#A7B0C4]/20 p-8 text-center text-xs text-[#A7B0C4]">
              No available slots found for this service on {selectedDate}. All stylists may be booked, on break, or off duty.
            </div>
          ) : (
            <div>
              <div className="font-mono text-xs text-[#36C6D3] mb-3">
                ✓ Found {availSlots.length} available slots for {selectedDate}:
              </div>
              <div className="grid gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
                {availSlots.map((slot, idx) => (
                  <div
                    key={`${slot.staff_id}_${slot.start_time}_${idx}`}
                    className="rounded-xl border border-[#7657F6]/40 bg-[#0B1020]/80 p-3 text-center"
                  >
                    <div className="font-mono text-sm font-bold text-[#F5F7FC]">
                      {slot.start_time} - {slot.end_time}
                    </div>
                    <div className="mt-1 text-[11px] text-[#36C6D3] truncate">
                      {slot.staff_name}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* MODAL: ADD SERVICE */}
      {showAddService && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-[#A7B0C4]/25 bg-[#171D33] p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-[#F5F7FC]">Add New Salon Service</h3>
            <form onSubmit={(e) => void handleCreateService(e)} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs text-[#A7B0C4] mb-1">Service Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Haircut & Blowdry"
                  value={newServiceName}
                  onChange={(e) => setNewServiceName(e.target.value)}
                  className="w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2 text-xs text-[#F5F7FC]"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-[#A7B0C4] mb-1">Category</label>
                  <input
                    type="text"
                    value={newServiceCategory}
                    onChange={(e) => setNewServiceCategory(e.target.value)}
                    className="w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2 text-xs text-[#F5F7FC]"
                  />
                </div>
                <div>
                  <label className="block text-xs text-[#A7B0C4] mb-1">Duration (mins) *</label>
                  <input
                    type="number"
                    min="5"
                    max="480"
                    required
                    value={newServiceDuration}
                    onChange={(e) => setNewServiceDuration(e.target.value)}
                    className="w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2 text-xs text-[#F5F7FC]"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-[#A7B0C4] mb-1">Price (INR) *</label>
                <input
                  type="number"
                  min="1"
                  step="0.01"
                  required
                  value={newServicePrice}
                  onChange={(e) => setNewServicePrice(e.target.value)}
                  className="w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2 text-xs text-[#F5F7FC]"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddService(false)}
                  className="rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-4 py-2 text-xs text-[#A7B0C4]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingService}
                  className="rounded-xl bg-[#7657F6] px-4 py-2 text-xs font-semibold text-white"
                >
                  {submittingService ? "Saving..." : "Create Service"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: ADD STAFF */}
      {showAddStaff && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-[#A7B0C4]/25 bg-[#171D33] p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-[#F5F7FC]">Add New Stylist / Staff Profile</h3>
            <form onSubmit={(e) => void handleCreateStaff(e)} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs text-[#A7B0C4] mb-1">Full Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Elena Rostova"
                  value={newStaffName}
                  onChange={(e) => setNewStaffName(e.target.value)}
                  className="w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2 text-xs text-[#F5F7FC]"
                />
              </div>
              <div>
                <label className="block text-xs text-[#A7B0C4] mb-1">Designation</label>
                <input
                  type="text"
                  value={newStaffRole}
                  onChange={(e) => setNewStaffRole(e.target.value)}
                  className="w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2 text-xs text-[#F5F7FC]"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-[#A7B0C4] mb-1">Phone</label>
                  <input
                    type="tel"
                    value={newStaffPhone}
                    onChange={(e) => setNewStaffPhone(e.target.value)}
                    className="w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2 text-xs text-[#F5F7FC]"
                  />
                </div>
                <div>
                  <label className="block text-xs text-[#A7B0C4] mb-1">Email</label>
                  <input
                    type="email"
                    value={newStaffEmail}
                    onChange={(e) => setNewStaffEmail(e.target.value)}
                    className="w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2 text-xs text-[#F5F7FC]"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddStaff(false)}
                  className="rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-4 py-2 text-xs text-[#A7B0C4]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingStaff}
                  className="rounded-xl bg-[#7657F6] px-4 py-2 text-xs font-semibold text-white"
                >
                  {submittingStaff ? "Adding..." : "Add Stylist"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: BOOK APPOINTMENT */}
      {showBookModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-[#A7B0C4]/25 bg-[#171D33] p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-[#F5F7FC]">Book Salon Appointment</h3>
            <form onSubmit={(e) => void handleBookAppointment(e)} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs text-[#A7B0C4] mb-1">Service *</label>
                <select
                  required
                  value={bookServiceId}
                  onChange={(e) => setBookServiceId(e.target.value)}
                  className="w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2 text-xs text-[#F5F7FC]"
                >
                  {services.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.duration_minutes} min • {s.currency} {s.price})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-[#A7B0C4] mb-1">Stylist (Optional)</label>
                  <select
                    value={bookStaffId}
                    onChange={(e) => setBookStaffId(e.target.value)}
                    className="w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2 text-xs text-[#F5F7FC]"
                  >
                    <option value="">Auto-Assign Stylist</option>
                    {staffList.map((st) => (
                      <option key={st.id} value={st.id}>
                        {st.full_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-[#A7B0C4] mb-1">Start Time (HH:MM) *</label>
                  <input
                    type="time"
                    required
                    value={bookStartTime}
                    onChange={(e) => setBookStartTime(e.target.value)}
                    className="w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2 text-xs text-[#F5F7FC]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs text-[#A7B0C4] mb-1">Customer Full Name *</label>
                <input
                  type="text"
                  required
                  placeholder="Customer name"
                  value={bookCustomerName}
                  onChange={(e) => setBookCustomerName(e.target.value)}
                  className="w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2 text-xs text-[#F5F7FC]"
                />
              </div>

              <div>
                <label className="block text-xs text-[#A7B0C4] mb-1">Customer Phone *</label>
                <input
                  type="tel"
                  required
                  placeholder="+919876543210"
                  value={bookCustomerPhone}
                  onChange={(e) => setBookCustomerPhone(e.target.value)}
                  className="w-full rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3.5 py-2 text-xs text-[#F5F7FC]"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowBookModal(false)}
                  className="rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-4 py-2 text-xs text-[#A7B0C4]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingBooking}
                  className="rounded-xl bg-[#36C6D3] px-4 py-2 text-xs font-bold text-[#0B1020]"
                >
                  {submittingBooking ? "Booking..." : "Confirm Booking"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: RESCHEDULE OR CANCEL */}
      {actionAppt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-[#A7B0C4]/25 bg-[#171D33] p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-bold text-[#F5F7FC]">
              Manage Appointment: {actionAppt.booking_reference}
            </h3>
            <p className="text-xs text-[#A7B0C4]">
              {actionAppt.customer_name} • {actionAppt.service_name} with {actionAppt.staff_name}
            </p>

            {/* Reschedule Section */}
            <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/60 p-4 space-y-3">
              <div className="font-mono text-xs font-semibold text-amber-300">
                Reschedule to New Date / Time
              </div>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="date"
                  value={rescheduleDate}
                  onChange={(e) => setRescheduleDate(e.target.value)}
                  className="rounded-lg border border-[#A7B0C4]/25 bg-[#171D33] px-3 py-1.5 font-mono text-xs text-[#F5F7FC]"
                />
                <input
                  type="time"
                  value={rescheduleTime}
                  onChange={(e) => setRescheduleTime(e.target.value)}
                  className="rounded-lg border border-[#A7B0C4]/25 bg-[#171D33] px-3 py-1.5 font-mono text-xs text-[#F5F7FC]"
                />
              </div>
              <button
                type="button"
                onClick={() => void handleReschedule()}
                className="w-full rounded-xl bg-amber-500 px-3.5 py-2 text-xs font-bold text-black hover:bg-amber-400"
              >
                Confirm Reschedule
              </button>
            </div>

            {/* Cancel Section */}
            <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-4 space-y-3">
              <div className="font-mono text-xs font-semibold text-rose-300">
                Cancel Appointment
              </div>
              <input
                type="text"
                placeholder="Reason for cancellation..."
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                className="w-full rounded-lg border border-rose-500/30 bg-[#0B1020] px-3 py-1.5 text-xs text-[#F5F7FC]"
              />
              <button
                type="button"
                onClick={() => void handleCancel()}
                className="w-full rounded-xl bg-rose-600 px-3.5 py-2 text-xs font-bold text-white hover:bg-rose-500"
              >
                Cancel Appointment
              </button>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setActionAppt(null)}
                className="rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-4 py-2 text-xs text-[#A7B0C4]"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
