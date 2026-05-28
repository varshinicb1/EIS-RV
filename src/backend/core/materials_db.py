import requests
import logging
from src.backend.core.config import HTTP_TIMEOUT_S, PUBCHEM_BASE

logger = logging.getLogger(__name__)

class MaterialsDatabase:
    """Universal material properties fetcher using PubChem REST API."""
    
    BASE_URL = PUBCHEM_BASE

    @staticmethod
    def get_compound_data(name: str) -> dict:
        """Fetches advanced properties for any given material/molecule name."""
        try:
            # First, fetch CID by name
            logger.info(f"Fetching CID for {name}")
            cid_resp = requests.get(f"{MaterialsDatabase.BASE_URL}/compound/name/{name}/cids/JSON", timeout=HTTP_TIMEOUT_S)
            if cid_resp.status_code != 200:
                logger.error(f"Failed to find {name} in PubChem.")
                return {"error": "Compound not found"}
            
            cid = cid_resp.json()['IdentifierList']['CID'][0]
            
            # Now fetch advanced properties
            logger.info(f"Fetching properties for CID {cid}")
            props = "MolecularWeight,MolecularFormula,XLogP,ExactMass,TPSA,Complexity,Charge"
            prop_resp = requests.get(f"{MaterialsDatabase.BASE_URL}/compound/cid/{cid}/property/{props}/JSON", timeout=HTTP_TIMEOUT_S)
            
            if prop_resp.status_code != 200:
                return {"error": "Failed to fetch properties"}
                
            data = prop_resp.json()['PropertyTable']['Properties'][0]
            
            # Fetch 3D SDF / conformer if available (we will use this for rendering or simulation)
            return {
                "cid": cid,
                "name": name.upper(),
                "formula": data.get("MolecularFormula", ""),
                "molecular_weight": float(data.get("MolecularWeight", 0)),
                "exact_mass": float(data.get("ExactMass", 0)),
                "xlogp": float(data.get("XLogP", 0)),
                "tpsa": float(data.get("TPSA", 0)),
                "complexity": float(data.get("Complexity", 0)),
                "charge": int(data.get("Charge", 0))
            }
        except Exception as e:
            logger.error(f"Database fetch error: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    def get_sdf(cid: int) -> str:
        """Fetches the 3D SDF geometry file for the compound."""
        try:
            resp = requests.get(f"{MaterialsDatabase.BASE_URL}/compound/cid/{cid}/SDF?record_type=3d", timeout=HTTP_TIMEOUT_S)
            if resp.status_code == 200:
                return resp.text
            # Fallback to 2D if 3D is not available
            resp = requests.get(f"{MaterialsDatabase.BASE_URL}/compound/cid/{cid}/SDF?record_type=2d", timeout=HTTP_TIMEOUT_S)
            return resp.text if resp.status_code == 200 else ""
        except Exception:
            return ""
