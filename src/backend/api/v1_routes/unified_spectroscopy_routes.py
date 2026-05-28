"""
Unified Spectroscopy API Routes
================================
REST API endpoints for unified spectroscopy analysis.

Endpoints:
- POST /api/v1/unified-spectroscopy/analyze - Full analysis with all features
- POST /api/v1/unified-spectroscopy/batch-analyze - Batch analysis
- POST /api/v1/unified-spectroscopy/pca - PCA analysis
- POST /api/v1/unified-spectroscopy/clustering - Clustering analysis
- POST /api/v1/unified-spectroscopy/augment - Data augmentation
- GET /api/v1/unified-spectroscopy/methods - Available methods
- GET /api/v1/unified-spectroscopy/health - Health check

Author: VidyuthLabs
Date: May 4, 2026
"""

import logging
import tempfile
import os
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel, Field

from src.backend.core.engines.unified_spectroscopy_engine import (
    UnifiedSpectroscopyAnalyzer,
    UnifiedSpectroscopyConfig,
    BatchSpectroscopyAnalyzer,
)
from src.backend.core.engines.raman_engine import (
    import_raman_data,
    RamanSpectrum,
    identify_material,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/unified-spectroscopy", tags=["unified-spectroscopy"])


# ═══════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════

class UnifiedAnalysisRequest(BaseModel):
    """Request model for unified spectroscopy analysis."""
    # Baseline correction
    baseline_method: str = Field("als", description="Baseline correction method")
    baseline_lambda: float = Field(1e5, description="Smoothness parameter")
    
    # Cosmic ray removal
    cosmic_ray_removal: bool = Field(False, description="Enable cosmic ray removal")
    cosmic_ray_threshold: float = Field(10.0, description="Cosmic ray threshold (std)")
    
    # Fourier filtering
    fourier_filtering: bool = Field(False, description="Enable Fourier filtering")
    fourier_cutoff_freq: float = Field(0.1, description="Fourier cutoff frequency")
    
    # Peak detection
    peak_detection: bool = Field(True, description="Enable peak detection")
    peak_fitting: bool = Field(True, description="Enable peak fitting")
    voigt_fitting: bool = Field(False, description="Use Voigt profile fitting")
    
    # Normalization
    normalize: bool = Field(True, description="Enable normalization")
    normalization_method: str = Field("minmax", description="Normalization method")
    
    # Data augmentation
    augmentation_enabled: bool = Field(False, description="Enable data augmentation")
    augmentation_n_samples: int = Field(5, description="Number of augmented samples")
    
    # Dimensionality reduction
    pca_enabled: bool = Field(False, description="Enable PCA")
    pca_n_components: int = Field(10, description="Number of PCA components")
    
    # Clustering
    clustering_enabled: bool = Field(False, description="Enable clustering")
    clustering_method: str = Field("kmeans", description="Clustering method")
    clustering_n_clusters: int = Field(3, description="Number of clusters")


class BatchAnalysisRequest(BaseModel):
    """Request model for batch analysis."""
    config: UnifiedAnalysisRequest
    perform_pca: bool = Field(True, description="Perform PCA on batch")
    perform_clustering: bool = Field(True, description="Perform clustering on batch")
    compute_statistics: bool = Field(True, description="Compute batch statistics")


# ═══════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/analyze")
async def analyze_unified(
    file: UploadFile = File(...),
    cosmic_ray_removal: bool = False,
    fourier_filtering: bool = False,
    voigt_fitting: bool = False,
    augmentation_enabled: bool = False,
    pca_enabled: bool = False,
    clustering_enabled: bool = False,
):
    """
    Analyze spectrum with unified spectroscopy engine.
    
    **Advanced Features:**
    - Cosmic ray removal (from BoxSERS)
    - Fourier filtering (from SpectraGuru)
    - Voigt peak fitting (from RamanLab)
    - Data augmentation (from BoxSERS)
    - PCA dimensionality reduction (from SpectraGuru)
    - Clustering analysis (from SpectraGuru)
    
    **Returns:**
    - Fully analyzed spectrum with all enhancements
    """
    logger.info(f"Unified analysis: {file.filename}")
    
    # Validate file type
    if not file.filename.endswith(('.txt', '.csv', '.TXT', '.CSV')):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload .txt or .csv file."
        )
    
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # Import spectrum
        spectrum = import_raman_data(tmp_path)
        spectrum.source_file = file.filename
        
        # Create unified config
        config = UnifiedSpectroscopyConfig(
            cosmic_ray_removal=cosmic_ray_removal,
            fourier_filtering=fourier_filtering,
            voigt_fitting=voigt_fitting,
            augmentation_enabled=augmentation_enabled,
            pca_enabled=pca_enabled,
            clustering_enabled=clustering_enabled,
        )
        
        # Analyze
        analyzer = UnifiedSpectroscopyAnalyzer(config)
        analyzed_spectrum = analyzer.analyze(spectrum)
        
        # Identify material
        material_matches = identify_material(analyzed_spectrum)
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        # Build response
        result = analyzed_spectrum.to_dict()
        result["material_matches"] = material_matches
        result["analysis_config"] = {
            "cosmic_ray_removal": cosmic_ray_removal,
            "fourier_filtering": fourier_filtering,
            "voigt_fitting": voigt_fitting,
            "augmentation_enabled": augmentation_enabled,
            "baseline_method": config.baseline_method,
            "normalization_method": config.normalization_method,
        }
        
        # Add augmented spectra if enabled
        if augmentation_enabled and hasattr(analyzed_spectrum, 'augmented_spectra'):
            result["augmented_spectra"] = [
                aug.to_dict() for aug in analyzed_spectrum.augmented_spectra
            ]
        
        logger.info(f"Unified analysis complete: {len(analyzed_spectrum.peaks)} peaks detected")
        return result
    
    except Exception as e:
        logger.error(f"Unified analysis failed: {e}")
        # Clean up temp file if it exists
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/batch-analyze")
async def batch_analyze_unified(
    files: List[UploadFile] = File(...),
    perform_pca: bool = True,
    perform_clustering: bool = True,
    compute_statistics: bool = True,
):
    """
    Batch analysis of multiple spectra with unified engine.
    
    **Features:**
    - Analyze multiple spectra simultaneously
    - Compute batch statistics (mean, std, confidence intervals)
    - Perform PCA across all spectra
    - Perform clustering to identify groups
    - Generate correlation matrix
    
    **Returns:**
    - Individual analysis results
    - Batch statistics
    - PCA results
    - Clustering results
    """
    logger.info(f"Batch analysis: {len(files)} files")
    
    if len(files) == 0:
        raise HTTPException(status_code=400, detail="No files provided")
    
    try:
        # Create batch analyzer
        config = UnifiedSpectroscopyConfig()
        batch_analyzer = BatchSpectroscopyAnalyzer(config)
        
        # Import all spectra
        temp_files = []
        for file in files:
            # Save temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
                content = await file.read()
                tmp.write(content)
                temp_files.append(tmp.name)
            
            # Import
            spectrum = import_raman_data(tmp.name)
            spectrum.source_file = file.filename
            batch_analyzer.add_spectrum(spectrum)
        
        # Analyze all
        analyzed_spectra = batch_analyzer.analyze_all()
        
        # Build response
        result = {
            "n_spectra": len(analyzed_spectra),
            "spectra": [s.to_dict() for s in analyzed_spectra],
        }
        
        # Compute statistics
        if compute_statistics:
            stats = batch_analyzer.compute_statistics()
            result["statistics"] = {
                "mean_spectrum": stats["mean_spectrum"].tolist(),
                "std_spectrum": stats["std_spectrum"].tolist(),
                "median_spectrum": stats["median_spectrum"].tolist(),
                "wavenumber": stats["wavenumber"].tolist(),
            }
        
        # Perform PCA
        if perform_pca and len(analyzed_spectra) >= 2:
            X_pca, pca_model, explained_var = batch_analyzer.perform_pca_analysis()
            result["pca"] = {
                "transformed_data": X_pca.tolist(),
                "explained_variance_ratio": explained_var.tolist(),
                "cumulative_variance": explained_var.cumsum().tolist(),
                "n_components": len(explained_var),
            }
        
        # Perform clustering
        if perform_clustering and len(analyzed_spectra) >= 2:
            labels, model = batch_analyzer.perform_clustering()
            result["clustering"] = {
                "labels": labels.tolist(),
                "n_clusters": len(set(labels)),
                "method": config.clustering_method,
            }
        
        # Clean up temp files
        for tmp_path in temp_files:
            try:
                os.unlink(tmp_path)
            except:
                pass
        
        logger.info(f"Batch analysis complete: {len(analyzed_spectra)} spectra")
        return result
    
    except Exception as e:
        logger.error(f"Batch analysis failed: {e}")
        # Clean up temp files
        try:
            for tmp_path in temp_files:
                os.unlink(tmp_path)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {str(e)}")


@router.post("/pca")
async def perform_pca_analysis(
    files: List[UploadFile] = File(...),
    n_components: int = 10,
):
    """
    Perform PCA dimensionality reduction on multiple spectra.
    
    **From SpectraGuru:**
    - Reduces high-dimensional spectral data to principal components
    - Identifies major sources of variance
    - Enables visualization in 2D/3D
    
    **Returns:**
    - Transformed data (PC scores)
    - Explained variance ratio
    - Cumulative variance
    """
    logger.info(f"PCA analysis: {len(files)} files, {n_components} components")
    
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="PCA requires at least 2 spectra")
    
    try:
        # Import spectra
        spectra = []
        temp_files = []
        
        for file in files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
                content = await file.read()
                tmp.write(content)
                temp_files.append(tmp.name)
            
            spectrum = import_raman_data(tmp.name)
            spectrum.source_file = file.filename
            spectra.append(spectrum)
        
        # Analyze spectra first
        config = UnifiedSpectroscopyConfig(pca_n_components=n_components)
        analyzer = UnifiedSpectroscopyAnalyzer(config)
        
        analyzed_spectra = [analyzer.analyze(s) for s in spectra]
        
        # Perform PCA
        X_pca, pca_model, explained_var = analyzer.perform_pca(analyzed_spectra)
        
        # Clean up
        for tmp_path in temp_files:
            try:
                os.unlink(tmp_path)
            except:
                pass
        
        result = {
            "n_spectra": len(spectra),
            "n_components": len(explained_var),
            "transformed_data": X_pca.tolist(),
            "explained_variance_ratio": explained_var.tolist(),
            "cumulative_variance": explained_var.cumsum().tolist(),
            "total_variance_explained": float(explained_var.sum()),
        }
        
        logger.info(f"PCA complete: {len(explained_var)} components, {explained_var.sum():.2%} variance")
        return result
    
    except Exception as e:
        logger.error(f"PCA analysis failed: {e}")
        try:
            for tmp_path in temp_files:
                os.unlink(tmp_path)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"PCA failed: {str(e)}")


@router.post("/clustering")
async def perform_clustering_analysis(
    files: List[UploadFile] = File(...),
    method: str = "kmeans",
    n_clusters: int = 3,
):
    """
    Perform clustering analysis on multiple spectra.
    
    **From SpectraGuru:**
    - K-means clustering for fast grouping
    - Hierarchical clustering for dendrogram visualization
    - Identifies similar spectra automatically
    
    **Returns:**
    - Cluster labels for each spectrum
    - Cluster centers (for K-means)
    - Linkage matrix (for hierarchical)
    """
    logger.info(f"Clustering: {len(files)} files, method={method}, n_clusters={n_clusters}")
    
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Clustering requires at least 2 spectra")
    
    try:
        # Import spectra
        spectra = []
        temp_files = []
        
        for file in files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
                content = await file.read()
                tmp.write(content)
                temp_files.append(tmp.name)
            
            spectrum = import_raman_data(tmp.name)
            spectrum.source_file = file.filename
            spectra.append(spectrum)
        
        # Analyze spectra first
        config = UnifiedSpectroscopyConfig(
            clustering_method=method,
            clustering_n_clusters=n_clusters
        )
        analyzer = UnifiedSpectroscopyAnalyzer(config)
        
        analyzed_spectra = [analyzer.analyze(s) for s in spectra]
        
        # Perform clustering
        if method == "kmeans":
            labels, model = analyzer.perform_kmeans_clustering(analyzed_spectra)
            result = {
                "method": "kmeans",
                "n_clusters": n_clusters,
                "labels": labels.tolist(),
                "cluster_centers": model.cluster_centers_.tolist(),
                "inertia": float(model.inertia_),
            }
        else:
            linkage_matrix, X = analyzer.perform_hierarchical_clustering(analyzed_spectra, method="ward")
            result = {
                "method": "hierarchical",
                "linkage_method": "ward",
                "linkage_matrix": linkage_matrix.tolist(),
            }
        
        # Clean up
        for tmp_path in temp_files:
            try:
                os.unlink(tmp_path)
            except:
                pass
        
        result["n_spectra"] = len(spectra)
        result["filenames"] = [f.filename for f in files]
        
        logger.info(f"Clustering complete: {method}")
        return result
    
    except Exception as e:
        logger.error(f"Clustering failed: {e}")
        try:
            for tmp_path in temp_files:
                os.unlink(tmp_path)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Clustering failed: {str(e)}")


@router.post("/augment")
async def augment_spectrum(
    file: UploadFile = File(...),
    n_augmentations: int = 5,
    noise_level: float = 0.01,
    xshift_range: float = 5.0,
):
    """
    Generate augmented spectra for data augmentation.
    
    **From BoxSERS:**
    - Noise injection: Add Gaussian noise
    - X-shift: Shift wavenumber axis
    - Intensity scaling: Scale intensity values
    
    **Use Cases:**
    - Training data augmentation for ML models
    - Robustness testing
    - Uncertainty quantification
    
    **Returns:**
    - Original spectrum
    - List of augmented spectra
    """
    logger.info(f"Data augmentation: {file.filename}, n={n_augmentations}")
    
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # Import spectrum
        spectrum = import_raman_data(tmp_path)
        spectrum.source_file = file.filename
        
        # Create config
        config = UnifiedSpectroscopyConfig(
            augmentation_enabled=True,
            augmentation_noise_level=noise_level,
            augmentation_xshift_range=xshift_range,
        )
        
        # Analyze original
        analyzer = UnifiedSpectroscopyAnalyzer(config)
        analyzed_spectrum = analyzer.analyze(spectrum)
        
        # Generate augmentations
        augmented_spectra = analyzer.augment_spectrum(analyzed_spectrum, n_augmentations)
        
        # Clean up
        os.unlink(tmp_path)
        
        result = {
            "original": analyzed_spectrum.to_dict(),
            "augmented": [aug.to_dict() for aug in augmented_spectra],
            "n_augmentations": len(augmented_spectra),
            "augmentation_config": {
                "noise_level": noise_level,
                "xshift_range": xshift_range,
            }
        }
        
        logger.info(f"Augmentation complete: {len(augmented_spectra)} spectra generated")
        return result
    
    except Exception as e:
        logger.error(f"Augmentation failed: {e}")
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Augmentation failed: {str(e)}")


@router.get("/methods")
async def get_unified_methods():
    """
    Get available methods in unified spectroscopy engine.
    
    **Returns:**
    - All preprocessing methods
    - All normalization methods
    - All peak fitting methods
    - All dimensionality reduction methods
    - All clustering methods
    - All augmentation methods
    """
    return {
        "preprocessing": {
            "cosmic_ray_removal": {
                "name": "Cosmic Ray Removal",
                "description": "Remove cosmic ray spikes using statistical outlier detection",
                "source": "BoxSERS",
                "recommended": True
            },
            "fourier_filtering": {
                "name": "Fourier Transform Filtering",
                "description": "Low-pass filtering in frequency domain",
                "source": "SpectraGuru",
                "recommended": True
            },
            "baseline_correction": {
                "methods": ["airPLS", "AsLS", "polynomial", "morphological"],
                "source": "Multiple sources",
                "recommended": "airPLS or AsLS"
            }
        },
        "normalization": {
            "minmax": {"name": "Min-Max", "source": "Standard"},
            "area": {"name": "Area Normalization", "source": "Standard"},
            "vector": {"name": "Vector (L2) Normalization", "source": "Standard"},
            "snv": {"name": "Standard Normal Variate", "source": "Standard"},
            "max_intensity": {"name": "Max Intensity", "source": "RamanSPy"},
            "auc": {"name": "Area Under Curve", "source": "RamanSPy"},
        },
        "peak_fitting": {
            "lorentzian": {"name": "Lorentzian", "source": "Standard"},
            "gaussian": {"name": "Gaussian", "source": "Standard"},
            "voigt": {"name": "Voigt Profile", "source": "RamanLab", "recommended": True},
            "asymmetric_voigt": {"name": "Asymmetric Voigt", "source": "RamanLab"},
        },
        "dimensionality_reduction": {
            "pca": {
                "name": "Principal Component Analysis",
                "description": "Linear dimensionality reduction",
                "source": "SpectraGuru",
                "recommended": True
            },
            "tsne": {
                "name": "t-SNE",
                "description": "Nonlinear dimensionality reduction",
                "source": "SpectraGuru",
                "recommended": True
            },
        },
        "clustering": {
            "kmeans": {
                "name": "K-Means Clustering",
                "description": "Fast partitional clustering",
                "source": "SpectraGuru",
                "recommended": True
            },
            "hierarchical": {
                "name": "Hierarchical Clustering",
                "description": "Agglomerative clustering with dendrogram",
                "source": "SpectraGuru",
                "recommended": True
            },
        },
        "augmentation": {
            "noise_injection": {
                "name": "Noise Injection",
                "description": "Add Gaussian noise",
                "source": "BoxSERS"
            },
            "xshift": {
                "name": "Wavenumber Shift",
                "description": "Shift wavenumber axis",
                "source": "BoxSERS"
            },
            "intensity_scaling": {
                "name": "Intensity Scaling",
                "description": "Scale intensity values",
                "source": "BoxSERS"
            },
            "mixup": {
                "name": "Mixup Augmentation",
                "description": "Linear interpolation between spectra",
                "source": "BoxSERS"
            },
        },
        "deep_learning": {
            "resunet_denoising": {
                "name": "ResUNet Denoising",
                "description": "Deep learning denoising with 1D ResUNet",
                "source": "DeepeR",
                "status": "Planned"
            },
            "cnn_classification": {
                "name": "CNN Classification",
                "description": "Convolutional neural network for classification",
                "source": "Raman-Spectra-Deep-Learning",
                "status": "Planned"
            },
            "simclr": {
                "name": "SimCLR Contrastive Learning",
                "description": "Self-supervised learning for few-shot classification",
                "source": "Raman-Spectra-Deep-Learning",
                "status": "Planned"
            },
        }
    }


@router.get("/health")
async def unified_health_check():
    """
    Health check for unified spectroscopy engine.
    
    **Returns:**
    - Engine status
    - Available features
    - Research sources
    """
    return {
        "status": "healthy",
        "engine": "unified_spectroscopy",
        "version": "1.0.0",
        "features": {
            "cosmic_ray_removal": True,
            "fourier_filtering": True,
            "voigt_fitting": True,
            "data_augmentation": True,
            "pca": True,
            "tsne": True,
            "clustering": True,
            "batch_analysis": True,
            "deep_learning": False,  # Planned
        },
        "research_sources": [
            "SpectraGuru (ACS Analytical Chemistry 2025)",
            "DeepeR (Deep Learning Enabled Raman)",
            "spectrai (PyTorch Framework)",
            "RamanSPy (Open-Source Python)",
            "BoxSERS (Full Analysis Package)",
            "RamanLab (6,939+ Reference Spectra)",
            "Raman-Spectra-Deep-Learning (CNN, LSTM, Transformer, GCN, SimCLR)",
        ],
        "algorithms": {
            "baseline": ["airPLS", "AsLS", "polynomial", "morphological"],
            "denoising": ["Savitzky-Golay", "Fourier", "cosmic ray removal"],
            "normalization": ["minmax", "area", "vector", "snv", "max_intensity", "auc"],
            "peak_fitting": ["Lorentzian", "Gaussian", "Voigt", "Asymmetric Voigt"],
            "dimensionality_reduction": ["PCA", "t-SNE"],
            "clustering": ["K-means", "Hierarchical"],
            "augmentation": ["noise injection", "x-shift", "intensity scaling", "mixup"],
        }
    }
