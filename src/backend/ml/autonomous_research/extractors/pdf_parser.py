"""
PDF Full-Text Parser
Extracts complete text from scientific papers
"""

import os
import re
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    logging.warning("PyPDF2 not available. Install with: pip install PyPDF2")

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logging.warning("pdfplumber not available. Install with: pip install pdfplumber")

from .base_extractor import BaseExtractor, ExtractionResult

logger = logging.getLogger(__name__)


@dataclass
class PDFContent:
    """Parsed PDF content"""
    full_text: str
    sections: Dict[str, str]
    page_count: int
    has_images: bool
    has_tables: bool
    extraction_method: str


class PDFParser(BaseExtractor):
    """
    PDF Full-Text Parser
    
    Features:
    - Downloads PDFs from URLs
    - Extracts full text using PyPDF2 and pdfplumber
    - Identifies sections (Abstract, Methods, Results, Discussion)
    - Handles multi-column layouts
    - Caches downloaded PDFs
    """
    
    # Section headers to detect
    SECTION_PATTERNS = {
        'abstract': r'\b(abstract|summary)\b',
        'introduction': r'\b(introduction|background)\b',
        'methods': r'\b(methods?|methodology|experimental|materials and methods)\b',
        'results': r'\b(results?|findings)\b',
        'discussion': r'\b(discussion|conclusion)\b',
        'references': r'\b(references|bibliography|citations)\b'
    }
    
    def __init__(self, cache_dir: str = "data/pdf_cache"):
        """
        Initialize PDF parser
        
        Args:
            cache_dir: Directory to cache downloaded PDFs
        """
        super().__init__("PDFParser")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Check dependencies
        if not PYPDF2_AVAILABLE and not PDFPLUMBER_AVAILABLE:
            raise ImportError(
                "Neither PyPDF2 nor pdfplumber available. "
                "Install with: pip install PyPDF2 pdfplumber"
            )
    
    def extract(self, paper: Dict[str, Any]) -> ExtractionResult:
        """
        Extract full text from paper PDF
        
        Args:
            paper: Paper metadata dict with 'pdf_url' field
        
        Returns:
            ExtractionResult with PDFContent
        """
        paper_id = paper.get('doi') or paper.get('pmid') or paper.get('arxiv_id', 'unknown')
        
        # Check if PDF URL available
        pdf_url = paper.get('pdf_url')
        if not pdf_url:
            # Fallback to abstract only
            return self._fallback_to_abstract(paper, paper_id)
        
        try:
            # Download PDF
            pdf_path = self._download_pdf(pdf_url, paper_id)
            if not pdf_path:
                return self._fallback_to_abstract(paper, paper_id)
            
            # Parse PDF
            content = self._parse_pdf(pdf_path)
            if not content:
                return self._fallback_to_abstract(paper, paper_id)
            
            # Calculate confidence
            confidence = self._calculate_confidence(content)
            
            self.log_success(paper_id, confidence)
            
            return ExtractionResult(
                success=True,
                data={
                    'full_text': content.full_text,
                    'sections': content.sections,
                    'page_count': content.page_count,
                    'has_images': content.has_images,
                    'has_tables': content.has_tables,
                    'extraction_method': content.extraction_method
                },
                confidence=confidence,
                method='pdf_parser'
            )
        
        except Exception as e:
            self.log_failure(paper_id, str(e))
            return self._fallback_to_abstract(paper, paper_id)
    
    def _download_pdf(self, url: str, paper_id: str) -> Optional[Path]:
        """
        Download PDF from URL
        
        Args:
            url: PDF URL
            paper_id: Paper identifier for caching
        
        Returns:
            Path to downloaded PDF or None
        """
        # Create safe filename
        safe_id = re.sub(r'[^\w\-_]', '_', paper_id)
        pdf_path = self.cache_dir / f"{safe_id}.pdf"
        
        # Check cache
        if pdf_path.exists():
            self.logger.debug(f"Using cached PDF: {pdf_path}")
            return pdf_path
        
        try:
            # Download PDF
            self.logger.info(f"Downloading PDF from {url}")
            response = requests.get(url, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; ResearchBot/1.0)'
            })
            response.raise_for_status()
            
            # Check if actually PDF
            content_type = response.headers.get('Content-Type', '')
            if 'pdf' not in content_type.lower() and not url.endswith('.pdf'):
                self.logger.warning(f"URL does not appear to be PDF: {content_type}")
                return None
            
            # Save to cache
            with open(pdf_path, 'wb') as f:
                f.write(response.content)
            
            self.logger.info(f"PDF downloaded: {pdf_path}")
            return pdf_path
        
        except requests.RequestException as e:
            self.logger.warning(f"Failed to download PDF: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error downloading PDF: {e}")
            return None
    
    def _parse_pdf(self, pdf_path: Path) -> Optional[PDFContent]:
        """
        Parse PDF file
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            PDFContent or None
        """
        # Try pdfplumber first (better for complex layouts)
        if PDFPLUMBER_AVAILABLE:
            content = self._parse_with_pdfplumber(pdf_path)
            if content:
                return content
        
        # Fallback to PyPDF2
        if PYPDF2_AVAILABLE:
            content = self._parse_with_pypdf2(pdf_path)
            if content:
                return content
        
        return None
    
    def _parse_with_pdfplumber(self, pdf_path: Path) -> Optional[PDFContent]:
        """Parse PDF using pdfplumber"""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Extract text from all pages
                pages_text = []
                has_images = False
                has_tables = False
                
                for page in pdf.pages:
                    # Extract text
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
                    
                    # Check for images
                    if page.images:
                        has_images = True
                    
                    # Check for tables
                    if page.extract_tables():
                        has_tables = True
                
                if not pages_text:
                    return None
                
                # Combine all text
                full_text = '\n\n'.join(pages_text)
                
                # Identify sections
                sections = self._identify_sections(full_text)
                
                return PDFContent(
                    full_text=full_text,
                    sections=sections,
                    page_count=len(pdf.pages),
                    has_images=has_images,
                    has_tables=has_tables,
                    extraction_method='pdfplumber'
                )
        
        except Exception as e:
            self.logger.warning(f"pdfplumber parsing failed: {e}")
            return None
    
    def _parse_with_pypdf2(self, pdf_path: Path) -> Optional[PDFContent]:
        """Parse PDF using PyPDF2"""
        try:
            with open(pdf_path, 'rb') as f:
                reader = PdfReader(f)
                
                # Extract text from all pages
                pages_text = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
                
                if not pages_text:
                    return None
                
                # Combine all text
                full_text = '\n\n'.join(pages_text)
                
                # Identify sections
                sections = self._identify_sections(full_text)
                
                return PDFContent(
                    full_text=full_text,
                    sections=sections,
                    page_count=len(reader.pages),
                    has_images=False,  # PyPDF2 doesn't easily detect images
                    has_tables=False,  # PyPDF2 doesn't easily detect tables
                    extraction_method='pypdf2'
                )
        
        except Exception as e:
            self.logger.warning(f"PyPDF2 parsing failed: {e}")
            return None
    
    def _identify_sections(self, text: str) -> Dict[str, str]:
        """
        Identify paper sections
        
        Args:
            text: Full paper text
        
        Returns:
            Dict mapping section names to text
        """
        sections = {}
        text_lower = text.lower()
        
        # Find section boundaries
        section_positions = []
        for section_name, pattern in self.SECTION_PATTERNS.items():
            matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
            for match in matches:
                # Check if it's a section header (at start of line or after newline)
                start = match.start()
                if start == 0 or text[start-1] in '\n\r':
                    section_positions.append((start, section_name))
        
        # Sort by position
        section_positions.sort()
        
        # Extract section text
        for i, (pos, name) in enumerate(section_positions):
            # Get text until next section or end
            if i < len(section_positions) - 1:
                next_pos = section_positions[i + 1][0]
                section_text = text[pos:next_pos]
            else:
                section_text = text[pos:]
            
            # Clean up
            section_text = section_text.strip()
            
            # Store (only first occurrence of each section)
            if name not in sections:
                sections[name] = section_text
        
        return sections
    
    def _calculate_confidence(self, content: PDFContent) -> float:
        """
        Calculate extraction confidence
        
        Args:
            content: Parsed PDF content
        
        Returns:
            Confidence score (0-1)
        """
        confidence = 0.0
        
        # Base confidence for successful extraction
        confidence += 0.3
        
        # Bonus for having sections
        if content.sections:
            confidence += 0.2 * (len(content.sections) / len(self.SECTION_PATTERNS))
        
        # Bonus for having methods section (critical for extraction)
        if 'methods' in content.sections:
            confidence += 0.2
        
        # Bonus for having results section
        if 'results' in content.sections:
            confidence += 0.2
        
        # Bonus for reasonable length
        if len(content.full_text) > 5000:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _fallback_to_abstract(self, paper: Dict[str, Any], 
                             paper_id: str) -> ExtractionResult:
        """
        Fallback to abstract-only extraction
        
        Args:
            paper: Paper metadata
            paper_id: Paper identifier
        
        Returns:
            ExtractionResult with abstract text
        """
        abstract = paper.get('abstract', '')
        title = paper.get('title', '')
        
        if not abstract and not title:
            self.log_failure(paper_id, "No PDF and no abstract available")
            return ExtractionResult(
                success=False,
                error="No text available",
                method='pdf_parser'
            )
        
        # Use title + abstract
        text = f"{title}\n\n{abstract}"
        
        self.logger.info(f"Falling back to abstract for {paper_id}")
        
        return ExtractionResult(
            success=True,
            data={
                'full_text': text,
                'sections': {'abstract': abstract},
                'page_count': 0,
                'has_images': False,
                'has_tables': False,
                'extraction_method': 'abstract_only'
            },
            confidence=0.3,  # Low confidence for abstract-only
            method='pdf_parser'
        )
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """
        Validate extracted PDF data
        
        Args:
            data: Extracted data dict
        
        Returns:
            True if valid
        """
        required_fields = ['full_text', 'sections', 'extraction_method']
        
        # Check required fields
        for field in required_fields:
            if field not in data:
                return False
        
        # Check text not empty
        if not data['full_text'] or len(data['full_text']) < 100:
            return False
        
        return True
    
    def clear_cache(self):
        """Clear PDF cache"""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info("PDF cache cleared")
    
    def get_cache_size(self) -> int:
        """Get cache size in bytes"""
        total_size = 0
        for pdf_file in self.cache_dir.glob('*.pdf'):
            total_size += pdf_file.stat().st_size
        return total_size
    
    def get_cache_count(self) -> int:
        """Get number of cached PDFs"""
        return len(list(self.cache_dir.glob('*.pdf')))


def main():
    """Test PDF parser"""
    import json
    
    # Test with a sample paper
    paper = {
        'doi': '10.3390/s20216013',
        'title': 'Critical Review of Electrochemical Glucose Sensing',
        'abstract': 'This is a test abstract...',
        'pdf_url': 'https://www.mdpi.com/1424-8220/20/21/6013/pdf'
    }
    
    parser = PDFParser()
    result = parser.extract(paper)
    
    if result.success:
        print(f"✅ Extraction successful!")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Method: {result.data['extraction_method']}")
        print(f"Text length: {len(result.data['full_text'])} chars")
        print(f"Sections: {list(result.data['sections'].keys())}")
        print(f"Pages: {result.data['page_count']}")
    else:
        print(f"❌ Extraction failed: {result.error}")


if __name__ == "__main__":
    main()
