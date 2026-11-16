/**
 * Stage 5: Salon Workflow Module TypeScript Definitions.
 */

export type SalonAppointmentStatus =
  | "confirmed"
  | "rescheduled"
  | "cancelled"
  | "completed"
  | "no_show";

export type SalonAppointmentSource = "dashboard" | "voice_agent" | "api";

export interface SalonService {
  id: string;
  organization_id: string;
  business_id: string;
  name: string;
  description?: string | null;
  category: string;
  price: number;
  currency: string;
  duration_minutes: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SalonServiceCreatePayload {
  name: string;
  description?: string;
  category?: string;
  price: number;
  currency?: string;
  duration_minutes: number;
  is_active?: boolean;
}

export interface SalonStaffWorkingHours {
  weekday: number;
  is_off: boolean;
  start_time?: string | null;
  end_time?: string | null;
}

export interface SalonStaffBreak {
  id: string;
  organization_id: string;
  business_id: string;
  staff_id: string;
  weekday?: number | null;
  specific_date?: string | null;
  label: string;
  start_time: string;
  end_time: string;
  created_at: string;
}

export interface SalonStaff {
  id: string;
  organization_id: string;
  business_id: string;
  full_name: string;
  role_designation: string;
  email?: string | null;
  phone?: string | null;
  bio?: string | null;
  is_active: boolean;
  assigned_service_ids: string[];
  assigned_service_names: string[];
  working_hours: SalonStaffWorkingHours[];
  breaks: SalonStaffBreak[];
  created_at: string;
  updated_at: string;
}

export interface SalonStaffCreatePayload {
  full_name: string;
  role_designation?: string;
  email?: string;
  phone?: string;
  bio?: string;
  is_active?: boolean;
  assigned_service_ids?: string[];
}

export interface SalonHoliday {
  id: string;
  organization_id: string;
  business_id: string;
  staff_id?: string | null;
  staff_name?: string | null;
  holiday_date: string;
  title: string;
  is_closed_all_day: boolean;
  start_time?: string | null;
  end_time?: string | null;
  created_at: string;
}

export interface SalonAvailabilitySlot {
  start_time: string;
  end_time: string;
  start_at: string;
  end_at: string;
  staff_id: string;
  staff_name: string;
  staff_role: string;
}

export interface SalonAvailabilityResponse {
  organization_id: string;
  business_id: string;
  service_id: string;
  service_name: string;
  duration_minutes: number;
  price: number;
  currency: string;
  requested_date: string;
  timezone: string;
  is_business_closed: boolean;
  closure_reason?: string | null;
  available_slots: SalonAvailabilitySlot[];
}

export interface SalonAppointment {
  id: string;
  organization_id: string;
  business_id: string;
  booking_reference: string;
  idempotency_key?: string | null;
  service_id: string;
  service_name: string;
  service_duration_minutes: number;
  service_price: number;
  service_currency: string;
  staff_id: string;
  staff_name: string;
  staff_role: string;
  customer_name: string;
  customer_phone: string;
  customer_email?: string | null;
  notes?: string | null;
  appointment_date: string;
  start_time: string;
  end_time: string;
  start_at: string;
  end_at: string;
  timezone: string;
  status: SalonAppointmentStatus;
  source: SalonAppointmentSource;
  cancelled_at?: string | null;
  cancellation_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SalonCreateAppointmentPayload {
  service_id: string;
  staff_id?: string;
  appointment_date: string;
  start_time: string;
  customer_name: string;
  customer_phone: string;
  customer_email?: string;
  notes?: string;
  idempotency_key?: string;
}
