"""
Spatiotemporal validation for CTG-LC
"""
import time
from typing import Optional
from ..core.message import Message, Position

class SpatiotemporalValidator:
    """
    Validates messages based on timestamps and spatial constraints
    """
    
    def __init__(self,
                 delta_t: float = 0.6,      # 600ms (clock drift + max delay)
                 epsilon: float = 0.5,       # 0.5m spatial tolerance
                 v_max: float = 2.0,         # 2 m/s max velocity
                 clock_drift: float = 0.1):  # 100ms clock drift
        """
        Args:
            delta_t: Maximum acceptable timestamp deviation (seconds)
            epsilon: Spatial tolerance (meters)
            v_max: Maximum agent velocity (m/s)
            clock_drift: Maximum clock drift (seconds)
        """
        self.delta_t = delta_t
        self.epsilon = epsilon
        self.v_max = v_max
        self.clock_drift = clock_drift
        
        # Track last known positions
        self.last_positions: dict = {}  # node_id -> (position, timestamp)
        
        # Violation statistics
        self.timestamp_violations = 0
        self.spatial_violations = 0
        self.kinematic_violations = 0
        self.total_validations = 0
    
    def validate_timestamp(self, message: Message) -> bool:
        """
        Validate message timestamp
        
        Args:
            message: Message to validate
            
        Returns:
            True if timestamp is valid, False otherwise
        """
        self.total_validations += 1
        
        current_time = time.time()
        time_diff = abs(message.timestamp - current_time)
        
        if time_diff > self.delta_t:
            self.timestamp_violations += 1
            return False
        
        return True
    
    def validate_spatial(self, message: Message, expected_position: Optional[Position] = None) -> bool:
        """
        Validate spatial position
        
        Args:
            message: Message to validate
            expected_position: Expected position (if known)
            
        Returns:
            True if position is valid, False otherwise
        """
        if message.position is None:
            return True  # No position to validate
        
        # If expected position is provided, check deviation
        if expected_position is not None:
            distance = message.position.distance_to(expected_position)
            if distance > self.epsilon:
                self.spatial_violations += 1
                return False
        
        return True
    
    def validate_kinematic(self, message: Message) -> bool:
        """
        Validate kinematic feasibility (for mobile agents)
        
        Args:
            message: Message to validate
            
        Returns:
            True if kinematically feasible, False otherwise
        """
        if message.position is None:
            return True
        
        sender_id = message.sender_id
        
        # Check if we have previous position
        if sender_id in self.last_positions:
            last_pos, last_time = self.last_positions[sender_id]
            
            # Calculate required velocity
            distance = message.position.distance_to(last_pos)
            time_elapsed = message.timestamp - last_time
            
            if time_elapsed > 0:
                required_velocity = distance / time_elapsed
                
                if required_velocity > self.v_max:
                    self.kinematic_violations += 1
                    return False
        
        # Update last known position
        self.last_positions[sender_id] = (message.position, message.timestamp)
        
        return True
    
    def validate_message(self, message: Message, expected_position: Optional[Position] = None) -> tuple:
        """
        Perform complete spatiotemporal validation
        
        Args:
            message: Message to validate
            expected_position: Expected position (optional)
            
        Returns:
            (is_valid, violation_type) where violation_type is one of:
            None, 'timestamp', 'spatial', 'kinematic'
        """
        # Temporal validation
        if not self.validate_timestamp(message):
            return (False, 'timestamp')
        
        # Spatial validation
        if not self.validate_spatial(message, expected_position):
            return (False, 'spatial')
        
        # Kinematic validation
        if not self.validate_kinematic(message):
            return (False, 'kinematic')
        
        return (True, None)
    
    def get_statistics(self) -> dict:
        """Get validation statistics"""
        return {
            'total_validations': self.total_validations,
            'timestamp_violations': self.timestamp_violations,
            'spatial_violations': self.spatial_violations,
            'kinematic_violations': self.kinematic_violations,
            'rejection_rate': (self.timestamp_violations + self.spatial_violations + 
                             self.kinematic_violations) / max(1, self.total_validations)
        }
    
    def reset_statistics(self):
        """Reset statistics"""
        self.timestamp_violations = 0
        self.spatial_violations = 0
        self.kinematic_violations = 0
        self.total_validations = 0