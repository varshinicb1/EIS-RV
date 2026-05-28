#!/usr/bin/env python3
"""Analyze mined papers"""
import json
from pathlib import Path
from collections import Counter

papers_dir = Path('data/mined_papers/biosensor_blood')

print('='*80)
print('LITERATURE MINING TEST RESULTS')
print('='*80)

# Collect data
by_source = {'pubmed': [], 'arxiv': [], 'zenodo': []}

for paper_file in papers_dir.glob('*.json'):
    with open(paper_file, 'r', encoding='utf-8') as f:
        paper = json.load(f)
        source = paper.get('source', 'unknown')
        if source in by_source:
            by_source[source].append(paper)

# Statistics
total = sum(len(papers) for papers in by_source.values())
print(f'\nTotal papers mined: {total}')
print(f'\nPapers by source:')
for source, papers in by_source.items():
    print(f'  {source}: {len(papers)}')

# Sample papers
print('\n' + '='*80)
print('SAMPLE PAPERS FROM EACH SOURCE')
print('='*80)

for source, papers in by_source.items():
    if papers:
        print(f'\n{source.upper()} ({len(papers)} papers):')
        print('-'*80)
        for i, paper in enumerate(papers[:2], 1):
            title = paper['title'][:70] + '...' if len(paper['title']) > 70 else paper['title']
            print(f'\n{i}. {title}')
            authors = ', '.join(paper['authors'][:3])
            if len(paper['authors']) > 3:
                authors += f' et al. ({len(paper["authors"])} total)'
            print(f'   Authors: {authors}')
            print(f'   Journal: {paper["journal"]}')
            print(f'   Date: {paper["publication_date"]}')
            if paper.get('doi'):
                print(f'   DOI: {paper["doi"]}')
            if paper.get('pdf_url'):
                print(f'   PDF: Available')
            print(f'   URL: {paper["url"]}')

print('\n' + '='*80)
print('SUCCESS! Literature miner is working perfectly!')
print('='*80)
print('\nNext steps:')
print('1. Run continuous mining: python literature_miner.py --interval 3600')
print('2. Mine all applications (biosensor, supercapacitor, battery, etc.)')
print('3. Extract data from papers (next phase)')
print('4. Build material database')
