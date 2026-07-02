from django.shortcuts import render
from accounts.decorators import role_required


@role_required('super_admin')
def super_admin_dashboard(request):
    return render(request, 'super-admin.html')
