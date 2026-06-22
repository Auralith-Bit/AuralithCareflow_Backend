# Patient Backend App

Django app for the patient-facing portal of the Careflow hospital queue management system.

## Directory Structure

```
Patient/
├── __init__.py
├── admin.py              # Admin registration for all models
├── apps.py               # AppConfig (name = 'Patient')
├── models.py             # PatientProfile, FamilyMember, Appointment
├── serializers.py        # DRF serializers for all models
├── urls.py               # API route definitions (/api/patient/)
├── urls_page.py          # Page route for patient.html (/patient/)
├── views.py              # All API views and page serving
├── README.md
└── migrations/
    ├── __init__.py
    └── 0001_initial.py   # Initial migration
```

## Models

### PatientProfile
Linked 1-to-1 with `accounts.User` (role=patient). Auto-created on first profile access.

| Field | Type | Notes |
|---|---|---|
| user | OneToOneField(User) | Linked user account |
| date_of_birth | DateField | nullable |
| blood_group | CharField(5) | e.g. "B+", "O-" |
| address | TextField | Patient's address |
| emergency_contact | CharField(20) | Emergency phone |
| created_at | DateTimeField | Auto |
| updated_at | DateTimeField | Auto |

### FamilyMember
Family members linked to a patient profile for booking on their behalf.

| Field | Type | Notes |
|---|---|---|
| patient | ForeignKey(PatientProfile) | Parent patient |
| name | CharField(200) | Full name |
| relationship | CharField(100) | e.g. "Spouse", "Son" |
| phone | CharField(20) | |
| date_of_birth | DateField | nullable |
| blood_group | CharField(5) | |
| is_active | BooleanField | Soft delete support |

### Appointment
Patient appointments/bookings with auto-generated token.

| Field | Type | Notes |
|---|---|---|
| patient | ForeignKey(PatientProfile) | Who booked |
| doctor_name | CharField(200) | Doctor's full name |
| doctor_specialty | CharField(200) | e.g. "MD, Senior Cardiologist" |
| department_name | CharField(100) | e.g. "Cardiology" |
| location | CharField(200) | Room/ward info |
| appointment_date | DateField | YYYY-MM-DD |
| appointment_time | TimeField | HH:MM:SS |
| token | CharField(20) | Auto-generated (e.g. "A-47") |
| fee | DecimalField(10,2) | Consultation fee |
| status | CharField(20) | confirmed/scheduled/rescheduled/cancelled/completed/missed |
| notes | TextField | Reason / notes |

## API Endpoints

All endpoints are prefixed with `/api/patient/`.

### Auth & Profile
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/register/` | No | Register new patient (creates User + PatientProfile) |
| GET | `/profile/` | Yes | Get patient profile (auto-creates if new) |
| PATCH | `/profile/` | Yes | Update profile + user fields (name, email, DOB, etc.) |

### Family Members
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/family/` | Yes | List active family members |
| POST | `/family/` | Yes | Add a family member |
| GET | `/family/<id>/` | Yes | Get family member detail |
| PUT | `/family/<id>/` | Yes | Update family member |
| DELETE | `/family/<id>/` | Yes | Remove family member |

### Doctors & Departments
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/departments/` | No | List all active departments |
| GET | `/doctors/?department=Cardiology` | No | List active doctors (optional dept filter) |
| GET | `/doctors/<id>/` | No | Doctor detail with waiting count |
| GET | `/doctors/slots/?doctor_id=2&date=2026-06-23` | No | Available time slots for a doctor on a date |

### Appointments
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/appointments/` | Yes | List patient's appointments |
| POST | `/appointments/` | Yes | Book appointment (auto-generates token) |
| GET | `/appointments/<id>/` | Yes | Appointment detail |
| PATCH | `/appointments/<id>/reschedule/` | Yes | Change date/time of appointment |
| DELETE | `/appointments/<id>/` | Yes | Cancel appointment (soft delete) |

### Queue & Activity
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/queue/status/?doctor=X&token=Y` | Yes | Get queue position (tokens ahead, now serving) |
| GET | `/queue/doctor-list/?doctor=X` | Yes | Full active queue for a doctor |
| GET | `/my-bookings/?filter=upcoming` | Yes | Upcoming appointments |
| GET | `/my-bookings/?filter=history` | Yes | Past appointments |
| GET | `/activity/` | Yes | Recent activity (completed/missed/cancelled) |

## Page Serving
| Route | View | Template |
|---|---|---|
| `/patient/` | `patient_dashboard` | `patient.html` |

## Dependencies (Read-only from other apps)
- `accounts.User` — user authentication and role management
- `accounts.permissions` — permission classes
- `admin_panel.Doctor` — doctor listing and availability
- `admin_panel.Department` — department listing
- `admin_panel.TimeSlot` — doctor time slot availability
- `reception.QueueEntry` — queue status tracking
- `reception.TokenCounter` — token number generation
