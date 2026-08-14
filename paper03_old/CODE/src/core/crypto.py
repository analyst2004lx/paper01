"""
Simplified cryptographic operations for CTG-LC
(In production, use proper Ed25519 signatures)
"""
import hashlib
import hmac

class SimpleCrypto:
    """Simplified signature scheme using HMAC-SHA256"""
    
    def __init__(self, node_id: str, secret_key: str = "shared_secret"):
        """
        Args:
            node_id: Node identifier
            secret_key: Shared secret (simplified, not secure for production)
        """
        self.node_id = node_id
        self.secret_key = secret_key.encode()
    
    def sign(self, message_digest: str) -> str:
        """
        Sign message digest
        
        Args:
            message_digest: SHA256 hash of message
            
        Returns:
            Signature string
        """
        signature = hmac.new(
            self.secret_key,
            f"{self.node_id}:{message_digest}".encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def verify(self, sender_id: str, message_digest: str, signature: str) -> bool:
        """
        Verify signature
        
        Args:
            sender_id: Claimed sender ID
            message_digest: Message digest
            signature: Signature to verify
            
        Returns:
            True if valid, False otherwise
        """
        expected_signature = hmac.new(
            self.secret_key,
            f"{sender_id}:{message_digest}".encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)