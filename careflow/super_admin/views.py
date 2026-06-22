from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def super_admin_dashboard(request):
    return render(request, 'super-admin.html')
