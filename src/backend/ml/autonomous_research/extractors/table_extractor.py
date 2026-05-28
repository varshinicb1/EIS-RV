"""
Table Extraction Engine
Extracts performance metrics and experimental conditions from tables
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import logging

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logging.warning("pdfplumber not available. Install with: pip install pdfplumber")

try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    logging.warning("camelot not available. Install with: pip install camelot-py[cv]")

from .base_extractor import BaseExtractor, ExtractionResult

logger = logging.getLogger(__name__)


@dataclass
class TableData:
    """Extracted table data"""
    caption: str
    headers: List[str]
    rows: List[List[str]]
    table_type: str  # 'performance', 'experimental', 'comparison', 'other'
    page_number: int


@dataclass
class PerformanceMetrics:
    """Performance metrics extracted from tables"""
    sensitivity: Optional[Tuple[float, str]] = None  # (value, unit)
    detection_limit: Optional[Tuple[float, str]] = None
    linear_range: Optional[Tuple[float, float, str]] = None  # (min, max, unit)
    selectivity: Dict[str, float] = None
    stability_days: Optional[int] = None
    reproducibility_rsd: Optional[float] = None
    response_time_s: Optional[float] = None


class TableExtractor(BaseExtractor):
    """
    Table Extraction Engine
    
    Features:
    - Detects tables in PDFs
    - Extracts table structure (rows, columns, headers)
    - Parses performance metrics
    - Parses experimental conditions
    - Handles merged cells and complex layouts
    """
    
    # Performance metric patterns
    METRIC_PATTERNS = {
        'sensitivity': r'sensitivity|sens\.',
        'detection_limit': r'detection limit|LOD|limit of detection',
        'linear_range': r'linear range|linearity',
        'selectivity': r'selectivity|interference',
        'stability': r'stability|lifetime',
        'reproducibility': r'reproducibility|RSD|precision',
        'response_time': r'response time|time'
    }
    
    # Unit patterns
    UNIT_PATTERNS = {
        'sensitivity': r'(μA|uA|µA|nA|mA)/(μM|uM|µM|mM|nM)',
        'detection_limit': r'(nM|μM|uM|µM|mM|pM|ppb|ppt)',
        'linear_range': r'(nM|μM|uM|µM|mM|pM)',
        'time': r'(s|sec|min|h|hour|day)',
        'percent': r'%|percent'
    }
    
    def __init__(self, cache_dir: str = "data/pdf_cache"):
        """
        Initialize table extractor
        
        Args:
            cache_dir: Directory with cached PDFs
        """
        super().__init__("TableExtractor")
        self.cache_dir = Path(cache_dir)
        
        if not PDFPLUMBER_AVAILABLE and not CAMELOT_AVAILABLE:
            raise ImportError(
                "Neither pdfplumber nor camelot available. "
                "Install with: pip install pdfplumber camelot-py[cv]"
            )
    
    def extract(self, paper: Dict[str, Any]) -> ExtractionResult:
        """
        Extract tables from paper PDF
        
        Args:
            paper: Paper metadata dict
        
        Returns:
            ExtractionResult with extracted tables and metrics
        """
        paper_id = paper.get('doi') or paper.get('pmid') or paper.get('arxiv_id', 'unknown')
        
        # Get PDF path
        safe_id = re.sub(r'[^\w\-_]', '_', paper_id)
        pdf_path = self.cache_dir / f"{safe_id}.pdf"
        
        if not pdf_path.exists():
            return ExtractionResult(
                success=False,
                error="PDF not found in cache",
                method='table_extractor'
            )
        
        try:
            # Extract tables
            tables = self._extract_tables(pdf_path)
            
            if not tables:
                return ExtractionResult(
                    success=False,
                    error="No tables found",
                    method='table_extractor'
                )
            
            # Parse performance metrics
            metrics = self._parse_performance_metrics(tables)
            
            # Parse experimental conditions
            conditions = self._parse_experimental_conditions(tables)
            
            # Calculate confidence
            confidence = self._calculate_confidence(tables, metrics, conditions)
            
            self.log_success(paper_id, confidence)
            
            return ExtractionResult(
                success=True,
                data={
                    'tables': [self._table_to_dict(t) for t in tables],
                    'performance_metrics': metrics,
                    'experimental_conditions': conditions,
                    'table_count': len(tables)
                },
                confidence=confidence,
                method='table_extractor'
            )
        
        except Exception as e:
            self.log_failure(paper_id, str(e))
            return ExtractionResult(
                success=False,
                error=str(e),
                method='table_extractor'
            )
    
    def _extract_tables(self, pdf_path: Path) -> List[TableData]:
        """
        Extract all tables from PDF
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            List of TableData objects
        """
        tables = []
        
        # Try pdfplumber first
        if PDFPLUMBER_AVAILABLE:
            tables = self._extract_with_pdfplumber(pdf_path)
        
        # Try camelot if pdfplumber failed or found no tables
        if not tables and CAMELOT_AVAILABLE:
            tables = self._extract_with_camelot(pdf_path)
        
        return tables
    
    def _extract_with_pdfplumber(self, pdf_path: Path) -> List[TableData]:
        """Extract tables using pdfplumber"""
        tables = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    page_tables = page.extract_tables()
                    
                    for table in page_tables:
                        if not table or len(table) < 2:
                            continue
                        
                        # First row is usually headers
                        headers = table[0]
                        rows = table[1:]
                        
                        # Classify table type
                        table_type = self._classify_table(headers, rows)
                        
                        tables.append(TableData(
                            caption="",  # pdfplumber doesn't extract captions
                            headers=headers,
                            rows=rows,
                            table_type=table_type,
                            page_number=page_num
                        ))
        
        except Exception as e:
            self.logger.warning(f"pdfplumber table extraction failed: {e}")
        
        return tables
    
    def _extract_with_camelot(self, pdf_path: Path) -> List[TableData]:
        """Extract tables using camelot"""
        tables = []
        
        try:
            # Extract tables
            camelot_tables = camelot.read_pdf(str(pdf_path), pages='all', flavor='lattice')
            
            for table in camelot_tables:
                df = table.df
                
                if df.empty or len(df) < 2:
                    continue
                
                # First row as headers
                headers = df.iloc[0].tolist()
                rows = df.iloc[1:].values.tolist()
                
                # Classify table type
                table_type = self._classify_table(headers, rows)
                
                tables.append(TableData(
                    caption="",
                    headers=headers,
                    rows=rows,
                    table_type=table_type,
                    page_number=table.page
                ))
        
        except Exception as e:
            self.logger.warning(f"camelot table extraction failed: {e}")
        
        return tables
    
    def _classify_table(self, headers: List[str], rows: List[List[str]]) -> str:
        """
        Classify table type
        
        Args:
            headers: Table headers
            rows: Table rows
        
        Returns:
            Table type: 'performance', 'experimental', 'comparison', 'other'
        """
        # Combine headers for analysis
        header_text = ' '.join(str(h).lower() for h in headers if h)
        
        # Check for performance metrics
        performance_keywords = ['sensitivity', 'detection', 'limit', 'linear', 'range', 'lod']
        if any(kw in header_text for kw in performance_keywords):
            return 'performance'
        
        # Check for experimental conditions
        experimental_keywords = ['temperature', 'ph', 'voltage', 'current', 'time', 'concentration']
        if any(kw in header_text for kw in experimental_keywords):
            return 'experimental'
        
        # Check for comparison
        comparison_keywords = ['comparison', 'vs', 'versus', 'this work', 'ref']
        if any(kw in header_text for kw in comparison_keywords):
            return 'comparison'
        
        return 'other'
    
    def _parse_performance_metrics(self, tables: List[TableData]) -> Dict[str, Any]:
        """
        Parse performance metrics from tables
        
        Args:
            tables: List of extracted tables
        
        Returns:
            Dict of performance metrics
        """
        metrics = {}
        
        for table in tables:
            if table.table_type != 'performance':
                continue
            
            # Parse each metric type
            for metric_name, pattern in self.METRIC_PATTERNS.items():
                value = self._extract_metric_from_table(table, pattern, metric_name)
                if value:
                    metrics[metric_name] = value
        
        return metrics
    
    def _extract_metric_from_table(self, table: TableData, 
                                   pattern: str, metric_name: str) -> Optional[Any]:
        """
        Extract specific metric from table
        
        Args:
            table: TableData object
            pattern: Regex pattern to match metric
            metric_name: Name of metric
        
        Returns:
            Extracted value or None
        """
        # Find column with metric
        metric_col = None
        for i, header in enumerate(table.headers):
            if header and re.search(pattern, str(header), re.IGNORECASE):
                metric_col = i
                break
        
        if metric_col is None:
            return None
        
        # Extract values from column
        values = []
        for row in table.rows:
            if metric_col < len(row):
                cell = str(row[metric_col])
                
                # Extract numeric value and unit
                value_match = re.search(r'([0-9.]+)\s*([a-zA-Zμµ/]+)?', cell)
                if value_match:
                    value = float(value_match.group(1))
                    unit = value_match.group(2) or ''
                    values.append((value, unit))
        
        # Return first value (usually "this work")
        return values[0] if values else None
    
    def _parse_experimental_conditions(self, tables: List[TableData]) -> Dict[str, Any]:
        """
        Parse experimental conditions from tables
        
        Args:
            tables: List of extracted tables
        
        Returns:
            Dict of experimental conditions
        """
        conditions = {}
        
        for table in tables:
            if table.table_type != 'experimental':
                continue
            
            # Extract common conditions
            conditions_patterns = {
                'ph': r'\bph\b',
                'temperature': r'temp|temperature',
                'voltage': r'voltage|potential|V\b',
                'scan_rate': r'scan rate',
                'concentration': r'concentration|conc\.'
            }
            
            for cond_name, pattern in conditions_patterns.items():
                value = self._extract_metric_from_table(table, pattern, cond_name)
                if value:
                    conditions[cond_name] = value
        
        return conditions
    
    def _calculate_confidence(self, tables: List[TableData], 
                             metrics: Dict, conditions: Dict) -> float:
        """Calculate extraction confidence"""
        confidence = 0.0
        
        # Base confidence for finding tables
        if tables:
            confidence += 0.3
        
        # Bonus for performance tables
        perf_tables = [t for t in tables if t.table_type == 'performance']
        if perf_tables:
            confidence += 0.3
        
        # Bonus for extracted metrics
        if metrics:
            confidence += 0.2 * (len(metrics) / len(self.METRIC_PATTERNS))
        
        # Bonus for experimental conditions
        if conditions:
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    def _table_to_dict(self, table: TableData) -> Dict[str, Any]:
        """Convert TableData to dict"""
        return {
            'caption': table.caption,
            'headers': table.headers,
            'rows': table.rows,
            'type': table.table_type,
            'page': table.page_number
        }
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """Validate extracted table data"""
        required_fields = ['tables', 'table_count']
        
        for field in required_fields:
            if field not in data:
                return False
        
        if data['table_count'] == 0:
            return False
        
        return True


def main():
    """Test table extractor"""
    # Test with a sample paper
    paper = {
        'doi': '10.3390/s20216013',
        'title': 'Critical Review of Electrochemical Glucose Sensing'
    }
    
    extractor = TableExtractor()
    result = extractor.extract(paper)
    
    if result.success:
        print(f"✅ Extraction successful!")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Tables found: {result.data['table_count']}")
        print(f"Performance metrics: {result.data['performance_metrics']}")
    else:
        print(f"❌ Extraction failed: {result.error}")


if __name__ == "__main__":
    main()
