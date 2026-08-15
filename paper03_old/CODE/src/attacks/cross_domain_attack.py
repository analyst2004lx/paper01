"""
Cross-domain attack simulation
"""
from typing import List, Set
from ..core.message import Message, MessageType

class CrossDomainAttacker:
    """
    Byzantine node in domain C(τ1) sends messages about τ2
    """
    
    def __init__(self, attacker_node_id: str, 
                 legitimate_tasks: Set[str]):
        self.attacker_id = attacker_node_id
        self.legitimate_tasks = legitimate_tasks  # Tasks this node should participate in
        self.attack_count = 0
    
    def generate_cross_domain_message(self, 
                                      unauthorized_task_id: str,
                                      message_type: MessageType,
                                      payload: any) -> Message:
        """
        Generate message for task outside attacker's domain
        
        Args:
            unauthorized_task_id: Task ID not in attacker's domain
            message_type: Type of consensus message
            payload: Message payload
            
        Returns:
            Cross-domain attack message
        """
        if unauthorized_task_id in self.legitimate_tasks:
            raise ValueError("Task is in legitimate domain")
        
        import time
        from ..core.message import Position
        
        # Create message for unauthorized task
        attack_msg = Message(
            msg_type=message_type,
            sender_id=self.attacker_id,
            timestamp=time.time(),
            position=Position(5.0, 5.0),  # Fake position
            task_id=unauthorized_task_id,
            payload=payload
        )
        
        self.attack_count += 1
        return attack_msg