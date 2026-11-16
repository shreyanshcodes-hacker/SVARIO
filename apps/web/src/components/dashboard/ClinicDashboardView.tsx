"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  cancelClinicAppointment,
  createClinicAppointment,
  createClinicConsultationType,
  createClinicDepartment,
  createClinicDoctor,
  createClinicSpeciality,
  fetchClinicAppointments,
  fetchClinicAvailability,
  fetchClinicConsultationTypes,
  fetchClinicDepartments,
  fetchClinicDoctors,
  fetchClinicSpecialities,
  updateClinicDepartment,
  updateClinicDoctor,
  upsertClinicDoctorWorkingHours,
} from "@/lib/api";
import type {
  ClinicAppointment,
  ClinicAvailableSlot,
  ClinicConsultationType,
  ClinicDepartment,
  ClinicDoctor,
  ClinicSpeciality,
  ConsultationMode,
} from "@/types/clinic";

interface ClinicDashboardViewProps {
  accessToken: string;
  organizationId: string;
  businessId: string;
  isOwnerOrAdmin: boolean;
}

type ClinicTab =
  | "appointments"
  | "doctors"
  | "consultations"
  | "departments"
  | "availability";

function maskContact(contact: string): string {
  const trimmed = contact.trim();
  if (trimmed.length <= 4) return "****";
  return `••••${trimmed.slice(-4)}`;
}

export function ClinicDashboardView({
  accessToken,
  organizationId,
  businessId,
  isOwnerOrAdmin,
}: ClinicDashboardViewProps) {
  const [activeTab, setActiveTab] = useState<ClinicTab>("appointments");
  const [departments, setDepartments] = useState<ClinicDepartment[]>([]);
  const [specialities, setSpecialities] = useState<ClinicSpeciality[]>([]);
  const [consultationTypes, setConsultationTypes] = useState<ClinicConsultationType[]>([]);
  const [doctors, setDoctors] = useState<ClinicDoctor[]>([]);
  const [appointments, setAppointments] = useState<ClinicAppointment[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Filters
  const [filterDate, setFilterDate] = useState<string>("");
  const [filterDoctorId, setFilterDoctorId] = useState<string>("");
  const [confirmCancelId, setConfirmCancelId] = useState<string | null>(null);

  // Quick-create forms
  const [newDeptName, setNewDeptName] = useState("");
  const [newSpecName, setNewSpecName] = useState("");
  const [newDocName, setNewDocName] = useState("");
  const [newDocTitle, setNewDocTitle] = useState("");
  const [newCtName, setNewCtName] = useState("");
  const [newCtDuration, setNewCtDuration] = useState("30");
  const [newCtMode, setNewCtMode] = useState<ConsultationMode>("in_person");
  const [newCtFee, setNewCtFee] = useState("");

  // Schedule & Availability
  const [availDate, setAvailDate] = useState<string>(
    new Date().toISOString().slice(0, 10)
  );
  const [availCtId, setAvailCtId] = useState<string>("");
  const [availDocId, setAvailDocId] = useState<string>("");
  const [availSlots, setAvailSlots] = useState<ClinicAvailableSlot[]>([]);
  const [availTimezone, setAvailTimezone] = useState<string>("UTC");
  const [scheduleDocId, setScheduleDocId] = useState<string>("");
  const [scheduleDay, setScheduleDay] = useState<string>("1");
  const [scheduleStart, setScheduleStart] = useState<string>("09:00:00");
  const [scheduleEnd, setScheduleEnd] = useState<string>("17:00:00");

  // Quick Booking from Availability
  const [bookingPatientName, setBookingPatientName] = useState("");
  const [bookingPatientContact, setBookingPatientContact] = useState("");

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const [depts, specs, cts, docs, appts] = await Promise.all([
        fetchClinicDepartments(accessToken, organizationId, businessId),
        fetchClinicSpecialities(accessToken, organizationId, businessId),
        fetchClinicConsultationTypes(accessToken, organizationId, businessId),
        fetchClinicDoctors(accessToken, organizationId, businessId),
        fetchClinicAppointments(accessToken, organizationId, businessId, {
          target_date: filterDate || undefined,
          doctor_id: filterDoctorId || undefined,
        }),
      ]);
      setDepartments(depts);
      setSpecialities(specs);
      setConsultationTypes(cts);
      setDoctors(docs);
      setAppointments(appts);
      if (cts.length > 0 && !availCtId) {
        setAvailCtId(cts[0].id);
      }
      if (docs.length > 0 && !scheduleDocId) {
        setScheduleDocId(docs[0].id);
      }
    } catch (err) {
      setErrorMsg(
        err instanceof Error ? err.message : "Failed to load clinic operations data."
      );
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, organizationId, businessId, filterDate, filterDoctorId, availCtId, scheduleDocId]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const todayIso = new Date().toISOString().slice(0, 10);
  const activeDeptsCount = departments.filter((d) => d.is_active).length;
  const todaysApptsCount = appointments.filter(
    (a) => a.starts_at.slice(0, 10) === todayIso && a.status !== "cancelled"
  ).length;
  const upcomingApptsCount = appointments.filter(
    (a) => a.starts_at >= new Date().toISOString() && a.status !== "cancelled"
  ).length;
  const cancelledApptsCount = appointments.filter(
    (a) => a.status === "cancelled"
  ).length;

  const handleCreateDept = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDeptName.trim()) return;
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await createClinicDepartment(accessToken, organizationId, businessId, {
        name: newDeptName.trim(),
      });
      setNewDeptName("");
      setSuccessMsg("Department created.");
      await loadAll();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Could not create department.");
    }
  };

  const handleCreateSpec = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSpecName.trim()) return;
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await createClinicSpeciality(accessToken, organizationId, businessId, {
        name: newSpecName.trim(),
      });
      setNewSpecName("");
      setSuccessMsg("Speciality created.");
      await loadAll();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Could not create speciality.");
    }
  };

  const handleCreateDoc = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDocName.trim()) return;
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await createClinicDoctor(accessToken, organizationId, businessId, {
        display_name: newDocName.trim(),
        professional_title: newDocTitle.trim() || null,
        consultation_type_ids: consultationTypes.map((c) => c.id),
        department_ids: departments.slice(0, 1).map((d) => d.id),
      });
      setNewDocName("");
      setNewDocTitle("");
      setSuccessMsg("Doctor profile created.");
      await loadAll();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Could not create doctor.");
    }
  };

  const handleCreateCt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCtName.trim()) return;
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await createClinicConsultationType(accessToken, organizationId, businessId, {
        name: newCtName.trim(),
        duration_minutes: Number(newCtDuration) || 30,
        consultation_mode: newCtMode,
        fee_amount: newCtFee ? Number(newCtFee) : null,
        currency_code: "INR",
      });
      setNewCtName("");
      setNewCtFee("");
      setSuccessMsg("Consultation type created.");
      await loadAll();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Could not create consultation type.");
    }
  };

  const handleCheckAvailability = async () => {
    if (!availCtId || !availDate) return;
    setErrorMsg(null);
    try {
      const resp = await fetchClinicAvailability(accessToken, organizationId, businessId, {
        consultation_type_id: availCtId,
        target_date: availDate,
        doctor_id: availDocId || undefined,
      });
      setAvailSlots(resp.slots);
      setAvailTimezone(resp.timezone);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to fetch availability.");
    }
  };

  const handleSaveSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scheduleDocId) return;
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await upsertClinicDoctorWorkingHours(
        accessToken,
        organizationId,
        businessId,
        scheduleDocId,
        [
          {
            day_of_week: Number(scheduleDay),
            start_time: scheduleStart,
            end_time: scheduleEnd,
            is_active: true,
          },
        ]
      );
      setSuccessMsg("Doctor working hours updated.");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to save working hours.");
    }
  };

  const handleBookSlot = async (slot: ClinicAvailableSlot) => {
    if (!bookingPatientName.trim() || !bookingPatientContact.trim()) {
      setErrorMsg("Enter patient display name and minimum contact before booking.");
      return;
    }
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const created = await createClinicAppointment(
        accessToken,
        organizationId,
        businessId,
        {
          doctor_id: slot.doctor_id,
          consultation_type_id: slot.consultation_type_id,
          patient_display_name: bookingPatientName.trim(),
          patient_contact: bookingPatientContact.trim(),
          starts_at: slot.starts_at,
        }
      );
      setSuccessMsg(`Booked ${created.booking_reference} for ${created.patient_display_name}.`);
      setBookingPatientName("");
      setBookingPatientContact("");
      await Promise.all([loadAll(), handleCheckAvailability()]);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to create appointment.");
    }
  };

  const handleCancelAppointment = async (appointmentId: string) => {
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await cancelClinicAppointment(
        accessToken,
        organizationId,
        businessId,
        appointmentId,
        "Cancelled from clinic dashboard"
      );
      setConfirmCancelId(null);
      setSuccessMsg("Appointment cancelled.");
      await loadAll();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to cancel appointment.");
    }
  };

  return (
    <section
      aria-label="Clinic Operations Hub"
      className="mt-8 rounded-2xl border border-[#36C6D3]/25 bg-[#171D33]/90 p-6 shadow-xl"
    >
      <div className="flex flex-col gap-2 border-b border-[#A7B0C4]/15 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <span className="font-mono text-[10px] uppercase tracking-widest text-[#36C6D3]">
            Stage 6 — Clinic Workflow Module
          </span>
          <h2 className="mt-1 text-xl font-bold text-[#F5F7FC]">
            Clinic Operations & Appointment Desk
          </h2>
          <p className="text-xs text-[#A7B0C4]">
            Administrative scheduling only. No clinical records, symptoms, or diagnoses stored.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadAll()}
          className="self-start rounded-xl border border-[#A7B0C4]/25 bg-[#0B1020] px-3 py-1.5 text-xs font-semibold text-[#F5F7FC] transition hover:border-[#36C6D3]/60"
        >
          Refresh Clinic Data
        </button>
      </div>

      {/* Overview KPI Strip */}
      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/70 p-3">
          <div className="font-mono text-[10px] uppercase text-[#A7B0C4]">Doctors</div>
          <div className="mt-1 text-lg font-bold text-[#F5F7FC]">{doctors.length}</div>
        </div>
        <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/70 p-3">
          <div className="font-mono text-[10px] uppercase text-[#A7B0C4]">Active Depts</div>
          <div className="mt-1 text-lg font-bold text-[#36C6D3]">{activeDeptsCount}</div>
        </div>
        <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/70 p-3">
          <div className="font-mono text-[10px] uppercase text-[#A7B0C4]">Consult Types</div>
          <div className="mt-1 text-lg font-bold text-[#F5F7FC]">
            {consultationTypes.length}
          </div>
        </div>
        <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/70 p-3">
          <div className="font-mono text-[10px] uppercase text-[#A7B0C4]">Today</div>
          <div className="mt-1 text-lg font-bold text-[#36C6D3]">{todaysApptsCount}</div>
        </div>
        <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/70 p-3">
          <div className="font-mono text-[10px] uppercase text-[#A7B0C4]">Upcoming</div>
          <div className="mt-1 text-lg font-bold text-[#7657F6]">{upcomingApptsCount}</div>
        </div>
        <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/70 p-3">
          <div className="font-mono text-[10px] uppercase text-[#A7B0C4]">Cancelled</div>
          <div className="mt-1 text-lg font-bold text-[#A7B0C4]">{cancelledApptsCount}</div>
        </div>
      </div>

      {/* Status Banners */}
      {errorMsg && (
        <div
          role="alert"
          className="mt-4 rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-2.5 text-xs text-rose-200"
        >
          {errorMsg}
        </div>
      )}
      {successMsg && (
        <div
          role="status"
          className="mt-4 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-2.5 text-xs text-emerald-200"
        >
          {successMsg}
        </div>
      )}

      {/* Tabs */}
      <div className="mt-5 flex flex-wrap gap-2 border-b border-[#A7B0C4]/15 pb-3">
        {(
          [
            ["appointments", "Appointments"],
            ["doctors", "Doctors"],
            ["consultations", "Consultation Types"],
            ["departments", "Departments & Specialities"],
            ["availability", "Schedules & Availability"],
          ] as const
        ).map(([tabId, label]) => (
          <button
            key={tabId}
            type="button"
            onClick={() => setActiveTab(tabId)}
            className={`rounded-xl px-3.5 py-1.5 text-xs font-semibold transition ${
              activeTab === tabId
                ? "bg-[#36C6D3] text-[#0B1020]"
                : "border border-[#A7B0C4]/20 bg-[#0B1020] text-[#A7B0C4] hover:text-[#F5F7FC]"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="py-8 text-center font-mono text-xs text-[#A7B0C4]">
          Loading clinic data...
        </div>
      ) : (
        <div className="mt-5">
          {/* Appointments Tab */}
          {activeTab === "appointments" && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-3">
                <input
                  type="date"
                  aria-label="Filter by date"
                  value={filterDate}
                  onChange={(e) => setFilterDate(e.target.value)}
                  className="rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-1.5 text-xs text-[#F5F7FC]"
                />
                <select
                  aria-label="Filter by doctor"
                  value={filterDoctorId}
                  onChange={(e) => setFilterDoctorId(e.target.value)}
                  className="rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-1.5 text-xs text-[#F5F7FC]"
                >
                  <option value="">All Doctors</option>
                  {doctors.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.display_name}
                    </option>
                  ))}
                </select>
              </div>

              {appointments.length === 0 ? (
                <div className="rounded-xl border border-dashed border-[#A7B0C4]/20 p-6 text-center text-xs text-[#A7B0C4]">
                  No clinic appointments match the current filter.
                </div>
              ) : (
                <div className="space-y-2">
                  {appointments.map((appt) => (
                    <div
                      key={appt.id}
                      className="flex flex-col justify-between gap-3 rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/70 p-4 sm:flex-row sm:items-center"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-[#36C6D3]">
                            {appt.booking_reference}
                          </span>
                          <span className="rounded-md bg-[#171D33] px-2 py-0.5 font-mono text-[10px] uppercase text-[#F5F7FC]">
                            {appt.status}
                          </span>
                        </div>
                        <div className="mt-1 text-sm font-semibold text-[#F5F7FC]">
                          {appt.patient_display_name}{" "}
                          <span className="font-mono text-xs text-[#A7B0C4]">
                            ({maskContact(appt.patient_contact)})
                          </span>
                        </div>
                        <div className="mt-0.5 text-xs text-[#A7B0C4]">
                          {appt.doctor_name ?? "Doctor"} •{" "}
                          {appt.consultation_type_name ?? "Consultation"} •{" "}
                          {appt.starts_at}
                        </div>
                      </div>

                      {appt.status !== "cancelled" && (
                        <div className="flex items-center gap-2">
                          {confirmCancelId === appt.id ? (
                            <>
                              <button
                                type="button"
                                onClick={() => void handleCancelAppointment(appt.id)}
                                className="rounded-lg bg-rose-600 px-3 py-1 text-xs font-semibold text-white"
                              >
                                Confirm Cancel
                              </button>
                              <button
                                type="button"
                                onClick={() => setConfirmCancelId(null)}
                                className="rounded-lg border border-[#A7B0C4]/25 px-3 py-1 text-xs text-[#A7B0C4]"
                              >
                                Keep
                              </button>
                            </>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setConfirmCancelId(appt.id)}
                              className="rounded-lg border border-rose-500/40 px-3 py-1 text-xs font-semibold text-rose-300 hover:bg-rose-500/15"
                            >
                              Cancel
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Doctors Tab */}
          {activeTab === "doctors" && (
            <div className="space-y-4">
              {isOwnerOrAdmin && (
                <form onSubmit={handleCreateDoc} className="flex flex-wrap gap-2">
                  <input
                    type="text"
                    placeholder="Doctor display name (e.g. Dr. Meera Nair)"
                    value={newDocName}
                    onChange={(e) => setNewDocName(e.target.value)}
                    className="min-w-[220px] flex-1 rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                  />
                  <input
                    type="text"
                    placeholder="Title (e.g. MD, General Physician)"
                    value={newDocTitle}
                    onChange={(e) => setNewDocTitle(e.target.value)}
                    className="min-w-[180px] rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                  />
                  <button
                    type="submit"
                    className="rounded-xl bg-[#7657F6] px-4 py-2 text-xs font-semibold text-white"
                  >
                    Add Doctor
                  </button>
                </form>
              )}

              <div className="grid gap-3 md:grid-cols-2">
                {doctors.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center justify-between rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/70 p-4"
                  >
                    <div>
                      <div className="text-sm font-semibold text-[#F5F7FC]">
                        {doc.display_name}
                      </div>
                      <div className="text-xs text-[#A7B0C4]">
                        {doc.professional_title || "Clinic Practitioner"} • Languages:{" "}
                        {doc.languages.join(", ")}
                      </div>
                    </div>
                    {isOwnerOrAdmin && (
                      <button
                        type="button"
                        onClick={async () => {
                          await updateClinicDoctor(
                            accessToken,
                            organizationId,
                            businessId,
                            doc.id,
                            { is_active: !doc.is_active }
                          );
                          await loadAll();
                        }}
                        className={`rounded-lg px-2.5 py-1 text-[11px] font-semibold ${
                          doc.is_active
                            ? "bg-emerald-500/20 text-emerald-300"
                            : "bg-slate-700/40 text-slate-300"
                        }`}
                      >
                        {doc.is_active ? "Active" : "Inactive"}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Consultation Types Tab */}
          {activeTab === "consultations" && (
            <div className="space-y-4">
              {isOwnerOrAdmin && (
                <form onSubmit={handleCreateCt} className="flex flex-wrap gap-2">
                  <input
                    type="text"
                    placeholder="Consultation name (e.g. Standard Consultation)"
                    value={newCtName}
                    onChange={(e) => setNewCtName(e.target.value)}
                    className="min-w-[200px] flex-1 rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                  />
                  <input
                    type="number"
                    min={5}
                    max={240}
                    value={newCtDuration}
                    onChange={(e) => setNewCtDuration(e.target.value)}
                    className="w-24 rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                  />
                  <select
                    value={newCtMode}
                    onChange={(e) => setNewCtMode(e.target.value as ConsultationMode)}
                    className="rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                  >
                    <option value="in_person">In-Person</option>
                    <option value="online">Online</option>
                  </select>
                  <input
                    type="number"
                    placeholder="Fee (optional)"
                    value={newCtFee}
                    onChange={(e) => setNewCtFee(e.target.value)}
                    className="w-28 rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                  />
                  <button
                    type="submit"
                    className="rounded-xl bg-[#7657F6] px-4 py-2 text-xs font-semibold text-white"
                  >
                    Add Consultation Type
                  </button>
                </form>
              )}
              <div className="grid gap-3 md:grid-cols-2">
                {consultationTypes.map((ct) => (
                  <div
                    key={ct.id}
                    className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/70 p-4"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-[#F5F7FC]">
                        {ct.name}
                      </span>
                      <span className="font-mono text-xs text-[#36C6D3]">
                        {ct.duration_minutes} min • {ct.consultation_mode}
                      </span>
                    </div>
                    {ct.fee_amount !== null && (
                      <div className="mt-1 text-xs text-[#A7B0C4]">
                        Fee: {ct.currency_code ?? "INR"} {ct.fee_amount}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Departments & Specialities Tab */}
          {activeTab === "departments" && (
            <div className="grid gap-6 md:grid-cols-2">
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-[#F5F7FC]">Departments</h3>
                {isOwnerOrAdmin && (
                  <form onSubmit={handleCreateDept} className="flex gap-2">
                    <input
                      type="text"
                      placeholder="New department name"
                      value={newDeptName}
                      onChange={(e) => setNewDeptName(e.target.value)}
                      className="flex-1 rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                    />
                    <button
                      type="submit"
                      className="rounded-xl bg-[#7657F6] px-3 py-2 text-xs font-semibold text-white"
                    >
                      Add
                    </button>
                  </form>
                )}
                {departments.map((d) => (
                  <div
                    key={d.id}
                    className="flex items-center justify-between rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/70 px-3 py-2 text-xs"
                  >
                    <span className="text-[#F5F7FC]">{d.name}</span>
                    {isOwnerOrAdmin && (
                      <button
                        type="button"
                        onClick={async () => {
                          await updateClinicDepartment(
                            accessToken,
                            organizationId,
                            businessId,
                            d.id,
                            { is_active: !d.is_active }
                          );
                          await loadAll();
                        }}
                        className="font-mono text-[10px] text-[#36C6D3]"
                      >
                        {d.is_active ? "Active" : "Inactive"}
                      </button>
                    )}
                  </div>
                ))}
              </div>

              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-[#F5F7FC]">Specialities</h3>
                {isOwnerOrAdmin && (
                  <form onSubmit={handleCreateSpec} className="flex gap-2">
                    <input
                      type="text"
                      placeholder="New speciality name"
                      value={newSpecName}
                      onChange={(e) => setNewSpecName(e.target.value)}
                      className="flex-1 rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-2 text-xs text-[#F5F7FC]"
                    />
                    <button
                      type="submit"
                      className="rounded-xl bg-[#7657F6] px-3 py-2 text-xs font-semibold text-white"
                    >
                      Add
                    </button>
                  </form>
                )}
                {specialities.map((s) => (
                  <div
                    key={s.id}
                    className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/70 px-3 py-2 text-xs text-[#F5F7FC]"
                  >
                    {s.name}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Schedules & Availability Tab */}
          {activeTab === "availability" && (
            <div className="space-y-6">
              {isOwnerOrAdmin && (
                <form
                  onSubmit={handleSaveSchedule}
                  className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/60 p-4"
                >
                  <div className="mb-2 text-xs font-semibold text-[#F5F7FC]">
                    Set Doctor Working Hours
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <select
                      value={scheduleDocId}
                      onChange={(e) => setScheduleDocId(e.target.value)}
                      className="rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-1.5 text-xs text-[#F5F7FC]"
                    >
                      {doctors.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.display_name}
                        </option>
                      ))}
                    </select>
                    <select
                      value={scheduleDay}
                      onChange={(e) => setScheduleDay(e.target.value)}
                      className="rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-1.5 text-xs text-[#F5F7FC]"
                    >
                      <option value="0">Sunday</option>
                      <option value="1">Monday</option>
                      <option value="2">Tuesday</option>
                      <option value="3">Wednesday</option>
                      <option value="4">Thursday</option>
                      <option value="5">Friday</option>
                      <option value="6">Saturday</option>
                    </select>
                    <input
                      type="text"
                      value={scheduleStart}
                      onChange={(e) => setScheduleStart(e.target.value)}
                      className="w-24 rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-1.5 text-xs text-[#F5F7FC]"
                    />
                    <input
                      type="text"
                      value={scheduleEnd}
                      onChange={(e) => setScheduleEnd(e.target.value)}
                      className="w-24 rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-1.5 text-xs text-[#F5F7FC]"
                    />
                    <button
                      type="submit"
                      className="rounded-xl bg-[#7657F6] px-4 py-1.5 text-xs font-semibold text-white"
                    >
                      Save Shift
                    </button>
                  </div>
                </form>
              )}

              <div className="rounded-xl border border-[#A7B0C4]/15 bg-[#0B1020]/60 p-4 space-y-3">
                <div className="text-xs font-semibold text-[#F5F7FC]">
                  Live Clinic Slot Availability & Quick Booking
                </div>
                <div className="flex flex-wrap gap-2">
                  <select
                    value={availCtId}
                    onChange={(e) => setAvailCtId(e.target.value)}
                    className="rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-1.5 text-xs text-[#F5F7FC]"
                  >
                    {consultationTypes.map((ct) => (
                      <option key={ct.id} value={ct.id}>
                        {ct.name} ({ct.duration_minutes}m)
                      </option>
                    ))}
                  </select>
                  <select
                    value={availDocId}
                    onChange={(e) => setAvailDocId(e.target.value)}
                    className="rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-1.5 text-xs text-[#F5F7FC]"
                  >
                    <option value="">Any Eligible Doctor</option>
                    {doctors.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.display_name}
                      </option>
                    ))}
                  </select>
                  <input
                    type="date"
                    value={availDate}
                    onChange={(e) => setAvailDate(e.target.value)}
                    className="rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-1.5 text-xs text-[#F5F7FC]"
                  />
                  <button
                    type="button"
                    onClick={() => void handleCheckAvailability()}
                    className="rounded-xl bg-[#36C6D3] px-4 py-1.5 text-xs font-semibold text-[#0B1020]"
                  >
                    Check Slots
                  </button>
                </div>

                <div className="flex flex-wrap gap-2">
                  <input
                    type="text"
                    placeholder="Patient display name"
                    value={bookingPatientName}
                    onChange={(e) => setBookingPatientName(e.target.value)}
                    className="rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-1.5 text-xs text-[#F5F7FC]"
                  />
                  <input
                    type="text"
                    placeholder="Patient contact (phone/email)"
                    value={bookingPatientContact}
                    onChange={(e) => setBookingPatientContact(e.target.value)}
                    className="rounded-xl border border-[#A7B0C4]/20 bg-[#0B1020] px-3 py-1.5 text-xs text-[#F5F7FC]"
                  />
                </div>

                {availSlots.length > 0 && (
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {availSlots.map((slot) => (
                      <button
                        key={`${slot.doctor_id}-${slot.starts_at}`}
                        type="button"
                        onClick={() => void handleBookSlot(slot)}
                        className="rounded-xl border border-[#36C6D3]/30 bg-[#171D33] p-2.5 text-left text-xs transition hover:border-[#36C6D3]"
                      >
                        <div className="font-semibold text-[#F5F7FC]">
                          {slot.doctor_name}
                        </div>
                        <div className="font-mono text-[11px] text-[#36C6D3]">
                          {slot.starts_at} ({availTimezone})
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
