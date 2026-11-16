export type ConsultationMode = "in_person" | "online";

export type ClinicAppointmentStatus =
  | "confirmed"
  | "rescheduled"
  | "cancelled"
  | "completed"
  | "no_show";

export interface ClinicDepartment {
  id: string;
  organization_id: string;
  business_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ClinicSpeciality {
  id: string;
  organization_id: string;
  business_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ClinicConsultationType {
  id: string;
  organization_id: string;
  business_id: string;
  name: string;
  description: string | null;
  duration_minutes: number;
  consultation_mode: ConsultationMode;
  fee_amount: number | string | null;
  currency_code: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ClinicDoctor {
  id: string;
  organization_id: string;
  business_id: string;
  display_name: string;
  professional_title: string | null;
  public_bio: string | null;
  languages: string[];
  is_active: boolean;
  department_ids: string[];
  speciality_ids: string[];
  consultation_type_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface DoctorWorkingHours {
  id: string;
  organization_id: string;
  business_id: string;
  doctor_id: string;
  day_of_week: number;
  start_time: string | null;
  end_time: string | null;
  is_active: boolean;
}

export interface ClinicAvailableSlot {
  doctor_id: string;
  doctor_name: string;
  consultation_type_id: string;
  starts_at: string;
  ends_at: string;
  timezone: string;
}

export interface ClinicAvailabilityResponse {
  organization_id: string;
  business_id: string;
  target_date: string;
  timezone: string;
  consultation_type_id: string;
  duration_minutes: number;
  slots: ClinicAvailableSlot[];
}

export interface ClinicAppointment {
  id: string;
  organization_id: string;
  business_id: string;
  booking_reference: string;
  doctor_id: string;
  doctor_name: string | null;
  consultation_type_id: string;
  consultation_type_name: string | null;
  department_id: string | null;
  patient_display_name: string;
  patient_contact: string;
  starts_at: string;
  ends_at: string;
  timezone: string;
  status: ClinicAppointmentStatus;
  source: "dashboard" | "voice_agent" | "api";
  cancellation_reason: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
}
