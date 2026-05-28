#!/usr/bin/env python3
"""
Test ML API Endpoints
======================
Quick test script to verify ML prediction endpoints are working.

Usage:
    python test_ml_api.py
"""

import requests
import numpy as np
import time

# API base URL
BASE_URL = "http://localhost:8000"

def test_model_status():
    """Test model status endpoint"""
    print("\n" + "="*80)
    print("TEST 1: Model Status")
    print("="*80)
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/ml/models/status")
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Status endpoint working")
        print(f"   Model loaded: {data['cv_transformer']['loaded']}")
        print(f"   Device: {data['cv_transformer']['device']}")
        print(f"   Parameters: {data['cv_transformer']['parameters']:,}")
        return True
    except Exception as e:
        print(f"❌ Status endpoint failed: {e}")
        return False


def test_model_info():
    """Test model info endpoint"""
    print("\n" + "="*80)
    print("TEST 2: Model Info")
    print("="*80)
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/ml/models/info")
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Info endpoint working")
        print(f"   Model: {data['cv_transformer']['name']}")
        print(f"   Version: {data['cv_transformer']['version']}")
        print(f"   Architecture: {data['cv_transformer']['architecture']}")
        print(f"   Mean inference time: {data['cv_transformer']['performance']['mean_inference_time_ms']:.2f} ms")
        return True
    except Exception as e:
        print(f"❌ Info endpoint failed: {e}")
        return False


def test_cv_prediction():
    """Test CV prediction endpoint"""
    print("\n" + "="*80)
    print("TEST 3: CV Prediction")
    print("="*80)
    
    # Generate synthetic CV data
    voltage = np.linspace(-0.5, 0.5, 100).tolist()
    current = (np.sin(np.linspace(0, 4*np.pi, 100)) * 0.5).tolist()
    
    try:
        start_time = time.time()
        
        response = requests.post(
            f"{BASE_URL}/api/v1/ml/predict/cv",
            json={
                "voltage": voltage,
                "current": current
            }
        )
        response.raise_for_status()
        
        elapsed = (time.time() - start_time) * 1000
        
        data = response.json()
        print(f"✅ Prediction endpoint working")
        print(f"   Mechanism: {data['mechanism_name']}")
        print(f"   Mechanism class: {data['mechanism_class']}")
        print(f"   Reversibility: {data['reversibility']:.4f} ({data['reversibility_category']})")
        print(f"   Inference time: {data['inference_time_ms']:.2f} ms")
        print(f"   Total API time: {elapsed:.2f} ms")
        print(f"   Peaks detected: {len(data['peaks'])}")
        print(f"   Parameters: {len(data['parameters'])}")
        print(f"   Species embedding: {len(data['species'])} dimensions")
        return True
    except Exception as e:
        print(f"❌ Prediction endpoint failed: {e}")
        return False


def test_invalid_input():
    """Test error handling with invalid input"""
    print("\n" + "="*80)
    print("TEST 4: Error Handling")
    print("="*80)
    
    # Test with mismatched array lengths
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/ml/predict/cv",
            json={
                "voltage": [1, 2, 3],
                "current": [1, 2]  # Different length
            }
        )
        
        if response.status_code == 400:
            print(f"✅ Error handling working")
            print(f"   Status code: {response.status_code}")
            print(f"   Error message: {response.json()['detail']}")
            return True
        else:
            print(f"❌ Expected 400 error, got {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False


def test_performance():
    """Test prediction performance with multiple requests"""
    print("\n" + "="*80)
    print("TEST 5: Performance")
    print("="*80)
    
    # Generate test data
    voltage = np.linspace(-0.5, 0.5, 100).tolist()
    current = (np.sin(np.linspace(0, 4*np.pi, 100)) * 0.5).tolist()
    
    num_requests = 10
    times = []
    
    try:
        print(f"   Running {num_requests} predictions...")
        
        for i in range(num_requests):
            start_time = time.time()
            
            response = requests.post(
                f"{BASE_URL}/api/v1/ml/predict/cv",
                json={"voltage": voltage, "current": current}
            )
            response.raise_for_status()
            
            elapsed = (time.time() - start_time) * 1000
            times.append(elapsed)
        
        mean_time = np.mean(times)
        std_time = np.std(times)
        min_time = np.min(times)
        max_time = np.max(times)
        
        print(f"✅ Performance test complete")
        print(f"   Requests: {num_requests}")
        print(f"   Mean time: {mean_time:.2f} ms")
        print(f"   Std dev: {std_time:.2f} ms")
        print(f"   Min time: {min_time:.2f} ms")
        print(f"   Max time: {max_time:.2f} ms")
        print(f"   Throughput: {1000 / mean_time:.2f} requests/second")
        return True
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("="*80)
    print("ML API TEST SUITE")
    print("="*80)
    print(f"Testing API at: {BASE_URL}")
    
    results = []
    
    # Run tests
    results.append(("Model Status", test_model_status()))
    results.append(("Model Info", test_model_info()))
    results.append(("CV Prediction", test_cv_prediction()))
    results.append(("Error Handling", test_invalid_input()))
    results.append(("Performance", test_performance()))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:20s} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! ML API is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    exit(main())
