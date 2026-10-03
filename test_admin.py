import httpx
res = httpx.post("http://127.0.0.1:8000/api/v1/auth/login", data={"username": "admin@sevalor.com", "password": "superpassword"}, headers={"Host": "localhost"})
token = res.json()["access_token"]
res2 = httpx.get("http://127.0.0.1:8000/api/v1/superadmin/tenants", headers={"Authorization": "Bearer " + token, "Host": "localhost"})
print(res2.status_code)
print(res2.json())
