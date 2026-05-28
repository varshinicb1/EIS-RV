"""
Base Extractor Class
Abstract base for all extractors
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result from an extraction operation"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    error: Optional[str] = None
    method: str = "unknown"


class BaseExtractor(ABC):
    """
    Abstract base class for all extractors
    
    All extractors must implement:
    - extract(): Main extraction method
    - validate(): Validate extracted data
    """
    
    def __init__(self, name: str):
        """
        Initialize extractor
        
        Args:
            name: Extractor name for logging
        """
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def extract(self, paper: Dict[str, Any]) -> ExtractionResult:
        """
        Extract data from paper
        
        Args:
            paper: Paper metadata dict
        
        Returns:
            ExtractionResult with extracted data
        """
        pass
    
    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> bool:
        """
        Validate extracted data
        
        Args:
            data: Extracted data dict
        
        Returns:
            True if valid, False otherwise
        """
        pass
    
    def log_success(self, paper_id: str, confidence: float):
        """Log successful extraction"""
        self.logger.info(
            f"[{self.name}] Successfully extracted from {paper_id} "
            f"(confidence: {confidence:.2f})"
        )
    
    def log_failure(self, paper_id: str, error: str):
        """Log failed extraction"""
        self.logger.warning(
            f"[{self.name}] Failed to extract from {paper_id}: {error}"
        )
    
    def log_partial(self, paper_id: str, fields: int, total: int):
        """Log partial extraction"""
        self.logger.info(
            f"[{self.name}] Partial extraction from {paper_id}: "
            f"{fields}/{total} fields ({fields/total*100:.1f}%)"
        )
