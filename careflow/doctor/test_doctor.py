"""
Doctor Module Comprehensive End-to-End Test
Tests all API endpoints with the Django test client
"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
django.setup()

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status
from datetime import datetime, timedelta

from accounts.models import User
from hospital_admin.models import Doctor, Department
from reception.models import QueueEntry, TokenCounter
from doctor.models import VitalRecord, ConsultationNote, DoctorNotification, DoctorScheduleSettings
from doctor.views import (
    DoctorQueueView, DoctorQueueStatsView, CallNextPatientView,
    UpdateQueueEntryStatusView, AddEmergencyTokenView, ReorderQueueView,
    RegisterPatientView, PatientDirectoryView, VitalsView,
    ConsultationNoteView, ReferDoctorListView, ReferPatientView,
    DoctorScheduleView, DoctorNotificationListView, ClearNotificationsView,
    DoctorProfileView, DoctorStatusView, DoctorHistoryView,
)

User = get_user_model()

class DoctorModuleTest(TestCase):
    """End-to-end tests for the Doctor module"""

    @classmethod
    def setUpTestData(cls):
        # Create/get department
        cls.dept, _ = Department.objects.get_or_create(
            name='General Medicine', defaults={'floor': '1st Floor', 'is_active': True}
        )

        # Create a doctor user
        cls.doctor_user, _ = User.objects.get_or_create(
            phone='9800000001', defaults={'name': 'Dr. Test Doctor', 'role': 'doctor', 'is_active': True}
        )

        # Create an admin user (for cross-role access)
        cls.admin_user, _ = User.objects.get_or_create(
            phone='9800000099', defaults={'name': 'Admin User', 'role': 'hospital_admin', 'is_active': True}
        )

        # Create/update doctor profile
        cls.doctor, _ = Doctor.objects.update_or_create(
            user=cls.doctor_user,
            defaults={
                'name': 'Dr. Test Doctor',
                'specialty': 'General Physician',
                'department': cls.dept,
                'prefix': 'Z',
                'qualification': 'MD',
                'phone': '9800000001',
                'status': 'active',
                'is_active': True,
            }
        )

        cls.factory = APIRequestFactory()

    def _auth_request(self, method, url, data=None, user=None):
        """Helper to make authenticated requests"""
        if user is None:
            user = self.doctor_user
        if method == 'GET':
            request = self.factory.get(url)
        elif method == 'POST':
            request = self.factory.post(url, data or {}, format='json')
        elif method == 'PATCH':
            request = self.factory.patch(url, data or {}, format='json')
        elif method == 'PUT':
            request = self.factory.put(url, data or {}, format='json')
        elif method == 'DELETE':
            request = self.factory.delete(url)
        force_authenticate(request, user=user)
        return request

    def _get_response(self, view_class, method, url, data=None, user=None, **kwargs):
        """Get response from a view"""
        request = self._auth_request(method, url, data, user)
        view = view_class.as_view()
        # Resolve URL kwargs from the path (strip query string)
        from django.urls import resolve
        path = url.split('?')[0]
        resolver_match = resolve(path)
        resolver_match.kwargs.update(kwargs)
        return view(request, **resolver_match.kwargs)

    # ========== TEST 1: Doctor Queue View ==========
    def test_01_queue_empty(self):
        """Queue should return empty list when no patients"""
        resp = self._get_response(DoctorQueueView, 'GET', '/api/doctor/queue/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)

    def test_02_register_patient(self):
        """Register a walk-in patient"""
        resp = self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'Raju Sharma',
            'patient_phone': '9841000001',
            'complaint': 'Fever and cough',
            'token_type': 'normal',
            'age': 30,
            'gender': 'Male',
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['patient_name'], 'Raju Sharma')
        self.assertTrue(resp.data['token'].startswith(self.doctor.prefix + '-'))
        self.assertEqual(resp.data['status'], 'waiting')

    def test_03_queue_after_register(self):
        """Queue should show registered patient"""
        self.test_02_register_patient()
        resp = self._get_response(DoctorQueueView, 'GET', '/api/doctor/queue/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['patient_name'], 'Raju Sharma')
        self.assertEqual(resp.data[0]['status'], 'waiting')

    def test_04_queue_stats(self):
        """Queue stats should be accurate"""
        self.test_02_register_patient()
        resp = self._get_response(DoctorQueueStatsView, 'GET', '/api/doctor/queue/stats/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total'], 1)
        self.assertEqual(resp.data['waiting'], 1)
        self.assertEqual(resp.data['done'], 0)

    # ========== TEST 2: Call Next Flow ==========
    def test_10_call_next(self):
        """Call next patient should advance queue"""
        self.test_02_register_patient()
        resp = self._get_response(CallNextPatientView, 'POST', '/api/doctor/queue/call-next/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['patient_name'], 'Raju Sharma')

        # Verify status changed to serving
        q = QueueEntry.objects.get(token=resp.data['token'])
        self.assertEqual(q.status, 'serving')

    def test_11_call_next_empty(self):
        """Call next with empty queue should return queue_complete"""
        resp = self._get_response(CallNextPatientView, 'POST', '/api/doctor/queue/call-next/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get('queue_complete'))

    def test_12_full_queue_cycle(self):
        """Full cycle: register → call next → mark done → stats update"""
        # Register 2 patients
        self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'Patient One', 'complaint': 'Headache', 'token_type': 'normal',
        })
        self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'Patient Two', 'complaint': 'Fever', 'token_type': 'normal',
        })

        # Verify 2 waiting
        stats = self._get_response(DoctorQueueStatsView, 'GET', '/api/doctor/queue/stats/')
        self.assertEqual(stats.data['waiting'], 2)

        # Call next
        call1 = self._get_response(CallNextPatientView, 'POST', '/api/doctor/queue/call-next/')
        self.assertEqual(call1.data['patient_name'], 'Patient One')

        # Mark as done (update status to 'done')
        q1 = QueueEntry.objects.filter(patient_name='Patient One').first()
        resp = self._get_response(UpdateQueueEntryStatusView, 'PATCH',
            f'/api/doctor/queue/{q1.pk}/status/', {'status': 'done'})
        self.assertEqual(resp.status_code, 200)

        # Call next should pick Patient Two
        call2 = self._get_response(CallNextPatientView, 'POST', '/api/doctor/queue/call-next/')
        self.assertEqual(call2.data['patient_name'], 'Patient Two')

        # Stats: 1 done, 1 serving
        stats = self._get_response(DoctorQueueStatsView, 'GET', '/api/doctor/queue/stats/')
        self.assertEqual(stats.data['done'], 1)

    # ========== TEST 3: Status Updates ==========
    def test_20_skip_patient(self):
        """Skip should update status to skipped"""
        self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'Skip Test Patient', 'token_type': 'normal',
        })
        self._get_response(CallNextPatientView, 'POST', '/api/doctor/queue/call-next/')

        q = QueueEntry.objects.filter(patient_name='Skip Test Patient').first()
        resp = self._get_response(UpdateQueueEntryStatusView, 'PATCH',
            f'/api/doctor/queue/{q.pk}/status/', {'status': 'skipped'})
        self.assertEqual(resp.status_code, 200)

        # Verify via queue
        queue = self._get_response(DoctorQueueView, 'GET', '/api/doctor/queue/')
        skipped = [e for e in queue.data if e['status'] == 'skipped']
        self.assertEqual(len(skipped), 1)

    def test_21_hold_patient(self):
        """Hold should update status to hold"""
        self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'Hold Patient', 'token_type': 'normal',
        })
        q = QueueEntry.objects.filter(patient_name='Hold Patient').first()
        resp = self._get_response(UpdateQueueEntryStatusView, 'PATCH',
            f'/api/doctor/queue/{q.pk}/status/', {'status': 'hold'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'hold')

    def test_22_noshow_patient(self):
        """No-show should update status to noshow"""
        self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'NoShow Patient', 'token_type': 'normal',
        })
        q = QueueEntry.objects.filter(patient_name='NoShow Patient').first()
        resp = self._get_response(UpdateQueueEntryStatusView, 'PATCH',
            f'/api/doctor/queue/{q.pk}/status/', {'status': 'noshow'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'noshow')

    def test_23_cancel_patient(self):
        """Cancel should set status to cancelled"""
        self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'Cancel Patient', 'token_type': 'normal',
        })
        q = QueueEntry.objects.filter(patient_name='Cancel Patient').first()
        resp = self._get_response(UpdateQueueEntryStatusView, 'PATCH',
            f'/api/doctor/queue/{q.pk}/status/', {'status': 'cancelled'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'cancelled')

    # ========== TEST 4: Emergency Token ==========
    def test_30_add_emergency(self):
        """Emergency token should be added and appear in queue"""
        resp = self._get_response(AddEmergencyTokenView, 'POST', '/api/doctor/queue/emergency/', {
            'patient_name': 'Emergency Patient',
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['patient_name'], 'Emergency Patient')
        self.assertTrue(resp.data['token'].startswith(self.doctor.prefix + '-'))

    # ========== TEST 5: Vitals ==========
    def test_40_save_and_get_vitals(self):
        """Save vitals then retrieve them"""
        self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'Vital Patient', 'token_type': 'normal',
        })
        q = QueueEntry.objects.filter(patient_name='Vital Patient').first()

        # Save vitals
        resp = self._get_response(VitalsView, 'POST', '/api/doctor/vitals/', {
            'queue_entry': q.pk,
            'bp': '120/80',
            'pulse': 72,
            'temp': 37.0,
            'spo2': 98,
            'weight': 65.0,
            'height': 170,
            'rbs': 110,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['bp'], '120/80')
        self.assertIsNotNone(resp.data['bmi'])  # BMI computed

        # Get vitals
        resp = self._get_response(VitalsView, 'GET', f'/api/doctor/vitals/{q.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['bp'], '120/80')

    # ========== TEST 6: Consultation Notes ==========
    def test_50_save_and_get_note(self):
        """Save consultation note then retrieve it"""
        self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'Note Patient', 'token_type': 'normal',
        })
        q = QueueEntry.objects.filter(patient_name='Note Patient').first()

        # Save note
        resp = self._get_response(ConsultationNoteView, 'POST', '/api/doctor/notes/', {
            'queue_entry': q.pk,
            'diagnosis': 'Viral fever',
            'prescription': 'Paracetamol 500mg TDS',
            'is_visible_to_patient': True,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['diagnosis'], 'Viral fever')

        # Get note
        resp = self._get_response(ConsultationNoteView, 'GET', f'/api/doctor/notes/{q.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['diagnosis'], 'Viral fever')
        self.assertEqual(resp.data['prescription'], 'Paracetamol 500mg TDS')

    # ========== TEST 7: Referral ==========
    def test_60_list_refer_doctors(self):
        """Refer doctor list should return active doctors"""
        resp = self._get_response(ReferDoctorListView, 'GET', '/api/doctor/refer/doctors/')
        self.assertEqual(resp.status_code, 200)
        names = [d['name'] for d in resp.data]
        self.assertIn('Dr. Test Doctor', names)

    def test_61_refer_patient(self):
        """Refer patient to another doctor"""
        self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'Refer Patient', 'token_type': 'normal',
        })
        q = QueueEntry.objects.filter(patient_name='Refer Patient').first()

        resp = self._get_response(ReferPatientView, 'POST',
            f'/api/doctor/refer/{q.pk}/', {
                'doctor': 'Dr. Specialist',
                'reason': 'Needs specialist consultation',
            })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'referred')
        self.assertEqual(resp.data['referred_to'], 'Dr. Specialist')
        self.assertEqual(resp.data['refer_reason'], 'Needs specialist consultation')

    # ========== TEST 8: Schedule ==========
    def test_70_get_schedule(self):
        """Schedule settings should return with defaults"""
        resp = self._get_response(DoctorScheduleView, 'GET', '/api/doctor/schedule/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('slot_duration', resp.data)
        self.assertIn('start_time', resp.data)

    def test_71_update_schedule(self):
        """Update schedule settings"""
        resp = self._get_response(DoctorScheduleView, 'PUT', '/api/doctor/schedule/', {
            'slot_duration': 15,
            'start_time': '09:30:00',
            'end_time': '16:00:00',
            'break_time': '13:00:00',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['slot_duration'], 15)

    # ========== TEST 9: Notifications ==========
    def test_80_notifications(self):
        """Notifications should list and clear"""
        # Create a notification via emergency
        self._get_response(AddEmergencyTokenView, 'POST', '/api/doctor/queue/emergency/', {
            'patient_name': 'Notif Patient',
        })

        resp = self._get_response(DoctorNotificationListView, 'GET', '/api/doctor/notifications/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 1)

        # Clear notifications
        resp = self._get_response(ClearNotificationsView, 'DELETE', '/api/doctor/notifications/clear/')
        self.assertEqual(resp.status_code, 200)

        resp = self._get_response(DoctorNotificationListView, 'GET', '/api/doctor/notifications/')
        self.assertEqual(len(resp.data), 0)

    # ========== TEST 10: Profile & Status ==========
    def test_90_get_profile(self):
        """Doctor profile should return correct data"""
        resp = self._get_response(DoctorProfileView, 'GET', '/api/doctor/profile/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['name'], 'Dr. Test Doctor')
        self.assertEqual(resp.data['specialty'], 'General Physician')

    def test_91_profile_readonly(self):
        """Doctor cannot edit own profile"""
        resp = self._get_response(DoctorProfileView, 'PUT', '/api/doctor/profile/', {
            'specialty': 'Cardiology',
        })
        self.assertEqual(resp.status_code, 405)

    def test_92_toggle_status(self):
        """Toggle doctor status"""
        # Initially active
        resp = self._get_response(DoctorStatusView, 'PATCH', '/api/doctor/status/', {
            'status': 'on-leave'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'on-leave')

    # ========== TEST 11: History ==========
    def test_100_history(self):
        """Completed consultations should appear in history"""
        self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'History Patient', 'token_type': 'normal',
        })
        q = QueueEntry.objects.filter(patient_name='History Patient').first()
        q.status = 'done'
        q.save()

        resp = self._get_response(DoctorHistoryView, 'GET', '/api/doctor/history/')
        self.assertEqual(resp.status_code, 200)
        names = [h['name'] for h in resp.data]
        self.assertIn('History Patient', names)

    # ========== TEST 12: Auth Guards ==========
    def test_110_unauthorized_access(self):
        """Non-doctor users should be rejected"""
        # Create a patient user
        patient_user, _ = User.objects.get_or_create(
            phone='9800000999', defaults={'name': 'Patient User', 'role': 'patient', 'is_active': True}
        )
        resp = self._get_response(DoctorQueueView, 'GET', '/api/doctor/queue/', user=patient_user)
        self.assertEqual(resp.status_code, 403)

    # ========== TEST 13: Patient Directory & Search ==========
    def test_120_patient_directory(self):
        """Patient directory should list all patients for this doctor"""
        self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'Dir Patient Alpha', 'token_type': 'normal',
        })
        self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'Dir Patient Beta', 'token_type': 'normal',
        })

        resp = self._get_response(PatientDirectoryView, 'GET', '/api/doctor/patients/')
        self.assertEqual(resp.status_code, 200)
        names = [p['patient_name'] for p in resp.data]
        self.assertIn('Dir Patient Alpha', names)
        self.assertIn('Dir Patient Beta', names)

    def test_121_patient_search(self):
        """Patient search should filter by name"""
        self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'Unique Name XYZ', 'token_type': 'normal',
        })
        self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'Something Else', 'token_type': 'normal',
        })

        resp = self._get_response(PatientDirectoryView, 'GET', '/api/doctor/patients/?q=Unique')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['patient_name'], 'Unique Name XYZ')

    # ========== TEST 14: Reorder Queue ==========
    def test_130_reorder_queue(self):
        """Reorder should work without errors"""
        resp = self._get_response(ReorderQueueView, 'POST', '/api/doctor/queue/reorder/')
        self.assertEqual(resp.status_code, 200)

    # ========== TEST 15: Data Consistency ==========
    def test_140_vitals_in_queue_response(self):
        """Queue response should include vitals data in the expected format"""
        self._get_response(RegisterPatientView, 'POST', '/api/doctor/patients/register/', {
            'patient_name': 'Vital Queue Check', 'token_type': 'normal',
        })
        q = QueueEntry.objects.filter(patient_name='Vital Queue Check').first()
        self._get_response(VitalsView, 'POST', '/api/doctor/vitals/', {
            'queue_entry': q.pk, 'bp': '130/85', 'pulse': 88, 'temp': 37.1, 'spo2': 97,
        })

        resp = self._get_response(DoctorQueueView, 'GET', '/api/doctor/queue/')
        entry = [e for e in resp.data if e['patient_name'] == 'Vital Queue Check']
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry[0]['vitals']['bp'], '130/85')
        self.assertEqual(entry[0]['vitals']['temp'], 37.1)


if __name__ == '__main__':
    import unittest
    unittest.main(verbosity=2)
