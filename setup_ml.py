#!/usr/bin/env python3
"""Setup ML model for workflows."""
import requests

# Load database
print("Loading materials database...")
response = requests.post(
    "http://localhost:8000/api/v2/material-id/database/load",
    params={"db_path": "data/materials_database.json"}
)
print(f"Load Status: {response.status_code}")
print(f"Response: {response.json()}")
print()

# Train model
print("Training ML model...")
response = requests.post(
    "http://localhost:8000/api/v2/material-id/train",
    json={"test_size": 0.2, "force_retrain": True}
)
print(f"Train Status: {response.status_code}")
print(f"Response: {response.json()}")
print()

# Check status
print("Checking status...")
response = requests.get("http://localhost:8000/api/v2/material-id/status")
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
