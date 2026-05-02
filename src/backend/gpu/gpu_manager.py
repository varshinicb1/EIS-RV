"""
Secure GPU Manager for RTX 4050
================================
Manages CUDA/GPU acceleration with safety checks and resource limits

SECURITY FEATURES:
- Memory safety checks
- Resource limits
- Automatic cleanup
- Error handling
- Performance monitoring
"""

import torch
import platform
import subprocess
from typing import Dict, Optional, List
from dataclasses import dataclass
import logging
import psutil

logger = logging.getLogger(__name__)


@dataclass
class GPUInfo:
    """GPU information"""
    name: str
    compute_capability: tuple
    total_memory: int  # bytes
    available_memory: int  # bytes
    cuda_version: str
    driver_version: str
    device_id: int


class GPUManager:
    """Secure GPU manager with safety checks"""
    
    # Maximum memory usage (80% of available)
    MAX_MEMORY_USAGE = 0.8
    
    # Minimum free memory (512 MB)
    MIN_FREE_MEMORY = 512 * 1024 * 1024
    
    def __init__(self):
        self.cuda_available = torch.cuda.is_available()
        self.device = None
        self.gpu_info = None
        self._initialize()
    
    def _initialize(self):
        """Initialize GPU detection with error handling"""
        try:
            if self.cuda_available:
                self.device = torch.device("cuda:0")
                self.gpu_info = self._get_gpu_info()
                
                if self.gpu_info:
                    logger.info(f"✅ GPU Detected: {self.gpu_info.name}")
                    logger.info(f"   CUDA Version: {self.gpu_info.cuda_version}")
                    logger.info(f"   Memory: {self.gpu_info.total_memory / 1e9:.2f} GB")
                    
                    # Check if GPU is healthy
                    if not self._check_gpu_health():
                        logger.warning("⚠️  GPU health check failed, using CPU")
                        self.cuda_available = False
                        self.device = torch.device("cpu")
            else:
                self.device = torch.device("cpu")
                logger.warning("⚠️  No GPU detected, using CPU")
        except Exception as e:
            logger.error(f"GPU initialization error: {e}")
            self.cuda_available = False
            self.device = torch.device("cpu")
    
    def _check_gpu_health(self) -> bool:
        """Check if GPU is healthy and responsive"""
        try:
            # Try a simple operation
            test_tensor = torch.randn(100, 100, device=self.device)
            result = torch.matmul(test_tensor, test_tensor)
            torch.cuda.synchronize()
            
            # Clean up
            del test_tensor, result
            torch.cuda.empty_cache()
            
            return True
        except Exception as e:
            logger.error(f"GPU health check failed: {e}")
            return False
    
    def _get_gpu_info(self) -> Optional[GPUInfo]:
        """Get detailed GPU information with error handling"""
        if not self.cuda_available:
            return None
        
        try:
            device_id = 0
            props = torch.cuda.get_device_properties(device_id)
            
            return GPUInfo(
                name=props.name,
                compute_capability=(props.major, props.minor),
                total_memory=props.total_memory,
                available_memory=torch.cuda.mem_get_info()[0],
                cuda_version=torch.version.cuda or "Unknown",
                driver_version=self._get_driver_version(),
                device_id=device_id
            )
        except Exception as e:
            logger.error(f"Failed to get GPU info: {e}")
            return None
    
    def _get_driver_version(self) -> str:
        """Get NVIDIA driver version safely"""
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
            
            if result.returncode == 0:
                return result.stdout.strip()
            return "Unknown"
        except Exception:
            return "Unknown"
    
    def get_device(self) -> torch.device:
        """Get the current device (GPU or CPU)"""
        return self.device
    
    def is_gpu_available(self) -> bool:
        """Check if GPU is available and healthy"""
        return self.cuda_available and self.gpu_info is not None
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current GPU memory usage safely"""
        if not self.cuda_available:
            return {
                "allocated": 0,
                "reserved": 0,
                "free": 0,
                "total": 0,
                "utilization_percent": 0
            }
        
        try:
            allocated = torch.cuda.memory_allocated() / 1e9  # GB
            reserved = torch.cuda.memory_reserved() / 1e9  # GB
            free = torch.cuda.mem_get_info()[0] / 1e9  # GB
            total = self.gpu_info.total_memory / 1e9 if self.gpu_info else 0
            
            utilization = (allocated / total * 100) if total > 0 else 0
            
            return {
                "allocated": round(allocated, 2),
                "reserved": round(reserved, 2),
                "free": round(free, 2),
                "total": round(total, 2),
                "utilization_percent": round(utilization, 1)
            }
        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")
            return {
                "allocated": 0,
                "reserved": 0,
                "free": 0,
                "total": 0,
                "utilization_percent": 0
            }
    
    def check_memory_available(self, required_bytes: int) -> bool:
        """Check if enough memory is available"""
        if not self.cuda_available:
            return False
        
        try:
            free_memory = torch.cuda.mem_get_info()[0]
            return free_memory >= required_bytes + self.MIN_FREE_MEMORY
        except:
            return False
    
    def clear_cache(self):
        """Clear GPU cache safely"""
        if self.cuda_available:
            try:
                torch.cuda.empty_cache()
                logger.info("🧹 GPU cache cleared")
            except Exception as e:
                logger.error(f"Failed to clear cache: {e}")
    
    def optimize_for_inference(self):
        """Optimize GPU settings for inference"""
        if self.cuda_available:
            try:
                torch.backends.cudnn.benchmark = True
                torch.backends.cudnn.deterministic = False
                logger.info("⚡ GPU optimized for inference")
            except Exception as e:
                logger.error(f"Failed to optimize for inference: {e}")
    
    def optimize_for_training(self):
        """Optimize GPU settings for training"""
        if self.cuda_available:
            try:
                torch.backends.cudnn.benchmark = False
                torch.backends.cudnn.deterministic = True
                logger.info("🎯 GPU optimized for training")
            except Exception as e:
                logger.error(f"Failed to optimize for training: {e}")
    
    def to_gpu(self, tensor: torch.Tensor) -> torch.Tensor:
        """Move tensor to GPU if available"""
        try:
            return tensor.to(self.device)
        except Exception as e:
            logger.error(f"Failed to move tensor to GPU: {e}")
            return tensor
    
    def to_cpu(self, tensor: torch.Tensor) -> torch.Tensor:
        """Move tensor to CPU safely"""
        try:
            return tensor.cpu()
        except Exception as e:
            logger.error(f"Failed to move tensor to CPU: {e}")
            return tensor
    
    def get_status(self) -> Dict:
        """Get comprehensive GPU status"""
        if not self.cuda_available or not self.gpu_info:
            return {
                "available": False,
                "device": "CPU",
                "message": "No GPU detected or GPU unhealthy"
            }
        
        memory = self.get_memory_usage()
        
        return {
            "available": True,
            "device": "GPU",
            "name": self.gpu_info.name,
            "cuda_version": self.gpu_info.cuda_version,
            "driver_version": self.gpu_info.driver_version,
            "compute_capability": f"{self.gpu_info.compute_capability[0]}.{self.gpu_info.compute_capability[1]}",
            "memory": memory,
            "healthy": self._check_gpu_health()
        }
    
    def benchmark(self) -> Dict[str, float]:
        """Run GPU benchmark with memory safety"""
        if not self.cuda_available:
            return {"error": "No GPU available"}
        
        logger.info("🏃 Running GPU benchmark...")
        
        try:
            # Check available memory
            free_memory = torch.cuda.mem_get_info()[0]
            
            # Calculate safe matrix size
            # Each matrix needs size*size*4 bytes (float32)
            # We need 2 matrices + result
            required_memory_per_element = 4 * 3  # 3 matrices
            max_size = int((free_memory * self.MAX_MEMORY_USAGE / required_memory_per_element) ** 0.5)
            
            # Limit to reasonable size
            size = min(max_size, 4096)
            
            if size < 512:
                return {"error": "Insufficient GPU memory for benchmark"}
            
            logger.info(f"   Using matrix size: {size}x{size}")
            
            iterations = 100
            
            # Warmup
            a = torch.randn(size, size, device=self.device)
            b = torch.randn(size, size, device=self.device)
            _ = torch.matmul(a, b)
            torch.cuda.synchronize()
            
            # Benchmark
            import time
            start = time.time()
            for _ in range(iterations):
                c = torch.matmul(a, b)
            torch.cuda.synchronize()
            end = time.time()
            
            elapsed = end - start
            gflops = (2 * size**3 * iterations) / (elapsed * 1e9)
            
            # Clean up
            del a, b, c
            torch.cuda.empty_cache()
            
            return {
                "matrix_size": size,
                "iterations": iterations,
                "elapsed_seconds": round(elapsed, 3),
                "gflops": round(gflops, 2),
                "avg_time_ms": round((elapsed / iterations) * 1000, 2),
                "memory_used_gb": round((size * size * 4 * 3) / 1e9, 2)
            }
            
        except Exception as e:
            logger.error(f"Benchmark failed: {e}")
            # Clean up on error
            torch.cuda.empty_cache()
            return {"error": str(e)}
    
    def get_system_info(self) -> Dict:
        """Get system information"""
        try:
            return {
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_total_gb": round(psutil.virtual_memory().total / 1e9, 2),
                "memory_available_gb": round(psutil.virtual_memory().available / 1e9, 2),
                "memory_percent": psutil.virtual_memory().percent,
                "platform": platform.system(),
                "platform_version": platform.version(),
                "python_version": platform.python_version()
            }
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            return {}


# Global GPU manager instance
_gpu_manager = None


def get_gpu_manager() -> GPUManager:
    """Get global GPU manager instance"""
    global _gpu_manager
    if _gpu_manager is None:
        _gpu_manager = GPUManager()
    return _gpu_manager


def is_rtx_4050() -> bool:
    """Check if RTX 4050 is detected"""
    manager = get_gpu_manager()
    if manager.gpu_info:
        return "4050" in manager.gpu_info.name
    return False


if __name__ == "__main__":
    # Test secure GPU manager
    logging.basicConfig(level=logging.INFO)
    
    manager = get_gpu_manager()
    print("\n" + "=" * 60)
    print("SECURE GPU MANAGER TEST")
    print("=" * 60)
    
    status = manager.get_status()
    print(f"\n📊 GPU Status:")
    for key, value in status.items():
        print(f"   {key}: {value}")
    
    if manager.is_gpu_available():
        print(f"\n🏃 Running benchmark...")
        benchmark = manager.benchmark()
        print(f"\n📈 Benchmark Results:")
        for key, value in benchmark.items():
            print(f"   {key}: {value}")
    
    system_info = manager.get_system_info()
    print(f"\n💻 System Info:")
    for key, value in system_info.items():
        print(f"   {key}: {value}")
    
    print("\n✅ Secure GPU Manager initialized successfully")
