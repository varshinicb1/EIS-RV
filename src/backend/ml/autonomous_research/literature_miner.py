#!/usr/bin/env python3
"""
Literature Mining Engine
Continuously mines scientific literature for electrochemistry data

Mines from:
- PubMed / PMC (open access)
- arXiv (preprints)
- Zenodo (datasets)
- Publisher APIs (Springer, Elsevier, etc.)
"""

import os
import time
import json
import requests
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Paper:
    """Represents a scientific paper"""
    title: str
    authors: List[str]
    abstract: str
    doi: Optional[str]
    pmid: Optional[str]
    arxiv_id: Optional[str]
    publication_date: str
    journal: str
    url: str
    pdf_url: Optional[str]
    keywords: List[str]
    source: str  # 'pubmed', 'arxiv', 'zenodo', etc.
    relevance_score: float = 0.0
    mined_date: str = datetime.now().isoformat()


class LiteratureMiner:
    """
    Autonomous literature mining engine
    Runs 24/7, continuously discovering new research
    """
    
    # Search keywords by application
    SEARCH_KEYWORDS = {
        'biosensor_blood': [
            'glucose biosensor', 'lactate sensor', 'cholesterol detection',
            'hemoglobin sensor', 'blood glucose electrochemical',
            'screen printed electrode blood', 'nanomaterial biosensor blood',
            'graphene biosensor glucose', 'carbon nanotube sensor blood'
        ],
        
        'biosensor_water': [
            'heavy metal detection electrochemical', 'lead sensor water',
            'cadmium detection', 'arsenic sensor', 'water quality sensor',
            'electrochemical water pollutant', 'screen printed electrode water'
        ],
        
        'biosensor_food': [
            'food safety sensor electrochemical', 'pesticide detection',
            'mycotoxin sensor', 'food contaminant electrochemical'
        ],
        
        'supercapacitor': [
            'supercapacitor nanomaterial', 'pseudocapacitor electrode',
            'EDLC carbon', 'metal oxide supercapacitor',
            'conducting polymer supercapacitor', 'graphene supercapacitor',
            'specific capacitance', 'energy density supercapacitor'
        ],
        
        'battery': [
            'lithium ion battery electrode', 'sodium ion battery material',
            'coin cell battery', 'cathode material battery',
            'anode material lithium', 'solid electrolyte battery',
            'battery nanomaterial', 'capacity retention battery'
        ],
        
        'raman': [
            'raman spectroscopy material', 'SERS detection',
            'surface enhanced raman', 'raman material identification'
        ],
        
        'cv': [
            'cyclic voltammetry', 'electrochemical characterization CV',
            'redox potential cyclic voltammetry'
        ],
        
        'eis': [
            'electrochemical impedance spectroscopy', 'EIS battery',
            'impedance spectroscopy electrode', 'nyquist plot'
        ],
        
        'gcd': [
            'galvanostatic charge discharge', 'GCD battery',
            'charge discharge cycling', 'battery lifetime GCD'
        ]
    }
    
    def __init__(self, output_dir: Path, mining_interval: int = 3600):
        """
        Initialize literature miner
        
        Args:
            output_dir: Directory to save mined papers
            mining_interval: Time between mining runs (seconds)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.mining_interval = mining_interval
        self.last_mined = {}
        
        # Load state
        self.state_file = self.output_dir / 'mining_state.json'
        self.load_state()
        
        logger.info(f"Literature miner initialized")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Mining interval: {mining_interval}s ({mining_interval/3600:.1f}h)")
    
    def load_state(self):
        """Load mining state from file"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                self.last_mined = state.get('last_mined', {})
            logger.info(f"Loaded state: {len(self.last_mined)} keywords tracked")
    
    def save_state(self):
        """Save mining state to file"""
        state = {
            'last_mined': self.last_mined,
            'last_save': datetime.now().isoformat()
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def mine_continuously(self):
        """Run continuous mining loop"""
        logger.info("="*80)
        logger.info("Starting continuous literature mining")
        logger.info("="*80)
        
        iteration = 0
        
        while True:
            iteration += 1
            logger.info(f"\n{'='*80}")
            logger.info(f"Mining iteration {iteration}")
            logger.info(f"Time: {datetime.now().isoformat()}")
            logger.info(f"{'='*80}")
            
            try:
                # Mine all applications
                total_papers = 0
                
                for application, keywords in self.SEARCH_KEYWORDS.items():
                    logger.info(f"\nMining: {application}")
                    logger.info(f"Keywords: {len(keywords)}")
                    
                    app_papers = self.mine_application(application, keywords)
                    total_papers += len(app_papers)
                    
                    logger.info(f"Found {len(app_papers)} papers for {application}")
                
                logger.info(f"\nTotal papers mined: {total_papers}")
                
                # Save state
                self.save_state()
                
                # Wait for next iteration
                logger.info(f"\nWaiting {self.mining_interval}s until next mining...")
                time.sleep(self.mining_interval)
            
            except KeyboardInterrupt:
                logger.info("\nMining stopped by user")
                break
            
            except Exception as e:
                logger.error(f"Mining error: {e}")
                logger.info("Continuing after error...")
                time.sleep(60)  # Wait 1 minute before retry
    
    def mine_application(self, application: str, keywords: List[str]) -> List[Paper]:
        """Mine papers for specific application"""
        all_papers = []
        
        # Use ThreadPoolExecutor for parallel mining
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            
            for keyword in keywords:
                # Check if we need to mine this keyword
                if self.should_mine_keyword(keyword):
                    # Submit mining tasks
                    futures.append(executor.submit(self.mine_keyword, keyword, application))
            
            # Collect results
            for future in as_completed(futures):
                try:
                    papers = future.result()
                    all_papers.extend(papers)
                except Exception as e:
                    logger.error(f"Keyword mining failed: {e}")
        
        # Remove duplicates
        unique_papers = self.deduplicate_papers(all_papers)
        
        # Save papers
        self.save_papers(unique_papers, application)
        
        return unique_papers
    
    def should_mine_keyword(self, keyword: str) -> bool:
        """Check if keyword should be mined"""
        if keyword not in self.last_mined:
            return True
        
        last_time = datetime.fromisoformat(self.last_mined[keyword])
        time_since = datetime.now() - last_time
        
        # Mine if more than mining_interval has passed
        return time_since.total_seconds() >= self.mining_interval
    
    def mine_keyword(self, keyword: str, application: str) -> List[Paper]:
        """Mine papers for specific keyword"""
        logger.info(f"  Mining: '{keyword}'")
        
        papers = []
        
        # Mine from different sources
        try:
            papers.extend(self.search_pubmed(keyword))
        except Exception as e:
            logger.warning(f"PubMed search failed: {e}")
        
        try:
            papers.extend(self.search_arxiv(keyword))
        except Exception as e:
            logger.warning(f"arXiv search failed: {e}")
        
        try:
            papers.extend(self.search_zenodo(keyword))
        except Exception as e:
            logger.warning(f"Zenodo search failed: {e}")
        
        # Update last mined time
        self.last_mined[keyword] = datetime.now().isoformat()
        
        logger.info(f"    Found {len(papers)} papers")
        
        return papers
    
    def search_pubmed(self, keyword: str, max_results: int = 20) -> List[Paper]:
        """Search PubMed for papers"""
        papers = []
        
        try:
            # Use E-utilities API
            base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
            
            # Search
            search_url = f"{base_url}esearch.fcgi"
            search_params = {
                'db': 'pubmed',
                'term': keyword,
                'retmax': max_results,
                'retmode': 'json',
                'sort': 'relevance'
            }
            
            response = requests.get(search_url, params=search_params, timeout=30)
            response.raise_for_status()
            
            search_results = response.json()
            pmids = search_results.get('esearchresult', {}).get('idlist', [])
            
            if not pmids:
                return papers
            
            # Fetch details
            fetch_url = f"{base_url}esummary.fcgi"
            fetch_params = {
                'db': 'pubmed',
                'id': ','.join(pmids),
                'retmode': 'json'
            }
            
            response = requests.get(fetch_url, params=fetch_params, timeout=30)
            response.raise_for_status()
            
            fetch_results = response.json()
            
            for pmid in pmids:
                try:
                    result = fetch_results['result'][pmid]
                    
                    paper = Paper(
                        title=result.get('title', ''),
                        authors=[author['name'] for author in result.get('authors', [])],
                        abstract='',  # Need separate fetch for abstract
                        doi=result.get('elocationid', '').replace('doi: ', ''),
                        pmid=pmid,
                        arxiv_id=None,
                        publication_date=result.get('pubdate', ''),
                        journal=result.get('source', ''),
                        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        pdf_url=None,
                        keywords=[keyword],
                        source='pubmed'
                    )
                    
                    papers.append(paper)
                
                except Exception as e:
                    logger.warning(f"Failed to parse PubMed result {pmid}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"PubMed search failed: {e}")
        
        return papers
    
    def search_arxiv(self, keyword: str, max_results: int = 20) -> List[Paper]:
        """Search arXiv for papers"""
        papers = []
        
        try:
            # Use arXiv API
            base_url = "http://export.arxiv.org/api/query"
            
            params = {
                'search_query': f'all:{keyword}',
                'start': 0,
                'max_results': max_results,
                'sortBy': 'relevance',
                'sortOrder': 'descending'
            }
            
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            
            # Parse XML response
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            # Namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            for entry in root.findall('atom:entry', ns):
                try:
                    title = entry.find('atom:title', ns).text.strip()
                    abstract = entry.find('atom:summary', ns).text.strip()
                    published = entry.find('atom:published', ns).text
                    arxiv_id = entry.find('atom:id', ns).text.split('/abs/')[-1]
                    
                    authors = []
                    for author in entry.findall('atom:author', ns):
                        name = author.find('atom:name', ns).text
                        authors.append(name)
                    
                    paper = Paper(
                        title=title,
                        authors=authors,
                        abstract=abstract,
                        doi=None,
                        pmid=None,
                        arxiv_id=arxiv_id,
                        publication_date=published,
                        journal='arXiv',
                        url=f"https://arxiv.org/abs/{arxiv_id}",
                        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                        keywords=[keyword],
                        source='arxiv'
                    )
                    
                    papers.append(paper)
                
                except Exception as e:
                    logger.warning(f"Failed to parse arXiv entry: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"arXiv search failed: {e}")
        
        return papers
    
    def search_zenodo(self, keyword: str, max_results: int = 20) -> List[Paper]:
        """Search Zenodo for datasets"""
        papers = []
        
        try:
            # Use Zenodo API
            base_url = "https://zenodo.org/api/records/"
            
            params = {
                'q': keyword,
                'size': max_results,
                'sort': 'mostrecent'
            }
            
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            
            results = response.json()
            
            for hit in results.get('hits', {}).get('hits', []):
                try:
                    metadata = hit.get('metadata', {})
                    
                    # Get PDF/data URL
                    files = hit.get('files', [])
                    pdf_url = files[0].get('links', {}).get('self') if files else None
                    
                    paper = Paper(
                        title=metadata.get('title', ''),
                        authors=[creator.get('name', '') for creator in metadata.get('creators', [])],
                        abstract=metadata.get('description', ''),
                        doi=metadata.get('doi', ''),
                        pmid=None,
                        arxiv_id=None,
                        publication_date=metadata.get('publication_date', ''),
                        journal='Zenodo',
                        url=hit.get('links', {}).get('self', ''),
                        pdf_url=pdf_url,
                        keywords=[keyword],
                        source='zenodo'
                    )
                    
                    papers.append(paper)
                
                except Exception as e:
                    logger.warning(f"Failed to parse Zenodo result: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Zenodo search failed: {e}")
        
        return papers
    
    def deduplicate_papers(self, papers: List[Paper]) -> List[Paper]:
        """Remove duplicate papers"""
        seen = set()
        unique = []
        
        for paper in papers:
            # Create unique identifier
            identifier = paper.doi or paper.pmid or paper.arxiv_id or paper.title
            
            if identifier not in seen:
                seen.add(identifier)
                unique.append(paper)
        
        return unique
    
    def save_papers(self, papers: List[Paper], application: str):
        """Save papers to disk"""
        if not papers:
            return
        
        # Create application directory
        app_dir = self.output_dir / application
        app_dir.mkdir(parents=True, exist_ok=True)
        
        # Save each paper
        for paper in papers:
            # Create filename from title
            filename = self.sanitize_filename(paper.title) + '.json'
            filepath = app_dir / filename
            
            # Save paper metadata
            with open(filepath, 'w') as f:
                json.dump(asdict(paper), f, indent=2)
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename"""
        # Remove invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Limit length
        if len(filename) > 100:
            filename = filename[:100]
        
        return filename


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Literature Mining Engine')
    parser.add_argument('--output', type=str, default='data/mined_papers',
                        help='Output directory for mined papers')
    parser.add_argument('--interval', type=int, default=3600,
                        help='Mining interval in seconds (default: 3600 = 1 hour)')
    parser.add_argument('--test', action='store_true',
                        help='Run single test iteration')
    
    args = parser.parse_args()
    
    # Create miner
    miner = LiteratureMiner(
        output_dir=Path(args.output),
        mining_interval=args.interval
    )
    
    if args.test:
        # Test mode: mine once
        logger.info("Running in test mode (single iteration)")
        papers = miner.mine_application('biosensor_blood', ['glucose biosensor'])
        logger.info(f"Test complete: {len(papers)} papers found")
    else:
        # Production mode: continuous mining
        miner.mine_continuously()


if __name__ == "__main__":
    main()
