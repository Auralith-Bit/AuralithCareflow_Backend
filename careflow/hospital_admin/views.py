from datetime import timedelta, datetime
from collections import defaultdict
from rest_framework import viewsets, generics, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404
from accounts.decorators import role_required
from django.utils import timezone
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField
from accounts.permissions import IsHospitalAdmin
from rest_framework.permissions import IsAuthenticated
from accounts.models import User, Notification
from Patient.models import Appointment
from .models import Department, Doctor, HospitalProfile, Holiday, TimeSlot, EmergencyClosure
from .serializers import (
    DepartmentSerializer, DoctorSerializer, DoctorListSerializer,
    HospitalProfileSerializer, HolidaySerializer, TimeSlotSerializer,
    EmergencyClosureSerializer,
)
from reception.models import QueueEntry, ActivityLog


@role_required('hospital_admin', 'super_admin')
def admin_dashboard(request):
    return render(request, 'hospital-admin.html')


class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer
    search_fields = ['name']
    ordering_fields = ['name']
    permission_classes = [IsHospitalAdmin]

    def get_queryset(self):
        qs = Department.objects.all()
        if self.request.query_params.get('include_inactive') != 'true':
            qs = qs.filter(is_active=True)
        return qs

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        dept = get_object_or_404(Department, pk=pk)
        dept.is_active = True
        dept.save(update_fields=['is_active'])
        return Response(DepartmentSerializer(dept).data)


class DoctorViewSet(viewsets.ModelViewSet):
    search_fields = ['name', 'specialty', 'department__name']
    ordering_fields = ['name', 'status']
    permission_classes = [IsHospitalAdmin]

    def get_queryset(self):
        qs = Doctor.objects.all()
        if self.request.query_params.get('include_inactive') != 'true':
            qs = qs.filter(is_active=True)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return DoctorListSerializer
        return DoctorSerializer

    def perform_create(self, serializer):
        doctor = serializer.save()
        Notification.send(
            user=self.request.user,
            type='staff_added',
            title='👤 Doctor Created',
            message=f"Dr. {doctor.name} ({doctor.specialty}) added to {doctor.department.name if doctor.department else 'No department'}",
            icon='ti-user-plus',
            icon_color='ni-green',
        )
        for admin in User.objects.filter(role='hospital_admin', is_active=True).exclude(pk=self.request.user.pk):
            Notification.send(
                user=admin,
                type='staff_added',
                title='👤 Doctor Created',
                message=f"Dr. {doctor.name} ({doctor.specialty}) added to {doctor.department.name if doctor.department else 'No department'} by {self.request.user.name}",
                icon='ti-user-plus',
                icon_color='ni-green',
            )
        if not doctor.user:
            employee_id = User.generate_employee_id('doctor')
            user = User(
                phone=doctor.phone or '',
                name=doctor.name,
                email=doctor.email or '',
                role='doctor',
                employee_id=employee_id,
            )
            user.save()
            doctor.user = user
            doctor.save(update_fields=['user'])
        self._sync_time_slots(doctor)

    def perform_update(self, serializer):
        doctor = serializer.save()
        if doctor.user:
            user = doctor.user
            user.name = doctor.name
            user.phone = doctor.phone or ''
            user.email = doctor.email or ''
            user.save(update_fields=['name', 'phone', 'email'])
        self._sync_time_slots(doctor)

    def perform_destroy(self, instance):
        if instance.user:
            instance.user.is_active = False
            instance.user.save(update_fields=['is_active'])
        instance.is_active = False
        instance.save(update_fields=['is_active'])

    @action(detail=True, methods=['get'])
    def booked_times(self, request, pk=None):
        doctor = self.get_object()
        date_str = request.query_params.get('date')
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.now().date()
        except ValueError:
            return Response({'error': 'Invalid date format, use YYYY-MM-DD'}, status=400)
        appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=selected_date,
            status__in=['pending', 'confirmed', 'scheduled', 'rescheduled'],
        ).values_list('appointment_time', flat=True)
        queue_entries = QueueEntry.objects.filter(
            doctor=doctor,
            scheduled_date=selected_date,
            status__in=['waiting', 'arrived', 'serving'],
        ).values_list('time', flat=True)
        booked = set()
        for t in appointments:
            if t:
                booked.add(t.strftime('%H:%M'))
        for t in queue_entries:
            if t:
                booked.add(t.strftime('%H:%M'))
        return Response(sorted(booked))

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        doctor = get_object_or_404(Doctor, pk=pk)
        doctor.is_active = True
        doctor.save(update_fields=['is_active'])
        if doctor.user:
            doctor.user.is_active = True
            doctor.user.save(update_fields=['is_active'])
        return Response(DoctorSerializer(doctor).data)

    def _sync_time_slots(self, doctor):
        TimeSlot.objects.filter(doctor=doctor).delete()
        slots = []
        day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
        days_str = (doctor.days_available or '').lower()
        selected_days = [num for abbr, num in day_map.items() if abbr in days_str]
        if not selected_days:
            selected_days = list(range(5))
        for range_str in [doctor.day_slots, doctor.night_slots]:
            if not range_str:
                continue
            sep = '–' if '–' in range_str else '-' if '-' in range_str else None
            if not sep:
                continue
            parts = range_str.split(sep)
            if len(parts) != 2:
                continue
            try:
                start = datetime.strptime(parts[0].strip(), '%H:%M').time()
                end = datetime.strptime(parts[1].strip(), '%H:%M').time()
            except ValueError:
                continue
            for day in selected_days:
                slots.append(TimeSlot(
                    doctor=doctor, day_of_week=day,
                    start_time=start, end_time=end,
                    max_patients=doctor.slots_per_day or 20
                ))
        if slots:
            TimeSlot.objects.bulk_create(slots)


class HospitalProfileView(generics.RetrieveUpdateAPIView):
    queryset = HospitalProfile.objects.all()
    serializer_class = HospitalProfileSerializer
    permission_classes = [IsHospitalAdmin]

    def get_object(self):
        return HospitalProfile.get_profile()


class HolidayViewSet(viewsets.ModelViewSet):
    queryset = Holiday.objects.filter(is_active=True)
    serializer_class = HolidaySerializer
    ordering_fields = ['date']
    ordering = ['date']
    permission_classes = [IsHospitalAdmin]

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()


class TimeSlotViewSet(viewsets.ModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsHospitalAdmin]

    def get_queryset(self):
        qs = TimeSlot.objects.all()
        doctor_id = self.request.query_params.get('doctor')
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)
        return qs


class EmergencyClosureViewSet(viewsets.ModelViewSet):
    queryset = EmergencyClosure.objects.filter(is_active=True)
    serializer_class = EmergencyClosureSerializer
    permission_classes = [IsHospitalAdmin]

    def perform_create(self, serializer):
        closure = serializer.save(created_by=self.request.user)
        Notification.send(
            user=self.request.user,
            type='closure',
            title='🚧 Emergency Closure',
            message=f"OPD closure activated{' for ' + closure.department.name if closure.department else ''}: {closure.reason or 'No reason provided'}",
            icon='ti-lock',
            icon_color='ni-red',
        )
        for rec in User.objects.filter(role='receptionist', is_active=True).exclude(pk=self.request.user.pk):
            Notification.send(
                user=rec,
                type='closure',
                title='🚧 OPD Closure Active',
                message=f"OPD closed by {self.request.user.name}: {closure.reason or 'No reason provided'}. Stop issuing tokens.",
                icon='ti-lock',
                icon_color='ni-red',
            )


class DashboardStatsView(generics.GenericAPIView):
    permission_classes = [IsHospitalAdmin]

    def get(self, request):
        now = timezone.now()
        today_date = now.date()
        today_start = timezone.make_aware(datetime.combine(today_date, datetime.min.time()))
        today_end = today_start + timedelta(days=1)
        week_start_date = today_date - timedelta(days=today_date.weekday())
        week_start = timezone.make_aware(datetime.combine(week_start_date, datetime.min.time()))
        week_end = week_start + timedelta(days=7)

        # ── Range parameter (for Reports & Analytics filtering) ──
        range_param = request.query_params.get('range', 'weekly')
        if range_param == 'daily':
            period_start = today_start
            period_end = today_end
        elif range_param == 'monthly':
            month_start_date = today_date.replace(day=1)
            next_month_date = (month_start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            period_start = timezone.make_aware(datetime.combine(month_start_date, datetime.min.time()))
            period_end = timezone.make_aware(datetime.combine(next_month_date, datetime.min.time()))
        else:
            period_start = week_start
            period_end = week_end

        # ── Totals ──
        total_doctors = Doctor.objects.filter(is_active=True).count()
        total_departments = Department.objects.filter(is_active=True).count()
        all_departments = list(Department.objects.filter(is_active=True).values_list('name', flat=True))
        total_staff = User.objects.exclude(role__in=['patient', 'super_admin']).count()

        # ── Queue today ──
        today_qs = QueueEntry.objects.filter(created_at__gte=today_start, created_at__lt=today_end).select_related('doctor__department')
        patients_today = today_qs.count()

        # ── Avg wait time (today) ──
        done_today = today_qs.filter(status__in=['done', 'serving'])
        avg_wait_seconds = done_today.aggregate(
            avg=Avg(ExpressionWrapper(F('updated_at') - F('created_at'), output_field=DurationField()))
        )['avg']
        if avg_wait_seconds is not None:
            avg_wait_min = int(avg_wait_seconds.total_seconds() // 60)
        else:
            avg_wait_min = None

        # ── Weekly OPD ──
        week_qs = QueueEntry.objects.filter(created_at__gte=week_start, created_at__lt=week_end)
        weekday_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        weekly_raw = defaultdict(int)
        for entry in week_qs:
            wd = entry.created_at.astimezone(timezone.get_current_timezone()).weekday()
            weekly_raw[wd] += 1
        weekly_values = [weekly_raw.get(i, 0) for i in range(7)]
        weekly_total = sum(weekly_values)
        weekly_avg = round(weekly_total / 7, 1) if weekly_total else 0
        peak_idx = weekly_values.index(max(weekly_values)) if weekly_values else 0
        weekly_opd = {
            'labels': weekday_names,
            'values': weekly_values,
            'total': weekly_total,
            'average': weekly_avg,
            'peak_day': weekday_names[peak_idx],
            'peak_value': max(weekly_values) if weekly_values else 0,
        }

        # ── Department load today ──
        dept_raw = defaultdict(int)
        for entry in today_qs:
            name = entry.doctor.department.name if entry.doctor and entry.doctor.department else 'Unknown'
            dept_raw[name] += 1
        total_dept = sum(dept_raw.values()) or 1
        dept_colors = ['#52b788', '#4361ee', '#f4a261', '#7209b7', '#e63946', '#e9c46a']
        dept_load = []
        for i, (name, count) in enumerate(sorted(dept_raw.items(), key=lambda x: -x[1])):
            dept_load.append({
                'name': name,
                'count': count,
                'percentage': round(count / total_dept * 100),
                'color': dept_colors[i % len(dept_colors)],
            })

        # ── Doctors on duty ──
        active_doctors = Doctor.objects.filter(is_active=True, status='active')
        doctors_on_duty = []
        for doc in active_doctors:
            name_parts = doc.name.split()
            initials = ''.join(p[0] for p in name_parts if p)[:2].upper()
            doctors_on_duty.append({
                'id': doc.id,
                'name': doc.name,
                'specialty': doc.specialty,
                'initials': initials,
                'avatar_color': doc.avatar_color or 'av-1',
                'status': doc.status,
                'department': doc.department.name if doc.department else '',
            })

        # ── Range-aware period queryset (for Reports & Analytics) ──
        range_qs = QueueEntry.objects.filter(created_at__gte=period_start, created_at__lt=period_end).select_related('doctor__department')

        # ── Range OPD grouping ──
        if range_param == 'daily':
            range_labels = ['8 AM', '9 AM', '10 AM', '11 AM', '12 PM', '1 PM', '2 PM', '3 PM', '4 PM', '5 PM']
            range_raw = defaultdict(int)
            for entry in range_qs:
                local_time = entry.created_at.astimezone(timezone.get_current_timezone())
                h = local_time.hour
                if 8 <= h <= 17:
                    range_raw[h] += 1
            range_values = [range_raw.get(h, 0) for h in range(8, 18)]
            range_total = sum(range_values)
            range_avg = round(range_total / (len([v for v in range_values if v > 0]) or 1), 1) if range_total else 0
        elif range_param == 'monthly':
            range_labels = ['Wk 1', 'Wk 2', 'Wk 3', 'Wk 4', 'Wk 5']
            range_raw = defaultdict(int)
            for entry in range_qs:
                local_time = entry.created_at.astimezone(timezone.get_current_timezone())
                wk = (local_time.day - 1) // 7 + 1
                range_raw[wk] += 1
            range_values = [range_raw.get(i, 0) for i in range(1, 6)]
            range_total = sum(range_values)
            weeks_with_data = len([v for v in range_values if v > 0]) or 1
            range_avg = round(range_total / weeks_with_data, 1) if range_total else 0
        else:
            range_labels = weekday_names
            range_values = weekly_values
            range_total = weekly_total
            range_avg = weekly_avg

        range_peak_idx = range_values.index(max(range_values)) if range_values else 0
        range_opd = {
            'labels': range_labels,
            'values': range_values,
            'total': range_total,
            'average': range_avg,
            'peak_day': range_labels[range_peak_idx] if range_values else '',
            'peak_value': max(range_values) if range_values else 0,
        }

        # ── OPD by doctor (range period) ──
        doc_raw = defaultdict(int)
        for entry in range_qs:
            doc_raw[entry.doctor_id] += 1
        opd_by_doctor = []
        doc_ids_in_data = set(doc_raw.keys())
        all_docs = {d.id: d for d in active_doctors}
        max_doc_count = max(doc_raw.values()) if doc_raw else 1
        for doc_id, count in sorted(doc_raw.items(), key=lambda x: -x[1]):
            doc = all_docs.get(doc_id)
            if doc:
                name_parts = doc.name.split()
                initials = ''.join(p[0] for p in name_parts if p)[:2].upper()
                opd_by_doctor.append({
                    'name': doc.name,
                    'initials': initials,
                    'avatar_color': doc.avatar_color or 'av-1',
                    'department': doc.department.name if doc.department else '',
                    'count': count,
                    'percentage': round(count / max_doc_count * 100),
                })
            else:
                opd_by_doctor.append({
                    'name': f'Doctor #{doc_id}',
                    'initials': 'DR',
                    'avatar_color': 'av-1',
                    'count': count,
                    'percentage': round(count / max_doc_count * 100),
                })

        # ── Department OPD share (range period) ──
        dept_share_raw = defaultdict(int)
        for entry in range_qs:
            name = entry.doctor.department.name if entry.doctor and entry.doctor.department else 'Unknown'
            dept_share_raw[name] += 1
        total_share = sum(dept_share_raw.values()) or 1
        dept_share_colors = ['#52b788', '#4361ee', '#f4a261', '#7209b7', '#e63946', '#e9c46a']
        dept_shares = []
        for i, (name, count) in enumerate(sorted(dept_share_raw.items(), key=lambda x: -x[1])):
            dept_shares.append({
                'name': name,
                'count': count,
                'percentage': round(count / total_share * 100),
                'color': dept_share_colors[i % len(dept_share_colors)],
            })
        opd_share = {
            'total': total_share,
            'departments': dept_shares,
        }

        # ── Range stats (for Reports & Analytics cards) ──
        range_patients = range_qs.count()
        range_done = range_qs.filter(status__in=['done', 'serving'])
        range_avg_wait_secs = range_done.aggregate(
            avg=Avg(ExpressionWrapper(F('updated_at') - F('created_at'), output_field=DurationField()))
        )['avg']
        range_avg_wait = int(range_avg_wait_secs.total_seconds() // 60) if range_avg_wait_secs else None
        range_cancelled = range_qs.filter(status='cancelled').count()
        range_cancellation_rate = round(range_cancelled / range_patients * 100, 1) if range_patients else 0

        # ── Wait time trend (last 4 weeks) ──
        wait_labels = []
        wait_values = []
        for w in range(4):
            w_start = week_start - timedelta(weeks=3 - w)
            w_end = w_start + timedelta(days=7)
            qs = QueueEntry.objects.filter(
                created_at__gte=w_start,
                created_at__lt=w_end,
                status__in=['done', 'serving'],
            )
            avg_secs = qs.aggregate(
                avg=Avg(ExpressionWrapper(F('updated_at') - F('created_at'), output_field=DurationField()))
            )['avg']
            wait_mins = int(avg_secs.total_seconds() // 60) if avg_secs else 0
            wait_labels.append(f'W{w+1}')
            wait_values.append(wait_mins)
        wait_time_trend = {
            'labels': wait_labels,
            'values': wait_values,
        }

        # ── Heatmap data (last 4 weeks) ──
        four_weeks_ago = today_date - timedelta(days=28)
        four_weeks_ago_dt = timezone.make_aware(datetime.combine(four_weeks_ago, datetime.min.time()))
        heat_qs = QueueEntry.objects.filter(created_at__gte=four_weeks_ago_dt)
        hours = ['8 AM', '9 AM', '10 AM', '11 AM', '12 PM', '1 PM', '2 PM', '3 PM', '4 PM', '5 PM']
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        heat = [[0] * 7 for _ in range(10)]
        for entry in heat_qs:
            local_time = entry.created_at.astimezone(timezone.get_current_timezone())
            wd = local_time.weekday()
            h = local_time.hour
            if 8 <= h <= 17:
                heat[h - 8][wd] += 1
        heatmap_data = {'hours': hours, 'days': days, 'data': heat}

        # ── Recent activity ──
        recent_logs = ActivityLog.objects.all()[:5]
        recent_activity = []
        for log in recent_logs:
            delta = now - log.timestamp
            if delta.days > 0:
                time_ago = f'{delta.days} day{"s" if delta.days > 1 else ""} ago'
            elif delta.seconds >= 3600:
                hrs = delta.seconds // 3600
                time_ago = f'{hrs} hour{"s" if hrs > 1 else ""} ago'
            elif delta.seconds >= 60:
                mins = delta.seconds // 60
                time_ago = f'{mins} minute{"s" if mins > 1 else ""} ago'
            else:
                time_ago = 'just now'
            icon_map = {
                'cancel': '🚨', 'checkin': '🆕', 'issue': '📋', 'reception': '👥',
            }
            recent_activity.append({
                'icon': icon_map.get(log.type, '📋'),
                'message': log.message,
                'time_ago': time_ago,
                'type': log.type,
            })

        # ── Quick metrics ──
        cancelled_today = today_qs.filter(status='cancelled').count()
        cancellation_rate = round(cancelled_today / patients_today * 100, 1) if patients_today else 0
        yesterday_start = today_start - timedelta(days=1)
        yesterday_count = QueueEntry.objects.filter(created_at__gte=yesterday_start, created_at__lt=today_start).count()
        daily_change_val = round((patients_today - yesterday_count) / (yesterday_count or 1) * 100, 1)

        return Response({
            'total_doctors': total_doctors,
            'total_staff': total_staff,
            'total_departments': total_departments,
            'all_departments': all_departments,
            'patients_today': patients_today,
            'avg_wait_time': avg_wait_min,
            'doctors_on_duty': doctors_on_duty,
            'weekly_opd': weekly_opd,
            'dept_load': dept_load,
            'recent_activity': recent_activity,
            'opd_by_doctor': opd_by_doctor,
            'opd_share': opd_share,
            'wait_time_trend': wait_time_trend,
            'heatmap_data': heatmap_data,
            'cancellation_rate': cancellation_rate,
            'cancelled_today': cancelled_today,
            'daily_change': daily_change_val,
            # Range-aware fields (for Reports & Analytics filtering)
            'range_opd': range_opd,
            'range_patients': range_patients,
            'range_avg_wait': range_avg_wait,
            'range_cancellation_rate': range_cancellation_rate,
        })
