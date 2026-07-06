from django.shortcuts import redirect

PUBLIC_PATHS = (
    '/login/',
    '/staff/',
    '/admin/',
)

PROTECTED_PAGES = {
    '/reception/': {'receptionist', 'hospital_admin', 'super_admin'},
    '/hospital-admin/': {'hospital_admin', 'super_admin'},
    '/super-admin/': {'super_admin'},
    '/patient/': {'patient'},
    '/doctor/': {'doctor', 'hospital_admin', 'super_admin'},
}


class PageAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if path.startswith(PUBLIC_PATHS):
            return self.get_response(request)
        for prefix, allowed_roles in PROTECTED_PAGES.items():
            if path.startswith(prefix):
                if not request.user.is_authenticated:
                    return redirect('/login/')
                if request.user.role not in allowed_roles:
                    return redirect('/login/')
                break
        return self.get_response(request)
