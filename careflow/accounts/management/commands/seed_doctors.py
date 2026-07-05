from django.core.management.base import BaseCommand
from django.db import transaction
from hospital_admin.models import Department, Doctor
from accounts.models import User
from doctor.models import DoctorScheduleSettings
from datetime import time
import string


DEPARTMENTS = [
    {'name': 'General Medicine', 'icon': '🏥', 'floor': 'Ground'},
    {'name': 'Cardiology', 'icon': '❤️', 'floor': '1st'},
    {'name': 'Orthopedics', 'icon': '🦴', 'floor': '1st'},
    {'name': 'Pediatrics', 'icon': '👶', 'floor': '2nd'},
    {'name': 'Dermatology', 'icon': '🧴', 'floor': '2nd'},
    {'name': 'Ophthalmology', 'icon': '👁️', 'floor': '3rd'},
    {'name': 'ENT', 'icon': '👂', 'floor': '3rd'},
    {'name': 'Neurology', 'icon': '🧠', 'floor': '4th'},
]

DOCTOR_SPECIALTIES = {
    'General Medicine': ['Internal Medicine', 'Family Medicine'],
    'Cardiology': ['Interventional Cardiology', 'Cardiac Electrophysiology'],
    'Orthopedics': ['Joint Replacement', 'Sports Medicine'],
    'Pediatrics': ['General Pediatrics', 'Pediatric Cardiology'],
    'Dermatology': ['Clinical Dermatology', 'Cosmetic Dermatology'],
    'Ophthalmology': ['Cataract Surgery', 'Retina Specialist'],
    'ENT': ['Otology', 'Rhinology'],
    'Neurology': ['Stroke Neurology', 'Epilepsy Neurology'],
}

FIRST_NAMES = ['Arun', 'Sita', 'Raj', 'Priya', 'Vikram', 'Anita', 'Mohan', 'Deepa',
               'Kiran', 'Sunita', 'Ravi', 'Meera', 'Amit', 'Neha', 'Sanjay', 'Pooja']

LAST_NAMES = ['Sharma', 'Verma', 'Patel', 'Gupta', 'Singh', 'Reddy', 'Nair', 'Joshi',
              'Das', 'Menon', 'Kumar', 'Iyer', 'Rao', 'Desai', 'Bose', 'Chopra']


class Command(BaseCommand):
    help = 'Seed departments and doctors (2 per department)'

    def handle(self, *args, **options):
        existing_prefixes = set(Doctor.objects.values_list('prefix', flat=True))
        avail = [l for l in string.ascii_uppercase if l not in existing_prefixes]
        prefix_idx = 0

        created_depts = 0
        created_doctors = 0
        doctor_names = []

        with transaction.atomic():
            for dept_data in DEPARTMENTS:
                dept, was_created = Department.objects.get_or_create(
                    name=dept_data['name'],
                    defaults={
                        'icon': dept_data['icon'],
                        'floor': dept_data['floor'],
                        'is_active': True,
                    },
                )
                if was_created:
                    created_depts += 1
                    self.stdout.write(f'  Created department: {dept.name}')

                doctor_count = Doctor.objects.filter(department=dept).count()
                existing_doctors_in_dept = list(Doctor.objects.filter(department=dept).values_list('name', flat=True))

                specialties = DOCTOR_SPECIALTIES.get(dept.name, ['General'])
                for i in range(2):
                    if doctor_count + i <= 1 or True:
                        name_idx = (len(doctor_names)) % len(FIRST_NAMES)
                        first = FIRST_NAMES[name_idx]
                        last = LAST_NAMES[(name_idx + len(doctor_names) // len(FIRST_NAMES)) % len(LAST_NAMES)]
                        full_name = f'Dr. {first} {last}'

                        if full_name in existing_doctors_in_dept:
                            continue

                        if prefix_idx >= len(avail):
                            self.stdout.write(self.style.WARNING('  No prefixes left, skipping remaining doctors'))
                            break

                        prefix = avail[prefix_idx]
                        prefix_idx += 1
                        specialty = specialties[i] if i < len(specialties) else specialties[0]

                        phone = f'98{1000000000 + len(doctor_names):09d}'[-10:]
                        user = User.objects.create(
                            phone=phone,
                            name=full_name,
                            role=User.Role.DOCTOR,
                            is_active=True,
                        )
                        user.set_unusable_password()
                        user.save()

                        doctor = Doctor.objects.create(
                            user=user,
                            name=full_name,
                            specialty=specialty,
                            department=dept,
                            qualification='MBBS, MD' if i == 0 else 'MBBS, DNB',
                            phone=phone,
                            email=f'{first.lower()}.{last.lower()}@careflow.com',
                            prefix=prefix,
                            days_available='Mon–Fri',
                            morning_slots='09:00–13:00',
                            evening_slots='17:00–19:00',
                            slots_per_day=25,
                            consultation_fee=500.00 if i == 0 else 350.00,
                            status='active',
                            is_active=True,
                        )

                        DoctorScheduleSettings.objects.create(
                            doctor=doctor,
                            slot_duration=10,
                            start_time=time(9, 0),
                            end_time=time(17, 0),
                            break_time=time(13, 0),
                            auto_advance=True,
                        )

                        created_doctors += 1
                        doctor_names.append(full_name)
                        self.stdout.write(f'  Created doctor: {full_name} ({dept.name}, prefix={prefix})')

        self.stdout.write(self.style.SUCCESS(f'\nDone: {created_depts} departments, {created_doctors} doctors created'))
