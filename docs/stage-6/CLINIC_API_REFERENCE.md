# SVARIO — STAGE 6: CLINIC API REFERENCE

**Base Prefix:** `/api/v1/organizations/{organization_id}/clinics/{business_id}`  
**Authentication:** Bearer Supabase JWT (`AuthenticatedUser`). All endpoints verify organization membership, `industry == "clinic"`, and business ownership. Configuration mutations require `owner` or `admin` role.

---

## 1. Departments
- `GET /departments?active_only=false` — List clinic departments.
- `POST /departments` — Create department (`name`, `description`, `is_active`). Returns `201` or `409` on duplicate name.
- `PATCH /departments/{department_id}` — Update department or toggle `is_active`.

## 2. Specialities
- `GET /specialities?active_only=false` — List clinic specialities.
- `POST /specialities` — Create speciality (`name`, `description`, `is_active`).
- `PATCH /specialities/{speciality_id}` — Update speciality.

## 3. Consultation Types
- `GET /consultation-types?active_only=false` — List consultation types.
- `POST /consultation-types` — Create consultation type (`name`, `duration_minutes` 5..240, `consultation_mode` `in_person | online`, optional `fee_amount`, `currency_code`).
- `PATCH /consultation-types/{consultation_type_id}` — Update consultation type.

## 4. Doctors & Mappings
- `GET /doctors?active_only=false&department_id=&speciality_id=` — List doctors with filters.
- `GET /doctors/{doctor_id}` — Get doctor details.
- `POST /doctors` — Create doctor with optional `department_ids`, `speciality_ids`, `consultation_type_ids`.
- `PATCH /doctors/{doctor_id}` — Update doctor profile or `is_active`.
- `PUT /doctors/{doctor_id}/departments` — Replace doctor department assignments (`{"ids": [...]}`).
- `PUT /doctors/{doctor_id}/specialities` — Replace doctor speciality assignments (`{"ids": [...]}`).
- `PUT /doctors/{doctor_id}/consultation-types` — Replace doctor consultation type eligibility (`{"ids": [...]}`).

## 5. Schedules, Breaks & Unavailability
- `GET /doctors/{doctor_id}/working-hours` — Get weekly shifts (`0=Sunday .. 6=Saturday`).
- `PUT /doctors/{doctor_id}/working-hours` — Bulk upsert weekly shifts.
- `GET /doctors/{doctor_id}/breaks` — List recurring or date-specific breaks.
- `POST /doctors/{doctor_id}/breaks` — Add break (`day_of_week` or `specific_date`, `break_start < break_end`).
- `GET /doctors/{doctor_id}/unavailability` — List doctor leave/unavailability blocks.
- `POST /doctors/{doctor_id}/unavailability` — Add unavailability (`starts_at < ends_at`).

## 6. Dynamic Availability & Appointments
- `GET /availability?consultation_type_id=&target_date=YYYY-MM-DD&doctor_id=&department_id=&speciality_id=` — Compute conflict-free slots in clinic timezone.
- `GET /appointments?doctor_id=&target_date=&status_filter=` — List clinic appointments (authenticated org members only).
- `GET /appointments/{appointment_id}` — Get appointment details.
- `POST /appointments` — Idempotent, overlap-safe booking (`doctor_id`, `consultation_type_id`, `patient_display_name`, `patient_contact`, `starts_at`, optional `department_id`, `idempotency_key`).
- `POST /appointments/{appointment_id}/reschedule` — Atomic reschedule (`new_starts_at`, optional `new_doctor_id`).
- `POST /appointments/{appointment_id}/cancel` — Idempotent cancellation (`reason`).
