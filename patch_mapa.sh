# Check if /gestio/feines works
curl -s -X GET http://127.0.0.1:8000/api/v1/gestio/feines -H "Authorization: Bearer mock" || echo "Fail"
