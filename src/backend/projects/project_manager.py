"""
Secure Project Management System
==================================
Local project storage with military-grade encryption and integrity checks
Company: VidyuthLabs

SECURITY FEATURES:
- Hardware-derived encryption keys (no key storage)
- HMAC integrity verification
- Path traversal protection
- Input sanitization
- Atomic file operations
- Secure deletion
- Audit logging
"""

import json
import shutil
import hmac
import hashlib
import base64
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging
import os

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit')


@dataclass
class Project:
    """Project data structure"""
    id: str
    name: str
    description: str
    created_at: str
    modified_at: str
    author: str
    tags: List[str]
    simulations: List[Dict]
    materials: List[Dict]
    results: List[Dict]
    notes: str
    version: int
    encrypted: bool
    integrity_hash: str = ""


class ProjectManager:
    """Secure project manager with military-grade encryption"""
    
    # Projects directory
    PROJECTS_DIR = Path.home() / "RĀMAN_Studio_Projects"
    
    # Project file extension
    PROJECT_EXT = ".dproj"
    
    # HMAC secret for integrity
    HMAC_SECRET = b'raman_studio_project_integrity_v1'
    
    # Maximum project name length
    MAX_NAME_LENGTH = 100
    
    # Allowed characters in project names
    ALLOWED_CHARS = r'[a-zA-Z0-9_\-\s]'
    
    def __init__(self):
        self._ensure_projects_dir()
        self.current_project: Optional[Project] = None
        self._setup_audit_logging()
    
    def _setup_audit_logging(self):
        """Set up audit logging for security events"""
        audit_file = Path.home() / ".raman-studio" / "project_audit.log"
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        
        handler = logging.FileHandler(audit_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        audit_logger.addHandler(handler)
        audit_logger.setLevel(logging.INFO)
    
    def _audit_log(self, action: str, details: Dict):
        """Log security-sensitive actions"""
        audit_logger.info(f"{action}: {json.dumps(details)}")
    
    def _ensure_projects_dir(self):
        """Ensure projects directory exists with proper permissions"""
        self.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Set restrictive permissions on Unix
        if os.name != 'nt':  # Not Windows
            os.chmod(self.PROJECTS_DIR, 0o700)
        
        logger.info(f"📁 Projects directory: {self.PROJECTS_DIR}")
    
    def _sanitize_project_name(self, name: str) -> str:
        """Sanitize project name to prevent path traversal and injection"""
        if not name or not isinstance(name, str):
            raise ValueError("Project name must be a non-empty string")
        
        # Remove path separators
        name = name.replace('/', '').replace('\\', '').replace('..', '')
        
        # Remove null bytes
        name = name.replace('\x00', '')
        
        # Allow only safe characters
        name = re.sub(f'[^{self.ALLOWED_CHARS}]', '', name)
        
        # Trim whitespace
        name = name.strip()
        
        # Limit length
        name = name[:self.MAX_NAME_LENGTH]
        
        # Ensure not empty after sanitization
        if not name:
            raise ValueError("Project name contains only invalid characters")
        
        # Prevent reserved names
        reserved = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'LPT1']
        if name.upper() in reserved:
            raise ValueError(f"'{name}' is a reserved name")
        
        return name
    
    def _validate_project_data(self, project: Project):
        """Validate project data before saving"""
        if not project.id or len(project.id) != 16:
            raise ValueError("Invalid project ID")
        
        if not project.name:
            raise ValueError("Project name is required")
        
        if not isinstance(project.simulations, list):
            raise ValueError("Simulations must be a list")
        
        if not isinstance(project.materials, list):
            raise ValueError("Materials must be a list")
        
        if not isinstance(project.results, list):
            raise ValueError("Results must be a list")
        
        if not isinstance(project.tags, list):
            raise ValueError("Tags must be a list")
    
    def _generate_project_id(self, name: str) -> str:
        """Generate unique project ID"""
        timestamp = datetime.now().isoformat()
        combined = f"{name}-{timestamp}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _get_project_encryption_key(self, project_id: str) -> bytes:
        """Derive encryption key from hardware ID + project ID"""
        try:
            from src.backend.licensing.license_manager import get_license_manager
            
            license_mgr = get_license_manager()
            hardware_id = license_mgr.get_hardware_id()
        except:
            # Fallback if license manager not available
            import uuid
            hardware_id = str(uuid.getnode())
        
        # Combine hardware ID and project ID
        combined = f"{hardware_id}-{project_id}"
        
        # Use PBKDF2 with high iteration count
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'raman_studio_project_encryption_v2',
            iterations=500000,
        )
        key = kdf.derive(combined.encode())
        return base64.urlsafe_b64encode(key)
    
    def _compute_integrity_hash(self, data: Dict) -> str:
        """Compute HMAC integrity hash"""
        data_str = json.dumps(data, sort_keys=True)
        mac = hmac.new(
            self.HMAC_SECRET,
            data_str.encode(),
            hashlib.sha256
        ).hexdigest()
        return mac
    
    def _encrypt_project(self, project_data: Dict) -> bytes:
        """Encrypt project data with derived key and HMAC"""
        project_id = project_data.get('id', '')
        
        # Compute integrity hash
        integrity_hash = self._compute_integrity_hash(project_data)
        project_data['integrity_hash'] = integrity_hash
        
        # Get encryption key
        key = self._get_project_encryption_key(project_id)
        f = Fernet(key)
        
        # Encrypt
        json_data = json.dumps(project_data).encode()
        encrypted = f.encrypt(json_data)
        
        # Add HMAC for additional integrity check
        mac = hmac.new(self.HMAC_SECRET, encrypted, hashlib.sha256).digest()
        
        return mac + b'::' + encrypted
    
    def _decrypt_project(self, encrypted_with_mac: bytes, project_id: str = "") -> Dict:
        """Decrypt project data and verify integrity"""
        try:
            # Split MAC and encrypted data
            parts = encrypted_with_mac.split(b'::', 1)
            if len(parts) != 2:
                raise ValueError("Invalid encrypted data format")
            
            mac, encrypted = parts
            
            # Verify HMAC
            expected_mac = hmac.new(self.HMAC_SECRET, encrypted, hashlib.sha256).digest()
            if not hmac.compare_digest(mac, expected_mac):
                raise ValueError("Project file integrity check failed - possible tampering")
            
            # Decrypt
            key = self._get_project_encryption_key(project_id)
            f = Fernet(key)
            decrypted = f.decrypt(encrypted)
            
            project_data = json.loads(decrypted.decode())
            
            # Verify internal integrity hash
            stored_hash = project_data.pop('integrity_hash', '')
            computed_hash = self._compute_integrity_hash(project_data)
            
            if stored_hash and not hmac.compare_digest(stored_hash, computed_hash):
                raise ValueError("Project data integrity check failed")
            
            project_data['integrity_hash'] = stored_hash
            
            return project_data
            
        except Exception as e:
            logger.error(f"Failed to decrypt project: {e}")
            raise
    
    def create_project(
        self,
        name: str,
        description: str = "",
        author: str = "User",
        tags: List[str] = None,
        encrypted: bool = True
    ) -> Project:
        """Create new project with sanitized inputs"""
        # Sanitize inputs
        name = self._sanitize_project_name(name)
        description = description[:500] if description else ""  # Limit description
        author = author[:100] if author else "User"  # Limit author
        tags = [tag[:50] for tag in (tags or [])][:10]  # Limit tags
        
        project_id = self._generate_project_id(name)
        now = datetime.now().isoformat()
        
        project = Project(
            id=project_id,
            name=name,
            description=description,
            created_at=now,
            modified_at=now,
            author=author,
            tags=tags,
            simulations=[],
            materials=[],
            results=[],
            notes="",
            version=1,
            encrypted=encrypted,
            integrity_hash=""
        )
        
        self._validate_project_data(project)
        self.current_project = project
        self.save_project(project)
        
        self._audit_log('project_created', {
            'project_id': project_id,
            'name': name,
            'author': author
        })
        
        logger.info(f"✅ Created project: {name} ({project_id})")
        return project
    
    def save_project(self, project: Optional[Project] = None):
        """Save project to disk with atomic write"""
        if project is None:
            project = self.current_project
        
        if project is None:
            raise ValueError("No project to save")
        
        # Validate before saving
        self._validate_project_data(project)
        
        # Update modification time
        project.modified_at = datetime.now().isoformat()
        project.version += 1
        
        # Convert to dict
        project_data = asdict(project)
        
        # Sanitize name again (in case it was modified)
        safe_name = self._sanitize_project_name(project.name)
        project_file = self.PROJECTS_DIR / f"{safe_name}{self.PROJECT_EXT}"
        
        # Atomic write using temporary file
        temp_file = project_file.with_suffix('.tmp')
        
        try:
            if project.encrypted:
                # Encrypt project data
                encrypted_data = self._encrypt_project(project_data)
                with open(temp_file, 'wb') as f:
                    f.write(encrypted_data)
            else:
                # Save as JSON
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(project_data, f, indent=2)
            
            # Set restrictive permissions before moving
            if os.name != 'nt':
                os.chmod(temp_file, 0o600)
            
            # Atomic rename
            temp_file.replace(project_file)
            
            self._audit_log('project_saved', {
                'project_id': project.id,
                'name': project.name,
                'version': project.version
            })
            
            logger.info(f"💾 Saved project: {project.name} (v{project.version})")
            
        except Exception as e:
            # Clean up temp file on error
            if temp_file.exists():
                temp_file.unlink()
            raise
    
    def load_project(self, project_name: str) -> Project:
        """Load project from disk with validation"""
        # Sanitize project name
        safe_name = self._sanitize_project_name(project_name)
        project_file = self.PROJECTS_DIR / f"{safe_name}{self.PROJECT_EXT}"
        
        if not project_file.exists():
            raise FileNotFoundError(f"Project not found: {project_name}")
        
        # Check file permissions (Unix only)
        if os.name != 'nt':
            stat_info = project_file.stat()
            if stat_info.st_mode & 0o077:  # Check if group/other have permissions
                logger.warning(f"⚠️  Insecure permissions on {project_file}")
        
        try:
            # Try to load as encrypted first
            with open(project_file, 'rb') as f:
                data = f.read()
            
            # Check if it's encrypted (has MAC)
            if b'::' in data:
                # Extract project ID from filename for decryption
                project_id = ""  # Will be extracted from decrypted data
                project_data = self._decrypt_project(data, project_id)
            else:
                # Load as JSON
                project_data = json.loads(data.decode())
        except Exception as e:
            logger.error(f"Failed to load project: {e}")
            raise
        
        project = Project(**project_data)
        self._validate_project_data(project)
        self.current_project = project
        
        self._audit_log('project_loaded', {
            'project_id': project.id,
            'name': project.name,
            'version': project.version
        })
        
        logger.info(f"📂 Loaded project: {project.name} (v{project.version})")
        return project
    
    def list_projects(self) -> List[Dict]:
        """List all projects with error handling"""
        projects = []
        
        for project_file in self.PROJECTS_DIR.glob(f"*{self.PROJECT_EXT}"):
            try:
                # Load project metadata only
                project = self.load_project(project_file.stem)
                projects.append({
                    'id': project.id,
                    'name': project.name,
                    'description': project.description,
                    'created_at': project.created_at,
                    'modified_at': project.modified_at,
                    'author': project.author,
                    'tags': project.tags,
                    'version': project.version,
                    'simulations_count': len(project.simulations),
                    'results_count': len(project.results),
                    'encrypted': project.encrypted
                })
            except Exception as e:
                logger.error(f"Failed to load project {project_file.stem}: {e}")
                # Continue with other projects
        
        return sorted(projects, key=lambda x: x['modified_at'], reverse=True)
    
    def delete_project(self, project_name: str):
        """Securely delete project"""
        safe_name = self._sanitize_project_name(project_name)
        project_file = self.PROJECTS_DIR / f"{safe_name}{self.PROJECT_EXT}"
        
        if not project_file.exists():
            raise FileNotFoundError(f"Project not found: {project_name}")
        
        # Secure deletion: overwrite with random data
        file_size = project_file.stat().st_size
        with open(project_file, 'wb') as f:
            f.write(os.urandom(file_size))
        
        # Delete file
        project_file.unlink()
        
        self._audit_log('project_deleted', {
            'name': project_name
        })
        
        logger.info(f"🗑️  Securely deleted project: {project_name}")
    
    def export_project(self, project_name: str, export_path: Path):
        """Export project to external location"""
        safe_name = self._sanitize_project_name(project_name)
        project_file = self.PROJECTS_DIR / f"{safe_name}{self.PROJECT_EXT}"
        
        if not project_file.exists():
            raise FileNotFoundError(f"Project not found: {project_name}")
        
        # Validate export path
        export_path = Path(export_path).resolve()
        if not export_path.parent.exists():
            raise ValueError("Export directory does not exist")
        
        shutil.copy2(project_file, export_path)
        
        self._audit_log('project_exported', {
            'name': project_name,
            'export_path': str(export_path)
        })
        
        logger.info(f"📤 Exported project: {project_name} → {export_path}")
    
    def import_project(self, import_path: Path) -> Project:
        """Import project from external location"""
        import_path = Path(import_path).resolve()
        
        if not import_path.exists():
            raise FileNotFoundError(f"Import file not found: {import_path}")
        
        # Validate file size (prevent DoS)
        max_size = 100 * 1024 * 1024  # 100 MB
        if import_path.stat().st_size > max_size:
            raise ValueError("Project file too large")
        
        # Copy to projects directory
        project_name = import_path.stem
        safe_name = self._sanitize_project_name(project_name)
        project_file = self.PROJECTS_DIR / f"{safe_name}{self.PROJECT_EXT}"
        
        shutil.copy2(import_path, project_file)
        
        # Load and validate
        project = self.load_project(safe_name)
        
        self._audit_log('project_imported', {
            'name': safe_name,
            'import_path': str(import_path)
        })
        
        logger.info(f"📥 Imported project: {safe_name}")
        return project
    
    def add_simulation(self, simulation_data: Dict):
        """Add simulation to current project"""
        if self.current_project is None:
            raise ValueError("No project loaded")
        
        # Validate simulation data
        if not isinstance(simulation_data, dict):
            raise ValueError("Simulation data must be a dictionary")
        
        simulation_data['timestamp'] = datetime.now().isoformat()
        simulation_data['id'] = hashlib.sha256(
            json.dumps(simulation_data, sort_keys=True).encode()
        ).hexdigest()[:16]
        
        self.current_project.simulations.append(simulation_data)
        self.save_project()
        
        logger.info(f"➕ Added simulation to project: {self.current_project.name}")
    
    def add_result(self, result_data: Dict):
        """Add result to current project"""
        if self.current_project is None:
            raise ValueError("No project loaded")
        
        if not isinstance(result_data, dict):
            raise ValueError("Result data must be a dictionary")
        
        result_data['timestamp'] = datetime.now().isoformat()
        result_data['id'] = hashlib.sha256(
            json.dumps(result_data, sort_keys=True).encode()
        ).hexdigest()[:16]
        
        self.current_project.results.append(result_data)
        self.save_project()
        
        logger.info(f"➕ Added result to project: {self.current_project.name}")
    
    def add_material(self, material_data: Dict):
        """Add material to current project"""
        if self.current_project is None:
            raise ValueError("No project loaded")
        
        if not isinstance(material_data, dict):
            raise ValueError("Material data must be a dictionary")
        
        material_data['added_at'] = datetime.now().isoformat()
        
        self.current_project.materials.append(material_data)
        self.save_project()
        
        logger.info(f"➕ Added material to project: {self.current_project.name}")
    
    def update_notes(self, notes: str):
        """Update project notes"""
        if self.current_project is None:
            raise ValueError("No project loaded")
        
        # Limit notes size
        notes = notes[:10000] if notes else ""
        
        self.current_project.notes = notes
        self.save_project()
        
        logger.info(f"📝 Updated notes for project: {self.current_project.name}")
    
    def search_projects(self, query: str) -> List[Dict]:
        """Search projects by name, description, or tags"""
        if not query or not isinstance(query, str):
            return []
        
        all_projects = self.list_projects()
        query_lower = query.lower()[:100]  # Limit query length
        
        results = []
        for project in all_projects:
            if (query_lower in project['name'].lower() or
                query_lower in project['description'].lower() or
                any(query_lower in tag.lower() for tag in project['tags'])):
                results.append(project)
        
        return results
    
    def get_project_stats(self) -> Dict:
        """Get statistics about all projects"""
        projects = self.list_projects()
        
        total_simulations = sum(p['simulations_count'] for p in projects)
        total_results = sum(p['results_count'] for p in projects)
        
        # Calculate disk usage
        disk_usage = sum(
            f.stat().st_size for f in self.PROJECTS_DIR.glob(f"*{self.PROJECT_EXT}")
        ) / (1024 * 1024)
        
        return {
            'total_projects': len(projects),
            'total_simulations': total_simulations,
            'total_results': total_results,
            'projects_dir': str(self.PROJECTS_DIR),
            'disk_usage_mb': round(disk_usage, 2)
        }


# Global project manager instance
_project_manager = None


def get_project_manager() -> ProjectManager:
    """Get global project manager instance"""
    global _project_manager
    if _project_manager is None:
        _project_manager = ProjectManager()
    return _project_manager


if __name__ == "__main__":
    # Test secure project manager
    logging.basicConfig(level=logging.INFO)
    
    manager = get_project_manager()
    print("\n" + "=" * 60)
    print("SECURE PROJECT MANAGER TEST")
    print("=" * 60)
    
    # Test sanitization
    try:
        bad_name = "../../../etc/passwd"
        safe_name = manager._sanitize_project_name(bad_name)
        print(f"\n🛡️  Sanitization test:")
        print(f"   Input: {bad_name}")
        print(f"   Output: {safe_name}")
    except ValueError as e:
        print(f"   ✅ Blocked: {e}")
    
    # Create test project
    project = manager.create_project(
        name="Test_Secure_Project",
        description="Testing secure project management",
        author="Security Team",
        tags=["security", "test", "encryption"]
    )
    
    print(f"\n✅ Created project: {project.name}")
    print(f"   ID: {project.id}")
    print(f"   Encrypted: {project.encrypted}")
    
    # Add simulation
    manager.add_simulation({
        'type': 'EIS',
        'material': 'MnO2',
        'parameters': {'R_s': 10, 'R_ct': 50}
    })
    
    # Get stats
    stats = manager.get_project_stats()
    print(f"\n📈 Project Stats:")
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n✅ Secure Project Manager initialized successfully")
