import requests
import json

# Test EIS identification
response = requests.post(
    "http://localhost:8000/api/v2/material-id/identify/eis",
    json={
        "frequencies": [0.01, 0.1, 1, 10, 100, 1000],
        "Z_real": [10, 15, 25, 35, 40, 42],
        "Z_imag": [0, -5, -15, -25, -10, -2],
        "top_k": 3
    }
)

print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
