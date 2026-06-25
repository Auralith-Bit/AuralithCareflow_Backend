import requests, json, subprocess, time, sys

proc = subprocess.Popen([sys.executable, 'manage.py', 'runserver', '9997', '--noreload'],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(3)
BASE = 'http://127.0.0.1:9997'
phone = '+9779900990022'

# 1. Check phone
r = requests.post(BASE + '/api/auth/check-phone/', json={'phone': phone})
print(f'1. Check phone: {r.status_code}')

# 2. Register
r = requests.post(BASE + '/api/patient/register/', json={
    'phone': phone, 'first_name': 'Demo', 'last_name': 'User',
    'email': 'demo2@example.com', 'date_of_birth': '1985-06-20', 'address': 'Kathmandu'
})
print(f'2. Register: {r.status_code}')
data = r.json()
user = data.get('user', {})
print(f'   User role: {user.get("role")}')
print(f'   Profile: {data.get("profile", {}).get("date_of_birth")}')

# 3. Send OTP
r = requests.post(BASE + '/api/auth/send-otp/', json={'phone': phone})
otp = r.json().get('otp', '')
print(f'3. Send OTP: {r.status_code}, OTP={otp}')

# 4. Verify OTP
r = requests.post(BASE + '/api/auth/verify-otp/', json={'phone': phone, 'otp': otp})
data = r.json()
token = data.get('access', '')
print(f'4. Verify OTP: {r.status_code}, token={token[:40]}...')

# 5. Fetch profile
headers = {'Authorization': f'Bearer {token}'}
r = requests.get(BASE + '/api/patient/profile/', headers=headers)
print(f'5. Fetch profile: {r.status_code}')
profile_data = r.json()
print(f'   Body: {json.dumps(profile_data, indent=2)[:500]}')

proc.terminate()
proc.wait()
print('\nDONE')
