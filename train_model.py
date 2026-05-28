#!/usr/bin/env python3
"""Quick script to train the ML model."""
import requests

# Train model
response = requests.post(
    "http://localhost:8000/api/v2/material-id/train",
    json={"test_size": 0.2, "force_retrain": False}
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
