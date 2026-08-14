"""
Experiment 3: Robustness Against Byzantine Attacks
Generates data for robustness.pdf
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import time
import yaml

from src.core.network import NetworkSimulator
from src.core.message import Position, Task, Message, MessageType
from src.core.node import NodeRole
from src.protocols.ctg_lc import CTGLCNode
from src.attacks.replay_attack import ReplayAttacker
from src.attacks.spatial_forgery import SpatialForgeryAttacker
from src.attacks.cross_domain_attack import CrossDomainAttacker

class RobustnessExperiment:
    """
    Test CTG-LC robustness against various attacks
    """
    
    def __init__(self, config_path: str = "experiments/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.results = {
            'replay': {'detection_rate': [], 'false_positive': []},
            'spatial_forgery': {'detection_rate': [], 'false_positive': []},
            'conflicting_msgs': {'detection_rate': [], 'false_positive': []},
            'cross_domain': {'detection_rate': [], 'false_positive': []},
            'weight_evolution': [],
            'consensus_success': []
        }
    
    def run_replay_attack_experiment(self, num_runs: int = 50) -> dict:
        """Test replay attack detection"""
        print("\n" + "="*70)
        print("Testing Replay Attack Detection")
        print("="*70)
        
        detection_rates = []
        false_positives = []
        
        for run in range(num_runs):
            # Setup
            network = self.create_network()
            nodes, scheduler_ids = self.create_ctg_lc_nodes(network, k=3, m=3, 
                                                           num_byzantine=1)
            
            # Identify Byzantine node
            byzantine_node = [n for n in nodes if n.is_byzantine][0]
            attacker = ReplayAttacker(byzantine_node.node_id)
            
            network.start()
            
            # Run normal consensus first (to populate cache)
            task_id = f"task_{run}_normal"
            domain = [n.node_id for n in nodes if not n.is_scheduler][:3]
            
            # ... initiate consensus ...
            time.sleep(0.5)
            
            # Now launch replay attacks
            num_attacks = 100
            detected = 0
            
            for i in range(num_attacks):
                # Generate replay attack
                attack_msg = attacker.generate_replay_attack(
                    target_task_id=f"task_{run}_attack_{i}",
                    delay=1.0
                )
                
                if attack_msg:
                    # Send to all nodes
                    network.send(attack_msg, domain)
                    time.sleep(0.01)
            
            time.sleep(0.5)
            
            # Count detections
            for node in nodes:
                if not node.is_byzantine:
                    detected += node.replay_attacks_detected
            
            # Calculate detection rate
            detection_rate = (detected / (num_attacks * len([n for n in nodes if not n.is_byzantine]))) * 100
            detection_rates.append(detection_rate)
            
            # Calculate false positives (honest messages rejected)
            total_honest_msgs = sum(n.messages_sent for n in nodes if not n.is_byzantine)
            total_rejections = sum(n.spatiotemporal_rejections for n in nodes)
            fp_rate = ((total_rejections - detected) / max(1, total_honest_msgs)) * 100
            false_positives.append(fp_rate)
            
            network.stop()
            
            if (run + 1) % 10 == 0:
                print(f"  Completed {run + 1}/{num_runs} runs")
        
        return {
            'detection_rate_mean': np.mean(detection_rates),
            'detection_rate_std': np.std(detection_rates),
            'false_positive_mean': np.mean(false_positives),
            'false_positive_std': np.std(false_positives)
        }
    
    # Similar methods for other attack types...
    
    def run_weight_evolution_experiment(self, num_rounds: int = 100) -> dict:
        """Track weight evolution under attacks"""
        print("\n" + "="*70)
        print("Testing Weight Evolution")
        print("="*70)
        
        network = self.create_network()
        nodes, scheduler_ids = self.create_ctg_lc_nodes(network, k=3, m=3,
                                                       num_byzantine=1)
        
        byzantine_node = [n for n in nodes if n.is_byzantine][0]
        honest_node = [n for n in nodes if not n.is_byzantine and not n.is_scheduler][0]
        
        network.start()
        
        weight_history = {
            'byzantine': [],
            'honest': []
        }
        
        for round_num in range(num_rounds):
            # Byzantine node sends invalid messages every 3 rounds
            if round_num % 3 == 0 and round_num >= 10:
                # Generate spatial forgery
                from src.attacks.spatial_forgery import SpatialForgeryAttacker
                attacker = SpatialForgeryAttacker(byzantine_node.node_id, 
                                                 byzantine_node.position)
                
                forged_pos = attacker.generate_kinematic_violation(
                    byzantine_node.position, 0.1, v_max=2.0
                )
                
                # Send message with forged position
                attack_msg = Message(
                    msg_type=MessageType.PREPARE,
                    sender_id=byzantine_node.node_id,
                    timestamp=time.time(),
                    position=forged_pos,
                    task_id=f"task_{round_num}",
                    payload={"action": "attack"}
                )
                
                network.send(attack_msg, [honest_node.node_id])
            
            time.sleep(0.05)
            
            # Record weights
            weight_history['byzantine'].append(
                honest_node.weight_manager.get_weight(byzantine_node.node_id)
            )
            weight_history['honest'].append(
                honest_node.weight_manager.get_weight(honest_node.node_id)
            )
        
        network.stop()
        
        return weight_history
    
    # ... helper methods (create_network, create_ctg_lc_nodes, etc.) ...

    def create_network(self) -> NetworkSimulator:
        """Create NetworkSimulator using config or defaults"""
        net_conf = self.config.get('network', {})
        return NetworkSimulator(
            mean_delay=net_conf.get('mean_delay', 0.03),
            jitter=net_conf.get('jitter', 0.01),
            packet_loss=net_conf.get('packet_loss', 0.001),
            bandwidth_limit=net_conf.get('bandwidth_limit', None)
        )

    def create_ctg_lc_nodes(self, network, k, m, num_byzantine: int = 0):
        """Create CTG-LC schedulers and agent nodes for tests.

        Returns (nodes_list, scheduler_ids)
        """
        scheduler_ids = [f"scheduler_{i}" for i in range(m)]

        schedulers = []
        for sched_id in scheduler_ids:
            scheduler = CTGLCNode(
                node_id=sched_id,
                role=NodeRole.SCHEDULER,
                position=Position(5.0, 5.0),
                network_simulator=network,
                scheduler_ids=scheduler_ids
            )
            schedulers.append(scheduler)

        agents = []
        for i in range(k):
            is_byzantine = (i < num_byzantine)
            agent = CTGLCNode(
                node_id=f"agent_{i}",
                role=NodeRole.AGV,
                position=Position(np.random.uniform(1, 9), np.random.uniform(1, 9)),
                network_simulator=network,
                scheduler_ids=scheduler_ids,
                is_byzantine=is_byzantine
            )
            agents.append(agent)

        return schedulers + agents, scheduler_ids