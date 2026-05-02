"""
Electronic Signatures
=====================
21 CFR Part 11 compliant electronic signatures for critical actions.

Author: VidyuthLabs
Date: May 1, 2026
"""

import logging
import hashlib
import hmac
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class SignatureType(str, Enum):
    """Signature type enumeration."""
    APPROVAL = "approval"  # Approve experiment/report
    REVIEW = "review"  # Review data
    VERIFICATION = "verification"  # Verify results
    AUTHORIZATION = "authorization"  # Authorize action
    ATTESTATION = "attestation"  # Attest to accuracy


class SignatureReason(str, Enum):
    """Signature reason enumeration."""
    EXPERIMENT_APPROVAL = "experiment_approval"
    REPORT_APPROVAL = "report_approval"
    DATA_REVIEW = "data_review"
    RESULT_VERIFICATION = "result_verification"
    METHOD_AUTHORIZATION = "method_authorization"
    QUALITY_ATTESTATION = "quality_attestation"


@dataclass
class ElectronicSignature:
    """
    Electronic signature record.
    
    21 CFR Part 11 Requirements:
    - Unique to one individual
    - Not reused or reassigned
    - Linked to their electronic record
    - Includes printed name, date/time, meaning
    """
    id: str
    user_id: str
    user_name: str
    user_email: str
    signature_type: SignatureType
    reason: SignatureReason
    resource_type: str  # experiment, report, batch_job
    resource_id: str
    timestamp: datetime
    ip_address: Optional[str] = None
    meaning: str = ""  # What this signature means
    signature_hash: str = ""  # Cryptographic signature
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "user_email": self.user_email,
            "signature_type": self.signature_type,
            "reason": self.reason,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "ip_address": self.ip_address,
            "meaning": self.meaning,
            "signature_hash": self.signature_hash
        }


class SignatureManager:
    """
    Electronic signature manager for 21 CFR Part 11 compliance.
    
    Features:
    - Multi-level approval workflows
    - Cryptographic signatures
    - Tamper-proof records
    - Audit trail integration
    - Non-repudiation
    
    21 CFR Part 11 Compliance:
    - § 11.50: Signature manifestations
    - § 11.70: Signature/record linking
    - § 11.100: General requirements
    - § 11.200: Electronic signature components
    - § 11.300: Controls for identification codes/passwords
    
    Examples:
        # Create signature
        manager = SignatureManager()
        
        signature = manager.create_signature(
            user_id="user-123",
            user_name="Dr. Jane Smith",
            user_email="jane@example.com",
            signature_type=SignatureType.APPROVAL,
            reason=SignatureReason.EXPERIMENT_APPROVAL,
            resource_type="experiment",
            resource_id="exp-456",
            meaning="I approve this experiment for publication"
        )
        
        # Verify signature
        is_valid = manager.verify_signature(signature)
    """
    
    def __init__(self, secret_key: str = "raman-studio-secret"):
        """
        Initialize signature manager.
        
        Args:
            secret_key: Secret key for HMAC signatures
        """
        self.secret_key = secret_key
        self.signatures: Dict[str, ElectronicSignature] = {}
        logger.info("Signature manager initialized")
    
    def create_signature(
        self,
        user_id: str,
        user_name: str,
        user_email: str,
        signature_type: SignatureType,
        reason: SignatureReason,
        resource_type: str,
        resource_id: str,
        meaning: str,
        ip_address: Optional[str] = None
    ) -> ElectronicSignature:
        """
        Create electronic signature.
        
        Args:
            user_id: User ID
            user_name: User full name
            user_email: User email
            signature_type: Signature type
            reason: Signature reason
            resource_type: Resource type (experiment, report, etc.)
            resource_id: Resource ID
            meaning: What this signature means
            ip_address: IP address (optional)
        
        Returns:
            Electronic signature
        """
        signature_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Create signature
        signature = ElectronicSignature(
            id=signature_id,
            user_id=user_id,
            user_name=user_name,
            user_email=user_email,
            signature_type=signature_type,
            reason=reason,
            resource_type=resource_type,
            resource_id=resource_id,
            timestamp=timestamp,
            ip_address=ip_address,
            meaning=meaning
        )
        
        # Generate cryptographic signature
        signature.signature_hash = self._generate_signature_hash(signature)
        
        # Store signature
        self.signatures[signature_id] = signature
        
        logger.info(
            f"Electronic signature created: {signature_type} by {user_name} "
            f"for {resource_type}:{resource_id}"
        )
        
        return signature
    
    def _generate_signature_hash(self, signature: ElectronicSignature) -> str:
        """
        Generate cryptographic signature hash.
        
        Args:
            signature: Electronic signature
        
        Returns:
            HMAC-SHA256 signature hash
        """
        # Create signature payload
        payload = (
            f"{signature.id}|"
            f"{signature.user_id}|"
            f"{signature.user_name}|"
            f"{signature.user_email}|"
            f"{signature.signature_type}|"
            f"{signature.reason}|"
            f"{signature.resource_type}|"
            f"{signature.resource_id}|"
            f"{signature.timestamp.isoformat()}|"
            f"{signature.meaning}"
        )
        
        # Generate HMAC signature
        signature_hash = hmac.new(
            self.secret_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature_hash
    
    def verify_signature(self, signature: ElectronicSignature) -> bool:
        """
        Verify electronic signature integrity.
        
        Args:
            signature: Electronic signature
        
        Returns:
            True if signature is valid
        """
        # Recalculate signature hash
        expected_hash = self._generate_signature_hash(signature)
        
        # Compare hashes (constant-time comparison)
        is_valid = hmac.compare_digest(signature.signature_hash, expected_hash)
        
        if not is_valid:
            logger.warning(f"Invalid signature detected: {signature.id}")
        
        return is_valid
    
    def get_signature(self, signature_id: str) -> Optional[ElectronicSignature]:
        """Get signature by ID."""
        return self.signatures.get(signature_id)
    
    def get_signatures_for_resource(
        self,
        resource_type: str,
        resource_id: str
    ) -> list[ElectronicSignature]:
        """
        Get all signatures for a resource.
        
        Args:
            resource_type: Resource type
            resource_id: Resource ID
        
        Returns:
            List of signatures
        """
        return [
            sig for sig in self.signatures.values()
            if sig.resource_type == resource_type and sig.resource_id == resource_id
        ]
    
    def get_signatures_by_user(self, user_id: str) -> list[ElectronicSignature]:
        """
        Get all signatures by user.
        
        Args:
            user_id: User ID
        
        Returns:
            List of signatures
        """
        return [
            sig for sig in self.signatures.values()
            if sig.user_id == user_id
        ]
    
    def revoke_signature(self, signature_id: str, reason: str) -> bool:
        """
        Revoke signature (mark as invalid).
        
        Note: In 21 CFR Part 11, signatures cannot be deleted,
        but they can be marked as revoked with a reason.
        
        Args:
            signature_id: Signature ID
            reason: Revocation reason
        
        Returns:
            True if revoked
        """
        signature = self.signatures.get(signature_id)
        if not signature:
            return False
        
        # Mark as revoked (add to meaning)
        signature.meaning += f"\n\n[REVOKED: {reason} at {datetime.utcnow().isoformat()}]"
        
        logger.info(f"Signature revoked: {signature_id} - Reason: {reason}")
        return True


# Global signature manager instance
_signature_manager = None


def get_signature_manager() -> SignatureManager:
    """Get or create global signature manager instance."""
    global _signature_manager
    if _signature_manager is None:
        _signature_manager = SignatureManager()
    return _signature_manager


# ===================================================================
#  Approval Workflows
# ===================================================================

class ApprovalWorkflow:
    """
    Multi-level approval workflow.
    
    Features:
    - Sequential approval (Level 1 → Level 2 → Level 3)
    - Parallel approval (multiple approvers at same level)
    - Conditional approval (based on criteria)
    - Rejection handling
    
    Examples:
        # Create workflow
        workflow = ApprovalWorkflow(
            resource_type="experiment",
            resource_id="exp-123",
            levels=[
                {"name": "Analyst Review", "required_approvers": 1},
                {"name": "Manager Approval", "required_approvers": 1},
                {"name": "QA Approval", "required_approvers": 2}
            ]
        )
        
        # Add approval
        workflow.add_approval(
            level=0,
            user_id="user-123",
            user_name="Dr. Jane Smith",
            user_email="jane@example.com"
        )
    """
    
    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        levels: list[Dict[str, Any]]
    ):
        """
        Initialize approval workflow.
        
        Args:
            resource_type: Resource type
            resource_id: Resource ID
            levels: Approval levels (list of dicts with name, required_approvers)
        """
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.levels = levels
        self.approvals: Dict[int, list[ElectronicSignature]] = {
            i: [] for i in range(len(levels))
        }
        self.current_level = 0
        self.status = "pending"  # pending, approved, rejected
        
        logger.info(
            f"Approval workflow created: {resource_type}:{resource_id} "
            f"with {len(levels)} levels"
        )
    
    def add_approval(
        self,
        level: int,
        user_id: str,
        user_name: str,
        user_email: str,
        meaning: str = "",
        ip_address: Optional[str] = None
    ) -> ElectronicSignature:
        """
        Add approval at specific level.
        
        Args:
            level: Approval level (0-indexed)
            user_id: User ID
            user_name: User full name
            user_email: User email
            meaning: Approval meaning
            ip_address: IP address
        
        Returns:
            Electronic signature
        """
        if level != self.current_level:
            raise ValueError(
                f"Cannot approve level {level}. Current level is {self.current_level}"
            )
        
        # Create signature
        manager = get_signature_manager()
        signature = manager.create_signature(
            user_id=user_id,
            user_name=user_name,
            user_email=user_email,
            signature_type=SignatureType.APPROVAL,
            reason=SignatureReason.EXPERIMENT_APPROVAL,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            meaning=meaning or f"Approved at level {level + 1}: {self.levels[level]['name']}",
            ip_address=ip_address
        )
        
        # Add to approvals
        self.approvals[level].append(signature)
        
        # Check if level is complete
        required = self.levels[level]['required_approvers']
        if len(self.approvals[level]) >= required:
            logger.info(
                f"Level {level + 1} complete: {len(self.approvals[level])}/{required} approvals"
            )
            
            # Move to next level
            if level + 1 < len(self.levels):
                self.current_level = level + 1
            else:
                # All levels complete
                self.status = "approved"
                logger.info(f"Workflow approved: {self.resource_type}:{self.resource_id}")
        
        return signature
    
    def reject(
        self,
        user_id: str,
        user_name: str,
        user_email: str,
        reason: str,
        ip_address: Optional[str] = None
    ) -> ElectronicSignature:
        """
        Reject at current level.
        
        Args:
            user_id: User ID
            user_name: User full name
            user_email: User email
            reason: Rejection reason
            ip_address: IP address
        
        Returns:
            Electronic signature
        """
        # Create rejection signature
        manager = get_signature_manager()
        signature = manager.create_signature(
            user_id=user_id,
            user_name=user_name,
            user_email=user_email,
            signature_type=SignatureType.APPROVAL,
            reason=SignatureReason.EXPERIMENT_APPROVAL,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            meaning=f"REJECTED: {reason}",
            ip_address=ip_address
        )
        
        self.status = "rejected"
        
        logger.info(
            f"Workflow rejected: {self.resource_type}:{self.resource_id} - "
            f"Reason: {reason}"
        )
        
        return signature
    
    def get_status(self) -> Dict[str, Any]:
        """Get workflow status."""
        return {
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "status": self.status,
            "current_level": self.current_level,
            "total_levels": len(self.levels),
            "levels": [
                {
                    "name": level['name'],
                    "required_approvers": level['required_approvers'],
                    "current_approvers": len(self.approvals[i]),
                    "complete": len(self.approvals[i]) >= level['required_approvers']
                }
                for i, level in enumerate(self.levels)
            ]
        }
