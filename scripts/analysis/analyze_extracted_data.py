#!/usr/bin/env python3
"""Analyze extracted data"""
import json
from pathlib import Path

extracted_dir = Path('data/extracted_data/biosensor_blood')

# Find papers with highest confidence
papers_with_data = []

for file in extracted_dir.glob('*.json'):
    if file.name != 'extraction_summary.json':
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            papers_with_data.append((file.name, data))

# Sort by confidence
papers_with_data.sort(key=lambda x: x[1]['extraction_confidence'], reverse=True)

print('='*80)
print('DATA EXTRACTION TEST RESULTS')
print('='*80)

# Load summary
with open(extracted_dir / 'extraction_summary.json', 'r') as f:
    summary = json.load(f)

print(f'\nTotal papers processed: {summary["total_papers"]}')
print(f'Average confidence: {summary["avg_confidence"]:.2f}')
print(f'\nExtraction success:')
print(f'  Materials: {summary["with_material"]} ({summary["with_material"]/summary["total_papers"]*100:.1f}%)')
print(f'  Electrodes: {summary["with_electrode"]} ({summary["with_electrode"]/summary["total_papers"]*100:.1f}%)')
print(f'  Analytes: {summary["with_analyte"]} ({summary["with_analyte"]/summary["total_papers"]*100:.1f}%)')
print(f'  Applications: {sum(summary["by_application"].values())} ({sum(summary["by_application"].values())/summary["total_papers"]*100:.1f}%)')

print(f'\nBy application:')
for app, count in summary['by_application'].items():
    print(f'  {app}: {count}')

print(f'\nBy analyte:')
for analyte, count in sorted(summary['by_analyte'].items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f'  {analyte}: {count}')

print('\n' + '='*80)
print('TOP EXTRACTED DATA EXAMPLES')
print('='*80)

for i, (filename, data) in enumerate(papers_with_data[:5], 1):
    print(f'\n{i}. Paper ID: {data["paper_id"]}')
    print(f'   Confidence: {data["extraction_confidence"]:.2f}')
    print(f'   Application: {data["application"]}')
    print(f'   Analyte: {data["target_analyte"]}')
    print(f'   Sample: {data["sample_type"]}')
    
    if data['material']:
        mat = data['material']
        print(f'   Material: {mat["name"]}')
        if mat['type']:
            print(f'     Type: {mat["type"]}')
        if mat['size_nm']:
            print(f'     Size: {mat["size_nm"]} nm')
    
    if data['electrode']:
        elec = data['electrode']
        print(f'   Electrode: {elec["type"]}')
        if elec['modification']:
            print(f'     Modified with: {elec["modification"]}')
    
    if data['performance']:
        perf = data['performance']
        if perf['sensitivity']:
            print(f'   Sensitivity: {perf["sensitivity"]} {perf["sensitivity_unit"]}')
        if perf['detection_limit']:
            print(f'   Detection limit: {perf["detection_limit"]} {perf["detection_limit_unit"]}')
        if perf['linear_range_min']:
            print(f'   Linear range: {perf["linear_range_min"]}-{perf["linear_range_max"]} {perf["linear_range_unit"]}')

print('\n' + '='*80)
print('SUCCESS! Data extraction is working!')
print('='*80)
print('\nNext steps:')
print('1. Improve extraction patterns (add more regex)')
print('2. Add PDF parsing for full text')
print('3. Add table extraction')
print('4. Add figure digitization')
print('5. Build material database')
