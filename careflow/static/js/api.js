const API = {
  BASE: '',

  getToken() {
    return localStorage.getItem('careflow_token');
  },

  setToken(token) {
    localStorage.setItem('careflow_token', token);
  },

  clearToken() {
    localStorage.removeItem('careflow_token');
  },

  getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  },

  headers(useJson = true) {
    const h = {};
    const token = this.getToken();
    if (token) h['Authorization'] = 'Bearer ' + token;
    if (useJson) h['Content-Type'] = 'application/json';
    const csrf = this.getCsrfToken();
    if (csrf) h['X-CSRFToken'] = csrf;
    return h;
  },

  async request(method, url, body = null) {
    const opts = { method, headers: this.headers(body !== null) };
    if (body !== null) opts.body = JSON.stringify(body);
    const res = await fetch(this.BASE + url, opts);
    if (res.status === 401) {
      this.clearToken();
      window.location.href = '/login/';
      throw new Error('Unauthorized');
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error || `HTTP ${res.status}`);
    }
    return res.json();
  },

  get(url) { return this.request('GET', url); },
  post(url, data) { return this.request('POST', url, data); },
  put(url, data) { return this.request('PUT', url, data); },
  patch(url, data) { return this.request('PATCH', url, data); },
  del(url) { return this.request('DELETE', url); },

  async checkPhone(phone) {
    const res = await fetch('/api/auth/check-phone/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCsrfToken() },
      body: JSON.stringify({ phone }),
    });
    if (!res.ok) throw new Error('Failed to check phone');
    return res.json();
  },

  async sendOTP(phone) {
    const res = await fetch('/api/auth/send-otp/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCsrfToken() },
      body: JSON.stringify({ phone }),
    });
    if (!res.ok) throw new Error('Failed to send OTP');
    return res.json();
  },

  async verifyOTP(phone, otp) {
    const res = await fetch('/api/auth/verify-otp/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCsrfToken() },
      body: JSON.stringify({ phone, otp }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || 'Invalid OTP');
    }
    const data = await res.json();
    this.setToken(data.access);
    return data;
  },

  async register(phone, first_name, last_name, email = '', role = 'patient') {
    const res = await fetch('/api/auth/register/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCsrfToken() },
      body: JSON.stringify({ phone, first_name, last_name, email, role }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || 'Registration failed');
    }
    const data = await res.json();
    this.setToken(data.access);
    return data;
  },

  async login(username, password) {
    const res = await fetch('/api/login/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) throw new Error('Invalid credentials');
    const data = await res.json();
    this.setToken(data.access);
    return data;
  },

  async getMe() {
    return this.get('/api/auth/me/');
  },

  // Reception APIs
  reception: {
    queue(params = '') { return API.get('/api/reception/queue/' + params); },
    queueStats() { return API.get('/api/reception/queue/stats/'); },
    queueDetail(id) { return API.get(`/api/reception/queue/${id}/`); },
    createEntry(data) { return API.post('/api/reception/queue/create/', data); },
    updateStatus(id, status) { return API.patch(`/api/reception/queue/${id}/status/`, { status }); },
    cancel(id, source) { return API.patch(`/api/reception/queue/${id}/cancel/`, { cancel_source: source || 'receptionist' }); },
    reschedule(id, data) { return API.patch(`/api/reception/queue/${id}/reschedule/`, data); },
    searchPatients(params) { return API.get('/api/reception/patients/search/?' + params); },
    checkPatient(phone) { return API.get('/api/reception/patients/check/?phone=' + encodeURIComponent(phone)); },
    nextToken(doctorId) { return API.get('/api/reception/tokens/next/?doctor_id=' + doctorId); },
    activity(limit = 10) { return API.get('/api/reception/activity/?limit=' + limit); },
    logActivity(msg, type) { return API.post('/api/reception/activity/', { message: msg, type }); },
    doctors() { return API.get('/api/reception/doctors/'); },
  },

  // Admin APIs
  admin: {
    departments() { return API.get('/api/admin/departments/'); },
    createDept(data) { return API.post('/api/admin/departments/', data); },
    updateDept(id, data) { return API.put(`/api/admin/departments/${id}/`, data); },
    deleteDept(id) { return API.del(`/api/admin/departments/${id}/`); },
    doctors(params = '') { return API.get('/api/admin/doctors/' + params); },
    doctorDetail(id) { return API.get(`/api/admin/doctors/${id}/`); },
    createDoctor(data) { return API.post('/api/admin/doctors/', data); },
    updateDoctor(id, data) { return API.put(`/api/admin/doctors/${id}/`, data); },
    deleteDoctor(id) { return API.del(`/api/admin/doctors/${id}/`); },
    hospitalProfile() { return API.get('/api/admin/hospital-profile/'); },
    updateHospitalProfile(data) { return API.put('/api/admin/hospital-profile/', data); },
    holidays(params = '') { return API.get('/api/admin/holidays/' + params); },
    createHoliday(data) { return API.post('/api/admin/holidays/', data); },
    deleteHoliday(id) { return API.del(`/api/admin/holidays/${id}/`); },
    slots(params = '') { return API.get('/api/admin/slots/' + params); },
    createSlot(data) { return API.post('/api/admin/slots/', data); },
    emergencyClosure(data) { return API.post('/api/admin/emergency-closures/', data); },
    users(params = '') { return API.get('/api/auth/users/' + params); },
    createStaff(data) { return API.post('/api/auth/create-staff/', data); },
    toggleUserStatus(id) { return API.patch(`/api/auth/users/${id}/toggle-status/`); },
    updateUser(id, data) { return API.patch(`/api/auth/users/${id}/update/`, data); },
    userDetail(id) { return API.get(`/api/auth/users/${id}/`); },
    updateUserGroups(id, groupIds) { return API.put(`/api/auth/users/${id}/groups/`, { groups: groupIds }); },
    userGroupMappings() { return API.get('/api/auth/user-group-mappings/'); },
    permissions() { return API.get('/api/auth/permissions/'); },
    groups() { return API.get('/api/auth/groups/'); },
    createGroup(data) { return API.post('/api/auth/groups/', data); },
    updateGroup(id, data) { return API.put(`/api/auth/groups/${id}/`, data); },
    deleteGroup(id) { return API.del(`/api/auth/groups/${id}/`); },
  },
};
