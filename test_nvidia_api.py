"""
Test NVIDIA ALCHEMI API Integration
====================================
Quick test to verify NVIDIA ALCHEMI is working.
"""

import requests
import json

# Test the NVIDIA chat endpoint
url = "http://localhost:8001/api/nvidia/chat"
payload = {
    "question": "What is the best material for supercapacitor electrodes?",
    "context": None
}

print("Testing NVIDIA ALCHEMI Chat Endpoint...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print("\nSending request...")

try:
    response = requests.post(url, json=payload, timeout=60)
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("\n✅ NVIDIA ALCHEMI is working!")
    else:
        print(f"\n⚠️  Error: {response.status_code}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
