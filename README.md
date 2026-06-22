# Careflow — Hospital Queue Management & OPD Booking System

A role-based Django REST backend for managing hospital queues, OPD appointments, and patient registration with dedicated dashboards for patients, receptionists, hospital admins, and super admins.

---

## Features

- **Phone + OTP Authentication** — OTP-based login with JWT session management
- **Multi-Role System** — Patient, Receptionist, Hospital Admin, Doctor, Super Admin
- **Queue Management** — Real-time token generation, status tracking, cancel/reschedule with audit trail
- **OPD Appointment Booking** — Browse doctors by department, view available slots, book/reschedule/cancel
- **Live Queue Status** — Track token position and now-serving for any doctor
- **Patient Portal** — Profile management, family members, appointment history, activity log
- **Hospital Administration** — Manage departments, doctors, time slots, holidays, emergency closures
- **Super Admin Panel** — User management, groups, permissions, staff creation
- **Token Counter** — Auto-incrementing daily tokens per doctor with prefix (e.g. A-001, B-015)
- **Slot Reuse** — Cancelled tokens can be reassigned to new patients

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Django 6.0.5, Django REST Framework 3.17.1 |
| Database | MySQL 8 (via PyMySQL) |
| Auth | JWT (simplejwt) + Session Auth |
| Frontend | Vanilla JavaScript (SPA-style HTML templates) |
| Time Zone | Asia/Kathmandu |

**Dependencies:**
```
Django==6.0.5
djangorestframework==3.17.1
djangorestframework_simplejwt==5.5.1
django-cors-headers==4.4.0
django-filter==25.2
django-storages==1.14.6
PyMySQL==1.2.0
```

---

## Architecture Overview

```
                    +------------------+
                    |  Login/Register   |
                    |  (loginregis.html)|
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
       +------v------+ +----v-----+ +------v-------+
       | Receptionist| | Hospital  | |   Patient    |
       | (reception/) | | Admin     | |  (Patient/)  |
       |              | |(hospital_ | |              |
       | Queue mgmt   | | admin/)   | | Appointment  |
       | Token issue  | |            | | booking      |
       | Patient      | |Depts,Dr's,| | Live queue   |
       | search       | |Holidays,  | | Family mgmt  |
       +------+-------+ |TimeSlots  | +--------------+
              |         +-----+-----+
              |               |
       +------v---------------v---+
       |       accounts/          |
       |  Auth, Users, OTP, Roles |
       +--------------------------+
       +--------------------------+
       |      super_admin/        |
       |  (page only — uses       |
       |   accounts APIs)         |
       +--------------------------+
```

All apps depend on `accounts` for identity and role checks. The `hospital_admin` app provides Department and Doctor models consumed by `reception` and `Patient`. The `TokenCounter` model in `reception` is shared for generating appointment tokens.

---

## Project Structure

```
careflow/
├── manage.py                          # Django management script
├── requirements.txt                   # Python dependencies
├── backend/                           # Django project package
│   ├── settings.py                    # Project settings
│   ├── urls.py                        # Root URL configuration
│   ├── wsgi.py                        # WSGI entry point
│   └── asgi.py                        # ASGI entry point
│
├── accounts/                          # User authentication & management
│   ├── models.py                      # Custom User model
│   ├── serializers.py                 # User, Group, Permission serializers
│   ├── views.py                       # OTP, register, login, user CRUD
│   ├── urls.py                        # /api/auth/ routes
│   └── permissions.py                 # Role-based permission classes
│
├── reception/                         # Queue management
│   ├── models.py                      # QueueEntry, Patient, ActivityLog, TokenCounter
│   ├── serializers.py                 # Queue entry serializers
│   ├── views.py                       # Queue CRUD, stats, search, tokens
│   └── urls.py                        # /api/reception/ routes
│
├── hospital_admin/                    # Hospital administration
│   ├── models.py                      # Department, Doctor, HospitalProfile, Holiday, TimeSlot, EmergencyClosure
│   ├── serializers.py                 # Model serializers
│   ├── views.py                       # CRUD viewsets
│   └── urls.py                        # /api/admin/ routes
│
├── Patient/                           # Patient portal
│   ├── models.py                      # PatientProfile, FamilyMember, Appointment
│   ├── serializers.py                 # Profile, appointment serializers
│   ├── views.py                       # Register, profile, appointments, queue, family
│   ├── urls.py                        # /api/patient/ routes
│   └── urls_page.py                   # /patient/ page route
│
├── super_admin/                       # Super admin (page only)
│   └── urls_page.py                   # /super-admin/ page route
│
├── templates/                         # HTML templates
│   ├── loginregis.html                # Login/registration page
│   ├── reception.html                 # Receptionist dashboard
│   ├── hospital-admin.html            # Hospital admin dashboard
│   ├── patient.html                   # Patient portal
│   └── super-admin.html               # Super admin dashboard
│
└── static/                            # Static files
    ├── css/login-style.css
    ├── images/Careflow_LOGO.png
    └── js/api.js                      # Central API client (vanilla JS)
```

---

## Django Apps & Models

### accounts — User & Authentication

| Model | Fields | Notes |
|---|---|---|
| User | `phone` (unique), `role`, `avatar_color`, `gender`, `date_of_birth`, `address` | Extends Django's `AbstractUser` |

**Roles:** `patient`, `doctor`, `receptionist`, `hospital_admin`, `super_admin`

### reception — Queue Management

| Model | Fields | Purpose |
|---|---|---|
| Patient | `name`, `phone`, `created_at` | Walk-in patient record |
| QueueEntry | `token`, `patient`, `doctor`, `status`, `visit_type`, `time`, `notes`, `cancel_source`, `reassigned` | Core queue line item |
| ActivityLog | `user`, `message`, `type`, `related_token`, `timestamp` | Audit trail for queue actions |
| TokenCounter | `doctor_prefix`, `date`, `counter_value` | Daily auto-incrementing token numbers |

### hospital_admin — Hospital Administration

| Model | Fields | Purpose |
|---|---|---|
| Department | `name`, `icon`, `floor`, `head`, `is_active` | Clinical departments |
| Doctor | `user`, `name`, `specialty`, `department`, `prefix` (unique), `status`, `slots_per_day` | Doctors with token prefix |
| HospitalProfile | `name`, `address`, `phone`, `email`, `logo_icon`, `registration_no` | Singleton hospital info |
| Holiday | `name`, `date`, `type`, `affects_all`, `is_active` | Hospital holidays |
| TimeSlot | `doctor`, `day_of_week`, `start_time`, `end_time`, `is_booked`, `max_patients` | Doctor availability |
| EmergencyClosure | `reason`, `from_date`, `to_date`, `is_active` | Emergency department closures |

### Patient — Patient Portal

| Model | Fields | Purpose |
|---|---|---|
| PatientProfile | `user`, `date_of_birth`, `blood_group`, `address`, `emergency_contact` | Extended patient info |
| FamilyMember | `patient`, `name`, `relationship`, `phone`, `date_of_birth`, `blood_group` | Family members for booking |
| Appointment | `patient`, `doctor_name`, `appointment_date`, `appointment_time`, `token`, `fee`, `status` | Patient bookings |

---

## API Reference

### Authentication — `/api/auth/`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/check-phone/` | Public | Check if phone is registered |
| POST | `/api/auth/send-otp/` | Public | Send OTP |
| POST | `/api/auth/verify-otp/` | Public | Verify OTP, issue JWT |
| POST | `/api/auth/register/` | Public | Register new user |
| POST | `/api/auth/login/` | Public | Phone + password login |
| GET | `/api/auth/me/` | Authenticated | Current user info |
| GET | `/api/auth/users/` | HospitalAdmin+ | List users (filter by `?role=`) |
| POST | `/api/auth/create-staff/` | HospitalAdmin+ | Create staff users |
| PATCH | `/api/auth/users/<id>/toggle-status/` | HospitalAdmin+ | Enable/disable user |
| PATCH | `/api/auth/users/<id>/update/` | HospitalAdmin+ | Update user |
| GET | `/api/auth/users/<id>/` | HospitalAdmin+ | User detail with groups |
| PUT | `/api/auth/users/<id>/groups/` | HospitalAdmin+ | Set user groups |
| GET | `/api/auth/permissions/` | HospitalAdmin+ | All permissions |
| GET | `/api/auth/groups/` | HospitalAdmin+ | List groups |
| POST | `/api/auth/groups/` | HospitalAdmin+ | Create group |
| GET/PUT/DELETE | `/api/auth/groups/<id>/` | HospitalAdmin+ | Group CRUD |
| POST | `/api/auth/token/refresh/` | Public | Refresh JWT |

### Queue (Reception) — `/api/reception/`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/reception/queue/` | Receptionist+ | List queue entries (filters: `status`, `type`, `reassigned`) |
| GET | `/api/reception/queue/stats/` | Receptionist+ | Queue counts by status |
| GET | `/api/reception/queue/<id>/` | Receptionist+ | Single queue entry |
| POST | `/api/reception/queue/create/` | Receptionist+ | Create queue entry |
| PATCH | `/api/reception/queue/<id>/status/` | Receptionist+ | Update status |
| PATCH | `/api/reception/queue/<id>/cancel/` | Receptionist+ | Cancel with source tracking |
| PATCH | `/api/reception/queue/<id>/reschedule/` | Receptionist+ | Reschedule queue entry |
| GET | `/api/reception/patients/search/` | Receptionist+ | Search patients |
| GET | `/api/reception/patients/check/` | Receptionist+ | Check active queue entry |
| GET | `/api/reception/tokens/next/` | Receptionist+ | Preview next token |
| GET/POST | `/api/reception/activity/` | Receptionist+ | Activity log |
| GET | `/api/reception/doctors/` | Public | Active doctors with wait counts |

### Hospital Admin — `/api/admin/`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| CRUD | `/api/admin/departments/` | HospitalAdmin+ | Department management |
| CRUD | `/api/admin/doctors/` | HospitalAdmin+ | Doctor management (searchable, filterable) |
| GET/PUT | `/api/admin/hospital-profile/` | HospitalAdmin+ | Hospital info singleton |
| CRUD | `/api/admin/holidays/` | HospitalAdmin+ | Holiday management |
| CRUD | `/api/admin/slots/` | HospitalAdmin+ | Time slots (filter `?doctor=`) |
| CRUD | `/api/admin/emergency-closures/` | HospitalAdmin+ | Emergency closures |

### Patient — `/api/patient/`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/patient/register/` | Public | Register new patient |
| GET/PATCH | `/api/patient/profile/` | Authenticated | View/update profile |
| GET/POST | `/api/patient/family/` | Authenticated | List/add family members |
| GET/PUT/DELETE | `/api/patient/family/<id>/` | Authenticated | Family member CRUD |
| GET | `/api/patient/departments/` | Public | Active departments |
| GET | `/api/patient/doctors/` | Public | Active doctors (filter `?department=`) |
| GET | `/api/patient/doctors/<id>/` | Public | Doctor detail with wait count |
| GET | `/api/patient/doctors/slots/` | Public | Available slots (`?doctor_id=&date=`) |
| GET/POST | `/api/patient/appointments/` | Authenticated | List/book appointments |
| GET/DELETE | `/api/patient/appointments/<id>/` | Authenticated | Detail/cancel appointment |
| PATCH | `/api/patient/appointments/<id>/reschedule/` | Authenticated | Reschedule appointment |
| GET | `/api/patient/queue/status/` | Authenticated | Queue position (`?doctor=&token=`) |
| GET | `/api/patient/queue/doctor-list/` | Authenticated | Full doctor queue |
| GET | `/api/patient/my-bookings/` | Authenticated | Upcoming/history (`?filter=`) |
| GET | `/api/patient/activity/` | Authenticated | Recent activity |

### Page Routes

| Route | View | Template |
|---|---|---|
| `/login/` | `login_registration_page` | `loginregis.html` |
| `/logout/` | `LogoutView` | Redirects to `/login/` |
| `/` | Lambda redirect | Redirects to `/login/` |
| `/reception/` | `reception_dashboard` | `reception.html` |
| `/admin-panel/` | `admin_dashboard` | `hospital-admin.html` |
| `/super-admin/` | `super_admin_dashboard` | `super-admin.html` |
| `/patient/` | `patient_dashboard` | `patient.html` |
| `/api/login/` | `LoginView` | JWT login (backwards compat) |

---

## Quick Start

### Prerequisites

- Python 3.10+
- MySQL 8+
- Node.js (optional — only for the `package-lock.json` artifact)

### Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd AuralithCareflow_Backend

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Linux/macOS

# 3. Install dependencies
pip install -r careflow/requirements.txt

# 4. Create MySQL database
mysql -u root -p -e "CREATE DATABASE careflow_DB CHARACTER SET utf8mb4;"

# 5. Update database credentials in careflow/backend/settings.py
#    (DATABASES -> default -> USER / PASSWORD)

# 6. Run migrations
python careflow/manage.py migrate

# 7. Create a superuser
python careflow/manage.py createsuperuser

# 8. Start development server
python careflow/manage.py runserver
```

The server starts at `http://127.0.0.1:8000/`.

---

## Authentication

### Phone + OTP Flow (Primary)

1. **Check Phone** — `POST /api/auth/check-phone/` — determines if the user exists
2. **Send OTP** — `POST /api/auth/send-otp/` — generates a 6-digit OTP
3. **Verify OTP** — `POST /api/auth/verify-otp/` — validates OTP, returns JWT tokens + creates Django session

### Phone + Password Flow (Fallback)

`POST /api/auth/login/` — standard Django authentication using `username=phone`

### JWT Configuration

| Parameter | Value |
|---|---|
| Access token lifetime | 12 hours |
| Refresh token lifetime | 7 days |
| Auth header | `Bearer <token>` |

The frontend `api.js` stores the JWT in `localStorage` and automatically redirects to `/login/` on 401 responses.

---

## Role Hierarchy

```
super_admin       — Full system access (users, groups, permissions)
hospital_admin    — Manage departments, doctors, time slots, holidays
receptionist      — Queue management, token issue, patient search
doctor            — Role defined, no dedicated dashboard yet
patient           — Appointment booking, queue tracking, profile management
```

Permission classes (`accounts/permissions.py`):
- `IsReceptionist` — allows `receptionist`, `hospital_admin`, `super_admin`
- `IsHospitalAdmin` — allows `hospital_admin`, `super_admin`
- `IsAdminOrReceptionist` — allows all three staff roles

---

## Frontend

Each dashboard is a standalone HTML template with embedded vanilla JavaScript, communicating with the backend via the `API` singleton in `static/js/api.js`. The `API` object provides namespaced methods:

```javascript
API.patient.register(data);          // POST /api/patient/register/
API.reception.createEntry(data);     // POST /api/reception/queue/create/
API.admin.createDoctor(data);        // POST /api/admin/doctors/
```

No frontend framework is used — all DOM manipulation is plain JavaScript.

---

## Development Notes

- OTP is returned in the API response for demo purposes (`SendOTPView` returns `{"sent": true, "otp": "123456"}`). Replace with an SMS gateway for production.
- MySQL credentials are currently hardcoded in `settings.py`. Use environment variables for production.
- Set `DEBUG=False`, restrict `ALLOWED_HOSTS`, and lock down `CORS_ALLOWED_ORIGINS` before deploying.
- The `Patient` app imports from `admin_panel` (legacy table names) but `INSTALLED_APPS` uses `hospital_admin`. This is compatible because the underlying MySQL tables are named `admin_panel_*`.
