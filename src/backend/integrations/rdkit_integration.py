"""
RDKit Integration for RĀMAN Studio
===================================
Provides molecular descriptor calculation and fingerprint generation
for material identification and similarity search.

Safe fallback: Returns None if RDKit is not installed.
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import RDKit - fail gracefully if not available
try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, AllChem, Crippen, Lipinski
    from rdkit.Chem import rdMolDescriptors
    RDKIT_AVAILABLE = True
    logger.info("RDKit integration enabled")
except ImportError:
    RDKIT_AVAILABLE = False
    logger.warning("RDKit not installed - molecular descriptor features disabled")


@dataclass
class MolecularDescriptors:
    """Container for molecular descriptors calculated by RDKit."""
    smiles: str
    molecular_weight: float
    logp: float  # Octanol-water partition coefficient
    tpsa: float  # Topological polar surface area
    num_h_donors: int
    num_h_acceptors: int
    num_rotatable_bonds: int
    num_aromatic_rings: int
    num_aliphatic_rings: int
    fraction_csp3: float  # Fraction of sp3 carbons
    molar_refractivity: float
    
    # Electrochemistry-relevant descriptors
    num_heteroatoms: int
    num_heavy_atoms: int
    formal_charge: int
    
    # Fingerprint (for similarity search)
    morgan_fingerprint: Optional[List[int]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "smiles": self.smiles,
            "molecular_weight": round(self.molecular_weight, 2),
            "logp": round(self.logp, 2),
            "tpsa": round(self.tpsa, 2),
            "num_h_donors": self.num_h_donors,
            "num_h_acceptors": self.num_h_acceptors,
            "num_rotatable_bonds": self.num_rotatable_bonds,
            "num_aromatic_rings": self.num_aromatic_rings,
            "num_aliphatic_rings": self.num_aliphatic_rings,
            "fraction_csp3": round(self.fraction_csp3, 3),
            "molar_refractivity": round(self.molar_refractivity, 2),
            "num_heteroatoms": self.num_heteroatoms,
            "num_heavy_atoms": self.num_heavy_atoms,
            "formal_charge": self.formal_charge,
            "morgan_fingerprint": self.morgan_fingerprint,
        }


class RDKitIntegration:
    """
    RDKit integration for molecular descriptor calculation.
    
    Usage:
        rdkit = RDKitIntegration()
        if rdkit.is_available():
            descriptors = rdkit.calculate_descriptors("C1=CC=CC=C1")  # Benzene
            print(descriptors.molecular_weight)  # 78.11
    """
    
    def __init__(self):
        self.available = RDKIT_AVAILABLE
    
    def is_available(self) -> bool:
        """Check if RDKit is available."""
        return self.available
    
    def smiles_to_mol(self, smiles: str) -> Optional[Any]:
        """
        Convert SMILES string to RDKit molecule object.
        
        Args:
            smiles: SMILES string representation
            
        Returns:
            RDKit Mol object or None if invalid/unavailable
        """
        if not self.available:
            return None
        
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                logger.warning(f"Invalid SMILES string: {smiles}")
            return mol
        except Exception as e:
            logger.error(f"Error parsing SMILES {smiles}: {e}")
            return None
    
    def calculate_descriptors(self, smiles: str) -> Optional[MolecularDescriptors]:
        """
        Calculate comprehensive molecular descriptors from SMILES.
        
        Args:
            smiles: SMILES string representation
            
        Returns:
            MolecularDescriptors object or None if calculation fails
        """
        if not self.available:
            logger.warning("RDKit not available - cannot calculate descriptors")
            return None
        
        mol = self.smiles_to_mol(smiles)
        if mol is None:
            return None
        
        try:
            # Calculate Morgan fingerprint (radius=2, 2048 bits)
            fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)
            fp_list = list(fp.ToBitString())
            fp_indices = [i for i, bit in enumerate(fp_list) if bit == '1']
            
            descriptors = MolecularDescriptors(
                smiles=smiles,
                molecular_weight=Descriptors.MolWt(mol),
                logp=Crippen.MolLogP(mol),
                tpsa=Descriptors.TPSA(mol),
                num_h_donors=Lipinski.NumHDonors(mol),
                num_h_acceptors=Lipinski.NumHAcceptors(mol),
                num_rotatable_bonds=Lipinski.NumRotatableBonds(mol),
                num_aromatic_rings=Lipinski.NumAromaticRings(mol),
                num_aliphatic_rings=Lipinski.NumAliphaticRings(mol),
                fraction_csp3=Lipinski.FractionCsp3(mol),
                molar_refractivity=Crippen.MolMR(mol),
                num_heteroatoms=Lipinski.NumHeteroatoms(mol),
                num_heavy_atoms=Lipinski.HeavyAtomCount(mol),
                formal_charge=Chem.GetFormalCharge(mol),
                morgan_fingerprint=fp_indices[:100],  # Store first 100 set bits
            )
            
            return descriptors
            
        except Exception as e:
            logger.error(f"Error calculating descriptors for {smiles}: {e}")
            return None
    
    def calculate_similarity(self, smiles1: str, smiles2: str) -> Optional[float]:
        """
        Calculate Tanimoto similarity between two molecules.
        
        Args:
            smiles1: First SMILES string
            smiles2: Second SMILES string
            
        Returns:
            Similarity score (0-1) or None if calculation fails
        """
        if not self.available:
            return None
        
        mol1 = self.smiles_to_mol(smiles1)
        mol2 = self.smiles_to_mol(smiles2)
        
        if mol1 is None or mol2 is None:
            return None
        
        try:
            fp1 = AllChem.GetMorganFingerprintAsBitVect(mol1, radius=2, nBits=2048)
            fp2 = AllChem.GetMorganFingerprintAsBitVect(mol2, radius=2, nBits=2048)
            
            from rdkit import DataStructs
            similarity = DataStructs.TanimotoSimilarity(fp1, fp2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return None
    
    def find_most_similar(
        self, 
        query_smiles: str, 
        candidate_smiles: List[str]
    ) -> Optional[List[tuple]]:
        """
        Find most similar molecules from a list of candidates.
        
        Args:
            query_smiles: Query molecule SMILES
            candidate_smiles: List of candidate SMILES strings
            
        Returns:
            List of (smiles, similarity_score) tuples, sorted by similarity (descending)
        """
        if not self.available:
            return None
        
        results = []
        for candidate in candidate_smiles:
            similarity = self.calculate_similarity(query_smiles, candidate)
            if similarity is not None:
                results.append((candidate, similarity))
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    def validate_smiles(self, smiles: str) -> bool:
        """
        Validate if a SMILES string is chemically valid.
        
        Args:
            smiles: SMILES string to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not self.available:
            return False
        
        mol = self.smiles_to_mol(smiles)
        return mol is not None


# Global singleton instance
_rdkit_instance = None

def get_rdkit_integration() -> RDKitIntegration:
    """Get the global RDKit integration instance."""
    global _rdkit_instance
    if _rdkit_instance is None:
        _rdkit_instance = RDKitIntegration()
    return _rdkit_instance
