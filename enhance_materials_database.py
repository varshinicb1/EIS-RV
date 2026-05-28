"""
Enhance Materials Database with Comprehensive Properties
=========================================================
Expands the materials database with additional properties from literature
and research pipeline data.

Adds:
- Detailed electrochemical properties
- Synthesis methods and costs
- Performance metrics
- Literature references
- Application domains

Author: VidyuthLabs
Date: May 13, 2026
"""

import json
from pathlib import Path
from typing import Dict, List, Any

# Enhanced material properties from literature
ENHANCED_MATERIALS = {
    "Graphene": {
        "capacitance_range_F_g": [200, 300],
        "typical_capacitance_F_g": 250,
        "energy_density_Wh_kg": 85,
        "power_density_W_kg": 100000,
        "cycle_life": 100000,
        "cost_per_kg_usd": 100,
        "synthesis_methods": ["CVD", "Mechanical exfoliation", "Chemical reduction"],
        "best_synthesis": "CVD on copper foil",
        "electrolytes": ["Aqueous", "Organic", "Ionic liquid"],
        "potential_window_V": {"aqueous": 0.8, "organic": 2.7, "ionic_liquid": 3.5},
        "applications": ["Supercapacitors", "Batteries", "Sensors", "Composites"],
        "advantages": ["High conductivity", "Large surface area", "Excellent mechanical properties"],
        "disadvantages": ["Expensive", "Difficult to process", "Aggregation issues"],
        "references": [
            "Zhu et al. (2011), Science, 332, 1537",
            "El-Kady et al. (2012), Science, 335, 1326"
        ]
    },
    "Reduced Graphene Oxide": {
        "capacitance_range_F_g": [180, 250],
        "typical_capacitance_F_g": 220,
        "energy_density_Wh_kg": 70,
        "power_density_W_kg": 80000,
        "cycle_life": 50000,
        "cost_per_kg_usd": 50,
        "synthesis_methods": ["Thermal reduction", "Chemical reduction", "Electrochemical reduction"],
        "best_synthesis": "Hydrazine reduction at 100°C",
        "electrolytes": ["Aqueous", "Organic"],
        "potential_window_V": {"aqueous": 1.0, "organic": 2.5},
        "applications": ["Supercapacitors", "Sensors", "Composites"],
        "advantages": ["Lower cost than graphene", "Scalable", "Good conductivity"],
        "disadvantages": ["Lower performance than pristine graphene", "Residual oxygen groups"],
        "references": [
            "Stoller et al. (2008), Nano Lett., 8, 3498",
            "Wang et al. (2009), J. Phys. Chem. C, 113, 13103"
        ]
    },
    "MXene (Ti3C2Tx)": {
        "capacitance_range_F_g": [300, 450],
        "typical_capacitance_F_g": 380,
        "energy_density_Wh_kg": 120,
        "power_density_W_kg": 150000,
        "cycle_life": 10000,
        "cost_per_kg_usd": 200,
        "synthesis_methods": ["HF etching", "LiF/HCl etching", "Electrochemical etching"],
        "best_synthesis": "LiF/HCl etching of Ti3AlC2",
        "electrolytes": ["Aqueous", "Organic", "Ionic liquid"],
        "potential_window_V": {"aqueous": 1.2, "organic": 3.0, "ionic_liquid": 3.5},
        "applications": ["Supercapacitors", "Batteries", "EMI shielding", "Sensors"],
        "advantages": ["Very high capacitance", "Excellent conductivity", "Hydrophilic"],
        "disadvantages": ["Oxidation in air", "Limited cycle life", "Expensive"],
        "references": [
            "Lukatskaya et al. (2013), Science, 341, 1502",
            "Ghidiu et al. (2014), Nature, 516, 78"
        ]
    },
    "Polyaniline (PANI)": {
        "capacitance_range_F_g": [400, 550],
        "typical_capacitance_F_g": 480,
        "energy_density_Wh_kg": 150,
        "power_density_W_kg": 50000,
        "cycle_life": 5000,
        "cost_per_kg_usd": 20,
        "synthesis_methods": ["Chemical polymerization", "Electrochemical polymerization"],
        "best_synthesis": "Oxidative polymerization with (NH4)2S2O8",
        "electrolytes": ["Aqueous acidic"],
        "potential_window_V": {"aqueous": 0.8},
        "applications": ["Supercapacitors", "Batteries", "Sensors", "Corrosion protection"],
        "advantages": ["Very high capacitance", "Low cost", "Easy synthesis"],
        "disadvantages": ["Poor cycle life", "Swelling/shrinking", "Acidic electrolyte required"],
        "references": [
            "Snook et al. (2011), J. Power Sources, 196, 1",
            "Wang et al. (2013), Chem. Soc. Rev., 42, 3088"
        ]
    },
    "Ruthenium Oxide (RuO2)": {
        "capacitance_range_F_g": [600, 800],
        "typical_capacitance_F_g": 720,
        "energy_density_Wh_kg": 200,
        "power_density_W_kg": 200000,
        "cycle_life": 100000,
        "cost_per_kg_usd": 5000,
        "synthesis_methods": ["Sol-gel", "Hydrothermal", "Electrodeposition"],
        "best_synthesis": "Sol-gel with RuCl3 precursor",
        "electrolytes": ["Aqueous", "Organic"],
        "potential_window_V": {"aqueous": 1.2, "organic": 2.5},
        "applications": ["Supercapacitors", "Electrocatalysis"],
        "advantages": ["Highest capacitance", "Excellent cycle life", "Fast kinetics"],
        "disadvantages": ["Very expensive", "Toxic", "Limited availability"],
        "references": [
            "Zheng et al. (1995), J. Electrochem. Soc., 142, 2699",
            "Hu et al. (2006), Nano Lett., 6, 2690"
        ]
    },
    "Manganese Dioxide (MnO2)": {
        "capacitance_range_F_g": [200, 350],
        "typical_capacitance_F_g": 280,
        "energy_density_Wh_kg": 90,
        "power_density_W_kg": 60000,
        "cycle_life": 10000,
        "cost_per_kg_usd": 10,
        "synthesis_methods": ["Hydrothermal", "Electrodeposition", "Chemical precipitation"],
        "best_synthesis": "Hydrothermal from KMnO4 at 140°C",
        "electrolytes": ["Aqueous neutral/alkaline"],
        "potential_window_V": {"aqueous": 1.0},
        "applications": ["Supercapacitors", "Batteries", "Catalysis"],
        "advantages": ["Low cost", "Abundant", "Environmentally friendly"],
        "disadvantages": ["Poor conductivity", "Moderate cycle life", "Dissolution in acidic media"],
        "references": [
            "Wei et al. (2011), Adv. Mater., 23, 3440",
            "Devaraj & Munichandraiah (2008), J. Phys. Chem. C, 112, 4406"
        ]
    },
    "Nickel Manganate (NiMn₂O₄)": {
        "capacitance_range_F_g": [250, 320],
        "typical_capacitance_F_g": 280,
        "energy_density_Wh_kg": 95,
        "power_density_W_kg": 70000,
        "cycle_life": 5000,
        "cost_per_kg_usd": 15,
        "synthesis_methods": ["Solution combustion", "Hydrothermal", "Co-precipitation"],
        "best_synthesis": "Solution combustion with glucose fuel at 550°C",
        "electrolytes": ["Aqueous alkaline", "Acetate buffer"],
        "potential_window_V": {"aqueous": 1.0, "buffer": 0.8},
        "applications": ["Supercapacitors", "Biosensors", "Batteries", "Electrocatalysis"],
        "advantages": ["Good capacitance", "Low cost", "Dual redox couples", "Biocompatible"],
        "disadvantages": ["Moderate cycle life", "Requires alkaline electrolyte"],
        "biosensor_performance": {
            "analyte": "Uric Acid",
            "sensitivity_uA_uM_cm2": 0.044,
            "lod_M": 3.999e-05,
            "linear_range_M": [1e-05, 2.5e-04],
            "stability_cycles": 500,
        },
        "references": [
            "Shubha MB et al. (2026), To be published",
            "Zhang et al. (2015), J. Power Sources, 276, 39"
        ]
    },
    "Activated Carbon": {
        "capacitance_range_F_g": [150, 250],
        "typical_capacitance_F_g": 200,
        "energy_density_Wh_kg": 60,
        "power_density_W_kg": 100000,
        "cycle_life": 100000,
        "cost_per_kg_usd": 5,
        "synthesis_methods": ["Physical activation", "Chemical activation", "Biomass carbonization"],
        "best_synthesis": "KOH activation at 800°C",
        "electrolytes": ["Aqueous", "Organic", "Ionic liquid"],
        "potential_window_V": {"aqueous": 1.0, "organic": 2.7, "ionic_liquid": 3.5},
        "applications": ["Supercapacitors", "Water purification", "Gas storage"],
        "advantages": ["Very low cost", "Abundant", "High surface area", "Excellent cycle life"],
        "disadvantages": ["Moderate capacitance", "Pore size distribution issues"],
        "references": [
            "Pandolfo & Hollenkamp (2006), J. Power Sources, 157, 11",
            "Zhang & Zhao (2009), Chem. Soc. Rev., 38, 2520"
        ]
    },
}


def enhance_database():
    """Enhance the materials database with comprehensive properties."""
    
    # Load existing database
    db_path = Path("data/materials_database.json")
    with open(db_path, 'r') as f:
        db = json.load(f)
    
    materials = db['materials']
    
    # Enhance each material
    enhanced_count = 0
    for material in materials:
        name = material['name']
        
        # Find matching enhanced data
        enhanced_data = None
        for key, data in ENHANCED_MATERIALS.items():
            if key.lower() in name.lower() or name.lower() in key.lower():
                enhanced_data = data
                break
        
        if enhanced_data:
            # Add enhanced properties
            material['performance'] = {
                'capacitance_range_F_g': enhanced_data['capacitance_range_F_g'],
                'typical_capacitance_F_g': enhanced_data['typical_capacitance_F_g'],
                'energy_density_Wh_kg': enhanced_data['energy_density_Wh_kg'],
                'power_density_W_kg': enhanced_data['power_density_W_kg'],
                'cycle_life': enhanced_data['cycle_life'],
            }
            
            material['economics'] = {
                'cost_per_kg_usd': enhanced_data['cost_per_kg_usd'],
                'cost_category': (
                    'very_low' if enhanced_data['cost_per_kg_usd'] < 10 else
                    'low' if enhanced_data['cost_per_kg_usd'] < 50 else
                    'medium' if enhanced_data['cost_per_kg_usd'] < 200 else
                    'high' if enhanced_data['cost_per_kg_usd'] < 1000 else
                    'very_high'
                ),
            }
            
            material['synthesis'] = {
                'methods': enhanced_data['synthesis_methods'],
                'best_method': enhanced_data['best_synthesis'],
            }
            
            material['electrochemistry'] = {
                'electrolytes': enhanced_data['electrolytes'],
                'potential_windows_V': enhanced_data['potential_window_V'],
            }
            
            material['applications'] = enhanced_data['applications']
            material['advantages'] = enhanced_data['advantages']
            material['disadvantages'] = enhanced_data['disadvantages']
            material['literature_references'] = enhanced_data['references']
            
            # Add biosensor data if available
            if 'biosensor_performance' in enhanced_data:
                material['biosensor_performance'] = enhanced_data['biosensor_performance']
            
            enhanced_count += 1
            print(f"✅ Enhanced: {name}")
    
    # Update metadata
    db['version'] = "3.0"
    db['last_updated'] = "2026-05-13"
    db['enhancements'] = {
        'performance_metrics': True,
        'economic_data': True,
        'synthesis_methods': True,
        'literature_references': True,
        'application_domains': True,
    }
    
    # Save enhanced database
    with open(db_path, 'w') as f:
        json.dump(db, f, indent=2)
    
    print(f"\n✅ Enhanced {enhanced_count}/{len(materials)} materials")
    print(f"✅ Saved to {db_path}")
    
    return enhanced_count


def generate_materials_summary():
    """Generate a summary of all materials with their key properties."""
    
    db_path = Path("data/materials_database.json")
    with open(db_path, 'r') as f:
        db = json.load(f)
    
    materials = db['materials']
    
    # Sort by capacitance
    materials_sorted = sorted(
        materials,
        key=lambda m: m.get('performance', {}).get('typical_capacitance_F_g', 0),
        reverse=True
    )
    
    summary = []
    summary.append("# Materials Database Summary")
    summary.append(f"\n**Total Materials**: {len(materials)}")
    summary.append(f"**Database Version**: {db['version']}")
    summary.append(f"**Last Updated**: {db['last_updated']}")
    summary.append("\n---\n")
    
    summary.append("## Materials Ranked by Capacitance\n")
    summary.append("| Rank | Material | Capacitance (F/g) | Cost ($/kg) | Cycle Life | Applications |")
    summary.append("|------|----------|-------------------|-------------|------------|--------------|")
    
    for i, material in enumerate(materials_sorted, 1):
        name = material['name']
        perf = material.get('performance', {})
        econ = material.get('economics', {})
        apps = material.get('applications', [])
        
        cap = perf.get('typical_capacitance_F_g', 'N/A')
        cost = econ.get('cost_per_kg_usd', 'N/A')
        cycles = perf.get('cycle_life', 'N/A')
        apps_str = ', '.join(apps[:2]) if apps else 'N/A'
        
        summary.append(f"| {i} | {name} | {cap} | {cost} | {cycles} | {apps_str} |")
    
    summary.append("\n---\n")
    summary.append("## Cost Categories\n")
    
    cost_categories = {}
    for material in materials:
        cat = material.get('economics', {}).get('cost_category', 'unknown')
        if cat not in cost_categories:
            cost_categories[cat] = []
        cost_categories[cat].append(material['name'])
    
    for cat, mats in sorted(cost_categories.items()):
        summary.append(f"\n### {cat.replace('_', ' ').title()}")
        for mat in mats:
            summary.append(f"- {mat}")
    
    # Save summary
    summary_path = Path("MATERIALS_DATABASE_SUMMARY.md")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(summary))
    
    print(f"\n✅ Summary saved to {summary_path}")


if __name__ == "__main__":
    print("="*70)
    print("ENHANCING MATERIALS DATABASE")
    print("="*70)
    
    enhanced_count = enhance_database()
    generate_materials_summary()
    
    print("\n" + "="*70)
    print("ENHANCEMENT COMPLETE")
    print("="*70)
    print(f"\n✅ Enhanced {enhanced_count} materials with:")
    print("   - Performance metrics (capacitance, energy, power, cycle life)")
    print("   - Economic data (cost per kg, cost category)")
    print("   - Synthesis methods (multiple methods, best method)")
    print("   - Electrochemistry (electrolytes, potential windows)")
    print("   - Applications and use cases")
    print("   - Advantages and disadvantages")
    print("   - Literature references")
    print("\n✅ Database version: 3.0")
    print("✅ Summary generated: MATERIALS_DATABASE_SUMMARY.md")
