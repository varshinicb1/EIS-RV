import unittest
import numpy as np
import logging
from unittest.mock import patch

from src.backend.core.engines.battery_engine import BatteryConfig, simulate_battery
from src.backend.core.engines.cv_engine import CVParameters, simulate_cv
from src.backend.core.engines.raman_engine import RamanAnalyzer, RamanSpectrum

logging.basicConfig(level=logging.ERROR)

class TestScientificIntegrations(unittest.TestCase):

    def test_battery_engine_fallback(self):
        """Test battery engine falls back gracefully when PyBaMM is missing."""
        config = BatteryConfig(chemistry="LiFePO4", C_rate=1.0)
        
        with patch('src.backend.core.engines.battery_engine.HAS_PYBAMM', False):
            result = simulate_battery(config)
            self.assertGreater(result.theoretical_capacity_mAh, 0)
            self.assertGreater(len(result.discharge_V), 0)

    def test_cv_engine_fallback(self):
        """Test CV engine falls back gracefully when pyMECSim is missing."""
        params = CVParameters()
        
        with patch('src.backend.core.engines.cv_engine.HAS_PYMECSIM', False):
            result = simulate_cv(params, use_mecsim=True)
            self.assertGreater(len(result.E), 0)
            self.assertGreater(len(result.i_total), 0)

    def test_raman_engine_fallback(self):
        """Test Raman engine falls back gracefully when RamanSPy/pybaselines are missing."""
        engine = RamanAnalyzer()
        x = np.linspace(200, 3000, 1000)
        y = np.exp(-0.5 * ((x - 1000) / 10)**2) + 0.1 * x  # Gaussian peak + linear baseline
        spectrum = RamanSpectrum(wavenumber=x, intensity=y)
        
        with patch('src.backend.core.engines.raman_engine.HAS_RAMANSPY', False), \
             patch('src.backend.core.engines.raman_engine.HAS_PYBASELINES', False):
            
            # Test preprocessing fallback
            preprocessed = engine.preprocess_ramanspy(spectrum)
            self.assertEqual(len(preprocessed.intensity), len(spectrum.intensity))
            
            # Test baseline fallback
            baseline = engine.baseline_correction(spectrum.wavenumber, spectrum.intensity)
            self.assertEqual(len(baseline), len(spectrum.intensity))

if __name__ == '__main__':
    unittest.main()
