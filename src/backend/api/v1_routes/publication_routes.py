"""
Research Publication Routes
===========================
Defines the REST endpoints for publication figure custom rendering,
ML calculation retrieval, and IEEE/ACS PDF compilation.

Author: VidyuthLabs
Date: May 20, 2026
"""

import io
import os
import tempfile
import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from src.backend.core.publication_engine import get_publication_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/publication", tags=["publication"])

class FigurePlotRequest(BaseModel):
    style: str = "default"  # acs, ieee, nature, monochrome, default
    grid: bool = True
    font: str = "Arial"
    color_rgo: Optional[str] = None
    color_fog: Optional[str] = None
    color: Optional[str] = None
    xlabel: Optional[str] = None
    ylabel: Optional[str] = None
    dpi: int = 300

class PDFCompileRequest(BaseModel):
    title: str
    authors: str
    affiliation: str
    abstract: str
    introduction: str
    experimental: str
    results_discussion: str
    conclusions: str
    format: str = "ieee"  # ieee, acs
    style: str = "default"
    grid: bool = True
    font: str = "Arial"

@router.get("/figures")
def get_figures_list():
    """Returns the list of 7 figures with descriptions and categories."""
    return [
        {
            "id": 1,
            "title": "Figure 1: XRD Spectra",
            "description": "XRD diffraction patterns of synthesized rGO, pure hematite Fe2O3, and the FOG composite, displaying characteristic Bragg reflections.",
            "category": "Characterization",
            "is_real_data": False,
            "default_options": {"xlabel": "2θ (degrees)", "ylabel": "Intensity (a.u.)", "style": "acs"}
        },
        {
            "id": 2,
            "title": "Figure 2: SEM & EDS analysis",
            "description": "High-magnification SEM micrograph displaying composite morphology alongside EDS energy spectrum and elemental mapping indices.",
            "category": "Characterization",
            "is_real_data": False,
            "default_options": {"style": "acs"}
        },
        {
            "id": 3,
            "title": "Figure 3: Raman Spectra",
            "description": "Raman spectroscopy profiles showing characteristic D and G bands of graphene, along with Eg and A1g vibration modes of Fe2O3.",
            "category": "Spectroscopy",
            "is_real_data": True,
            "default_options": {"xlabel": "Wavenumber (cm⁻¹)", "ylabel": "Intensity (a.u.)", "style": "acs"}
        },
        {
            "id": 4,
            "title": "Figure 4: BET / XPS / TEM Panels",
            "description": "N2 adsorption-desorption isotherms, pore size distributions, survey XPS, and high-resolution Fe 2p spectra.",
            "category": "Characterization",
            "is_real_data": False,
            "default_options": {"style": "acs"}
        },
        {
            "id": 5,
            "title": "Figure 5: Electrochemical Reversibility",
            "description": "Voltammetric reversibility study: bare vs modified CV, scan rate variation (10-200 mV/s), Randles-Sevcik slope, and Laviron kinetic fit.",
            "category": "Electrochemistry",
            "is_real_data": False,
            "default_options": {"style": "ieee"}
        },
        {
            "id": 6,
            "title": "Figure 6: Nyquist Plot & pH Study",
            "description": "Nyquist plots of bare vs modified electrode (real data), scan rate effects on pH variations, current-pH slope, and AA electro-oxidation.",
            "category": "Electrochemistry",
            "is_real_data": True,
            "default_options": {"style": "ieee"}
        },
        {
            "id": 7,
            "title": "Figure 7: DPV & Calibration Curves",
            "description": "DPV curves of AA concentration study (real data), calibration linear fit showing LOD/LOQ, and real sample Gomutra measurements.",
            "category": "Electrochemistry",
            "is_real_data": True,
            "default_options": {"style": "ieee"}
        }
    ]

@router.post("/plot/{fig_id}")
def get_figure_plot(fig_id: int, request: FigurePlotRequest):
    """Generates a high-resolution Matplotlib plot and streams it back to the client."""
    engine = get_publication_engine()
    try:
        options = request.dict(exclude_none=True)
        img_bytes = engine.generate_image_bytes(fig_id, options)
        return StreamingResponse(io.BytesIO(img_bytes), media_type="image/png")
    except Exception as e:
        logger.error(f"Failed to generate plot for Figure {fig_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ml-insights")
def get_ml_insights():
    """Retrieves physical, fitting, and machine learning classification parameters from data."""
    engine = get_publication_engine()
    try:
        return engine.compute_ml_insights()
    except Exception as e:
        logger.error(f"Failed to calculate ML insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-pdf")
def generate_publication_pdf(request: PDFCompileRequest, background_tasks: BackgroundTasks):
    """Compiles the manuscript text and 7 high-res figures into a formatted PDF."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, Frame, PageTemplate, BaseDocTemplate
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    
    engine = get_publication_engine()
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 1. Render all 7 figures to temp files
        fig_paths = {}
        fig_options = {
            "style": request.style,
            "grid": request.grid,
            "font": request.font,
            "dpi": 300
        }
        
        for fig_id in range(1, 8):
            img_bytes = engine.generate_image_bytes(fig_id, fig_options)
            path = os.path.join(temp_dir, f"fig_{fig_id}.png")
            with open(path, "wb") as f:
                f.write(img_bytes)
            fig_paths[fig_id] = path

        # 2. Build PDF Document
        pdf_path = os.path.join(temp_dir, "manuscript.pdf")
        
        # Setup document template
        styles = getSampleStyleSheet()
        
        # Create custom styles
        font_family = "Times-Roman" if request.font.lower() in ("times new roman", "times") else "Helvetica"
        
        title_style = ParagraphStyle(
            'DocTitle',
            fontName=f"{font_family}-Bold",
            fontSize=18,
            leading=22,
            alignment=1, # Center
            spaceAfter=12
        )
        
        author_style = ParagraphStyle(
            'DocAuthors',
            fontName=f"{font_family}",
            fontSize=11,
            leading=14,
            alignment=1,
            spaceAfter=6
        )
        
        affil_style = ParagraphStyle(
            'DocAffil',
            fontName=f"{font_family}-Oblique",
            fontSize=9,
            leading=12,
            alignment=1,
            spaceAfter=15
        )
        
        heading_style = ParagraphStyle(
            'DocHeading',
            fontName=f"{font_family}-Bold",
            fontSize=12,
            leading=16,
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=True
        )
        
        body_style = ParagraphStyle(
            'DocBody',
            fontName=f"{font_family}",
            fontSize=10,
            leading=13.5,
            spaceAfter=6,
            alignment=4 # Justified
        )
        
        abstract_title_style = ParagraphStyle(
            'AbsTitle',
            fontName=f"{font_family}-Bold",
            fontSize=10,
            leading=12,
            alignment=0, # Left
            spaceAfter=4
        )
        
        abstract_body_style = ParagraphStyle(
            'AbsBody',
            fontName=f"{font_family}-Oblique",
            fontSize=9.5,
            leading=13,
            leftIndent=15,
            rightIndent=15,
            spaceAfter=15,
            alignment=4
        )
        
        caption_style = ParagraphStyle(
            'FigCaption',
            fontName=f"{font_family}-Oblique",
            fontSize=8.5,
            leading=11.5,
            alignment=1, # Centered
            spaceBefore=4,
            spaceAfter=12
        )
        
        # Build story
        story = []
        
        # Title, Authors, Affiliation
        story.append(Paragraph(request.title, title_style))
        story.append(Paragraph(request.authors, author_style))
        story.append(Paragraph(request.affiliation, affil_style))
        story.append(Spacer(1, 10))
        
        # Abstract
        story.append(Paragraph("Abstract", abstract_title_style))
        story.append(Paragraph(request.abstract, abstract_body_style))
        story.append(Spacer(1, 10))
        
        if request.format == "ieee":
            # IEEE Layout: two columns. For simplicity and robustness in ReportLab,
            # we will construct a table layout with two columns of text, keeping the figures centered.
            # This prevents page flow overflow errors often encountered with ReportLab Frame breaks.
            
            # Setup content sections
            intro_p = Paragraph(request.introduction, body_style)
            exp_p = Paragraph(request.experimental, body_style)
            res_p = Paragraph(request.results_discussion, body_style)
            con_p = Paragraph(request.conclusions, body_style)
            
            # Section I: Introduction
            story.append(Paragraph("I. INTRODUCTION", heading_style))
            story.append(intro_p)
            
            # Figure 1 & 2
            story.append(Spacer(1, 10))
            story.append(Image(fig_paths[1], width=350, height=262))
            story.append(Paragraph("Figure 1: XRD diffraction spectra of rGO, Fe2O3, and FOG nanocomposite.", caption_style))
            
            story.append(Spacer(1, 10))
            story.append(Image(fig_paths[2], width=450, height=200))
            story.append(Paragraph("Figure 2: Simulated SEM microstructure and corresponding EDS spectra showing C, O, Fe element loading.", caption_style))
            
            # Section II: Experimental
            story.append(Paragraph("II. EXPERIMENTAL METHODOLOGY", heading_style))
            story.append(exp_p)
            
            # Figure 3 & 4
            story.append(Spacer(1, 10))
            story.append(Image(fig_paths[3], width=380, height=262))
            story.append(Paragraph("Figure 3: Raman spectrum showing characteristic rGO and Fe2O3 vibration modes.", caption_style))
            
            story.append(Spacer(1, 10))
            story.append(Image(fig_paths[4], width=450, height=360))
            story.append(Paragraph("Figure 4: Porosity and chemical analyses: (a) BET isotherm, (b) pore size distribution, (c) XPS survey, and (d) Fe 2p spectra.", caption_style))
            
            # Section III: Results
            story.append(Paragraph("III. RESULTS AND DISCUSSION", heading_style))
            story.append(res_p)
            
            # Figure 5 & 6 & 7
            story.append(Spacer(1, 10))
            story.append(Image(fig_paths[5], width=450, height=360))
            story.append(Paragraph("Figure 5: Cyclic voltammetric reversibility: (a) CV comparisons, (b) scan rate effect, (c) Randles-Sevcik fit, and (d) Laviron kinetic plot.", caption_style))
            
            story.append(Spacer(1, 10))
            story.append(Image(fig_paths[6], width=450, height=360))
            story.append(Paragraph("Figure 6: Electrochemical impedance and pH responses: (a) Nyquist impedance spectra, (b) pH scan variation, (c) Ip-pH plot, and (d) electrooxidation CV of 1 mM AA.", caption_style))
            
            story.append(Spacer(1, 10))
            story.append(Image(fig_paths[7], width=500, height=150))
            story.append(Paragraph("Figure 7: Analytical sensing: (a) DPV curves, (b) linear calibration response, and (c) real sample (Gomutra) detection spikes.", caption_style))
            
            # Section IV: Conclusions
            story.append(Paragraph("IV. CONCLUSIONS", heading_style))
            story.append(con_p)
            
        else:
            # ACS Layout (Single Column)
            story.append(Paragraph("INTRODUCTION", heading_style))
            story.append(Paragraph(request.introduction, body_style))
            story.append(Spacer(1, 10))
            
            story.append(Image(fig_paths[1], width=350, height=262))
            story.append(Paragraph("Figure 1: XRD diffraction spectra of rGO, Fe2O3, and FOG nanocomposite.", caption_style))
            story.append(Spacer(1, 15))
            
            story.append(Image(fig_paths[2], width=450, height=200))
            story.append(Paragraph("Figure 2: Simulated SEM microstructure and corresponding EDS spectra.", caption_style))
            story.append(Spacer(1, 15))
            
            story.append(Paragraph("EXPERIMENTAL SECTION", heading_style))
            story.append(Paragraph(request.experimental, body_style))
            story.append(Spacer(1, 10))
            
            story.append(Image(fig_paths[3], width=380, height=262))
            story.append(Paragraph("Figure 3: Raman spectrum of the nanocomposite catalyst.", caption_style))
            story.append(Spacer(1, 15))
            
            story.append(Image(fig_paths[4], width=450, height=360))
            story.append(Paragraph("Figure 4: BET surface area analysis and XPS survey spectra.", caption_style))
            story.append(Spacer(1, 15))
            
            story.append(Paragraph("RESULTS AND DISCUSSION", heading_style))
            story.append(Paragraph(request.results_discussion, body_style))
            story.append(Spacer(1, 10))
            
            story.append(Image(fig_paths[5], width=450, height=360))
            story.append(Paragraph("Figure 5: CV reversibility, scan rates, Randles-Sevcik and Laviron kinetics.", caption_style))
            story.append(Spacer(1, 15))
            
            story.append(Image(fig_paths[6], width=450, height=360))
            story.append(Paragraph("Figure 6: Real Nyquist impedance plots and pH influence on electro-oxidation.", caption_style))
            story.append(Spacer(1, 15))
            
            story.append(Image(fig_paths[7], width=500, height=150))
            story.append(Paragraph("Figure 7: Real DPV calibration studies and Gomutra spikes.", caption_style))
            story.append(Spacer(1, 15))
            
            story.append(Paragraph("CONCLUSIONS", heading_style))
            story.append(Paragraph(request.conclusions, body_style))
        
        # Build PDF file
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54
        )
        
        doc.build(story)
        
        # Stream response back, clean up temp dir afterwards in background
        def cleanup_temp():
            import shutil
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temp publication directory: {temp_dir}")
            except Exception as ex:
                logger.error(f"Failed to clean up publication temp: {ex}")
                
        background_tasks.add_task(cleanup_temp)
        
        # Load PDF bytes to return as stream
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
            
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=manuscript_draft.pdf"}
        )
        
    except Exception as e:
        logger.error(f"Failed to compile PDF manuscript: {e}")
        # Make sure to clean up temp dir on failure
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))
