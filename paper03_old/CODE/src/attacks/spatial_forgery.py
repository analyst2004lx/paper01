"""
Spatial forgery attack
"""
import numpy as np
from ..core.message import Message, Position

class SpatialForgeryAttacker:
    """
    Forges spatial positions to violate kinematic constraints
    """
    
    def __init__(self, attacker_node_id: str, real_position: Position):
        self.attacker_id = attacker_node_id
        self.real_position = real_position
        self.forgery_count = 0
    
    def generate_forged_position(self, target_position: Position, 
                                 max_deviation: float = 3.0) -> Position:
        """
        Generate forged position near target
        
        Args:
            target_position: Desired position to claim
            max_deviation: Maximum deviation from real position (meters)
            
        Returns:
            Forged position
        """
        # Forge position within max_deviation of target
        angle = np.random.uniform(0, 2 * np.pi)
        distance = np.random.uniform(0, max_deviation)
        
        forged_x = target_position.x + distance * np.cos(angle)
        forged_y = target_position.y + distance * np.sin(angle)
        
        self.forgery_count += 1
        return Position(forged_x, forged_y)
    
    def generate_kinematic_violation(self, last_position: Position,
                                     time_elapsed: float,
                                     v_max: float = 2.0) -> Position:
        """
        Generate position that violates kinematic constraints
        
        Args:
            last_position: Previous claimed position
            time_elapsed: Time since last message
            v_max: Maximum velocity (m/s)
            
        Returns:
            Position requiring impossible velocity
        """
        # Generate position requiring 3x max velocity
        required_velocity = v_max * 3
        distance = required_velocity * time_elapsed
        
        angle = np.random.uniform(0, 2 * np.pi)
        forged_x = last_position.x + distance * np.cos(angle)
        forged_y = last_position.y + distance * np.sin(angle)
        
        self.forgery_count += 1
        return Position(forged_x, forged_y)