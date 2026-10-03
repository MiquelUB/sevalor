import requests

res = requests.post("http://127.0.0.1:8000/api/v1/auth/login", data={"username": "admin@sevalor.com", "password": "superpassword"})
print(res.status_code)
print(res.json())

res2 = requests.get("http://127.0.0.1:8000/api/v1/superadmin/telemetria/kpis", headers={"Authorization": "Bearer " + res.json()["access_token"]})
print(res2.status_code)
print(res2.text)
