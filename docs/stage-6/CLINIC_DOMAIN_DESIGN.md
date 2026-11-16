# SVARIO — STAGE 6: CLINIC DOMAIN DESIGN

**Milestone:** Stage 6 — Clinic Workflow Module  
**Date:** 2026-11-16  
**Scope:** Outpatient & Specialty Clinics (`OrganizationIndustry.CLINIC`)

---

## 1. Domain Separation & Independence

The Clinic module is implemented as an independent domain (`apps/api/app/modules/clinics/`) separate from Salons (`apps/api/app/modules/salons/`) and Hospitals (Stage 7).

- **No Salon Coupling:** Doctors are NOT modeled as salon staff; consultations are NOT modeled as salon services.
- **No Generalized Scheduling Engine:** Stage 8's unified scheduling engine is not introduced here. Clinic availability logic lives cleanly inside `ClinicWorkflowService`, reusing only standard Python `datetime`/`zoneinfo` utilities and Svario's core `AuthenticatedUser` and `OrganizationService` contracts.

---

## 2. Core Clinic Entities & Relationships

1. **`clinic_departments`:** Logical clinical units (e.g., *General Medicine*, *Dermatology*, *Pediatrics*, *Dental*).
2. **`clinic_specialities`:** Medical specialities (e.g., *Cardiology Consultation*, *Orthopedics*, *General Practice*).
3. **`clinic_doctors`:** Administrative practitioner profiles (`display_name`, `professional_title`, `public_bio`, `languages`, `is_active`). Deliberately excludes private personal/home contact info or medical credentials/license numbers not required for reception discovery.
4. **`clinic_consultation_types`:** Administrative appointment types (`name`, `description`, `duration_minutes` 5–240, `consultation_mode` in `in_person | online`, optional `fee_amount`, optional `currency_code`, `is_active`). Excludes clinical treatment plans or medical procedure coding.
5. **Doctor Mappings:**
   - `clinic_doctor_departments`: Many-to-many assignment of doctors to departments.
   - `clinic_doctor_specialities`: Many-to-many assignment of doctors to specialities.
   - `clinic_doctor_consultation_types`: Many-to-many eligibility mapping determining which doctors offer which consultation types.
6. **Doctor Schedules & Availability:**
   - `clinic_doctor_working_hours`: Weekly schedule (`day_of_week` 0=Sunday..6=Saturday, `start_time`, `end_time`, `is_active`).
   - `clinic_doctor_breaks`: Recurring weekday or `specific_date` break intervals (`break_start`, `break_end`, `reason`).
   - `clinic_doctor_unavailability`: Date-time range unavailability/leave (`starts_at`, `ends_at`, `reason`).
7. **`clinic_appointments`:**
   - `id`, `organization_id`, `business_id`, `booking_reference` (e.g. `CLN-XXXXXXXX`), `doctor_id`, `consultation_type_id`, `department_id` (optional), `patient_display_name`, `patient_contact` (minimum administrative contact), `starts_at`, `ends_at`, `timezone`, `status` (`confirmed`, `rescheduled`, `cancelled`, `completed`, `no_show`), `idempotency_key`, `cancellation_reason`, `created_at`, `updated_at`.
   - Half-open interval `[starts_at, ends_at)` with PostgreSQL `btree_gist` exclusion constraint (`doctor_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&`) for active statuses (`confirmed`, `rescheduled`).

---

## 3. Availability Calculation Rules

`ClinicWorkflowService.get_availability(...)` computes valid slots for a target date by enforcing:
1. Business exists and belongs to `organization_id`.
2. Requested `consultation_type_id` exists, belongs to clinic, and `is_active = True`.
3. Requested `department_id` (if provided) exists, belongs to clinic, and `is_active = True`.
4. Candidate doctors must be `is_active = True`, eligible for `consultation_type_id`, and (if filtered) belong to `department_id` / `speciality_id`.
5. Clinic operating hours on that weekday (from `business_hours`) are respected if configured.
6. Doctor's `clinic_doctor_working_hours` for that `day_of_week` must be active (`is_active = True`).
7. Slots are sliced by `consultation_type.duration_minutes` (default step 15 or `duration_minutes`) in the clinic's `timezone`.
8. Slots overlapping `clinic_doctor_breaks`, `clinic_doctor_unavailability`, or active `clinic_appointments` (`confirmed` / `rescheduled`) are excluded.
9. Slots earlier than `now + lead_time_minutes` (if configured) are excluded.

---

## 4. Patient Data Minimization & Verification

- **Minimum Data:** Only `patient_display_name` and `patient_contact` (phone or email) are collected. No symptoms, diagnoses, medical history, prescriptions, insurance, or clinical notes are stored.
- **Voice Reschedule / Cancel Verification:** When rescheduling or cancelling via the voice agent, the caller must provide `booking_reference` AND `patient_contact_verification` (matching the stored `patient_contact` or its last 4+ characters). If verification fails, the backend returns a generic authorization/not-found error without leaking appointment existence.
