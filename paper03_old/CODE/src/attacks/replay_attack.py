"""
Replay attack simulation
"""
import time
from typing import List
from ..core.message import Message, MessageType

class ReplayAttacker:
    """
    Simulates replay attacks by resending old messages
    """
    
    def __init__(self, attacker_node_id: str):
        self.attacker_id = attacker_node_id
        self.message_cache = []  # Store intercepted messages
        self.replay_count = 0
    
    def intercept_message(self, message: Message):
        """Store message for later replay"""
        self.message_cache.append(message.to_dict())
    
    def generate_replay_attack(self, target_task_id: str, 
                               delay: float = 1.0) -> Message:
        """
        Generate replay attack by resending old message
        
        Args:
            target_task_id: Task to attack
            delay: Time delay for replay (seconds)
            
        Returns:
            Replayed message with old timestamp
        """
        if not self.message_cache:
            return None
        
        # Pick a random cached message
        import random
        cached = random.choice(self.message_cache)
        
        # Create replay with old timestamp
        replay_msg = Message.from_dict(cached)
        replay_msg.task_id = target_task_id
        replay_msg.sender_id = self.attacker_id
        # Keep old timestamp (this will violate Δt check)
        
        self.replay_count += 1
        return replay_msg