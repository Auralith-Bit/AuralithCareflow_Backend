from django.shortcuts import redirect


PROTECTED_PAGES = {
    '/reception/': {'receptionist', 'hospital_admin', 'super_admin'},
    '/admin-panel/': {'hospital_admin', 'super_admin'},
    '/super-admin/': {'super_admin'},
    '/admin/': {'super_admin'},
    '/patient/': {'patient'},
    '/doctor/': {'doctor', 'hospital_admin', 'super_admin'},
}


class PageAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        for prefix, allowed_roles in PROTECTED_PAGES.items():
            if request.path_info.startswith(prefix):
                if not request.user.is_authenticated:
                    return redirect('/login/')
                if request.user.role not in allowed_roles:
                    return redirect('/login/')
                break
        return self.get_response(request)
