"""
Experiment 4: Clustered Byzantine Distribution
Generates data for clustered_byzantine.pdf
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import time
import yaml
from typing import List, Tuple

from src.core.network import NetworkSimulator
from src.core.message import Position, Task, Message, MessageType
from src.core.node import NodeRole
from src.protocols.ctg_lc import CTGLCNode
from src.attacks.clustered_byzantine import ClusteredByzantineDistribution

class ClusteredByzantineExperiment:
    """
    Analyze impact of clustered Byzantine node distribution
    """
    
    def __init__(self, config_path: str = "experiments/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.results = {
            'spatial_distribution': {},
            'violation_probability': {},
            'domain_expansion': {}
        }
    
    def generate_spatial_distribution(self, n: int = 30, f: int = 10) -> dict:
        """
        Generate and analyze spatial distribution
        
        Args:
            n: Total nodes
            f: Byzantine nodes
            
        Returns:
            Distribution data
        """
        print("\n" + "="*70)
        print("Generating Spatial Distribution")
        print("="*70)
        
        distributor = ClusteredByzantineDistribution(
            workspace_width=10.0,
            workspace_height=10.0
        )
        
        # Generate clustered Byzantine positions
        byzantine_positions = distributor.generate_clustered_positions(
            num_byzantine=f,
            cluster_center=(2.5, 2.5),
            cluster_radius=2.0
        )
        
        # Generate honest node positions (avoiding cluster)
        honest_positions = []
        for _ in range(n - f):
            while True:
                x = np.random.uniform(0.5, 9.5)
                y = np.random.uniform(0.5, 9.5)
                # Avoid Byzantine cluster region
                if not (x < 5 and y < 5):
                    honest_positions.append(Position(x, y))
                    break
        
        # Analyze task domains
        k = 3
        task_locations = [
            (7.5, 7.5, 'tau1'),  # Avoids cluster
            (2.5, 7.5, 'tau2'),  # Edge
            (2.0, 2.0, 'tau3')   # Inside cluster
        ]
        
        task_analysis = []
        
        for tx, ty, task_name in task_locations:
            task_pos = Position(tx, ty)
            
            # Combine all positions
            all_positions = honest_positions + byzantine_positions
            is_byzantine = [False] * len(honest_positions) + [True] * len(byzantine_positions)
            
            # Find k nearest nodes
            distances = [task_pos.distance_to(pos) for pos in all_positions]
            nearest_indices = np.argsort(distances)[:k]
            
            # Count Byzantine nodes in domain
            byzantine_count = sum(1 for idx in nearest_indices if is_byzantine[idx])
            
            task_analysis.append({
                'task_name': task_name,
                'position': (tx, ty),
                'byzantine_count': byzantine_count,
                'domain_size': k,
                'violates_bound': byzantine_count >= k / 3
            })
            
            print(f"  Task {task_name}: {byzantine_count}/{k} Byzantine nodes")
        
        return {
            'byzantine_positions': [(p.x, p.y) for p in byzantine_positions],
            'honest_positions': [(p.x, p.y) for p in honest_positions],
            'task_analysis': task_analysis
        }
    
    def calculate_violation_probabilities(self, n: int = 30, f: int = 10, 
                                         k: int = 3, num_simulations: int = 1000) -> dict:
        """
        Calculate P(f_local >= k/3) for uniform vs clustered distributions
        
        Args:
            n: Total nodes
            f: Byzantine nodes
            k: Domain size
            num_simulations: Monte Carlo simulations
            
        Returns:
            Violation probabilities
        """
        print("\n" + "="*70)
        print(f"Calculating Violation Probabilities ({num_simulations} simulations)")
        print("="*70)
        
        distributor = ClusteredByzantineDistribution()
        
        # Uniform distribution
        uniform_byzantine = distributor.generate_uniform_positions(f)
        uniform_honest = distributor.generate_uniform_positions(n - f)
        
        uniform_prob = distributor.calculate_violation_probability(
            uniform_byzantine, uniform_honest, k, num_simulations
        )
        
        # Clustered distribution
        clustered_byzantine = distributor.generate_clustered_positions(
            num_byzantine=f,
            cluster_center=(2.5, 2.5),
            cluster_radius=2.0
        )
        
        clustered_honest = []
        for _ in range(n - f):
            while True:
                x = np.random.uniform(0.5, 9.5)
                y = np.random.uniform(0.5, 9.5)
                if not (x < 5 and y < 5):
                    clustered_honest.append(Position(x, y))
                    break
        
        clustered_prob = distributor.calculate_violation_probability(
            clustered_byzantine, clustered_honest, k, num_simulations
        )
        
        reduction = ((uniform_prob - clustered_prob) / uniform_prob) * 100
        
        print(f"  Uniform distribution: {uniform_prob*100:.1f}%")
        print(f"  Clustered distribution: {clustered_prob*100:.1f}%")
        print(f"  Reduction: {reduction:.1f}%")
        
        return {
            'uniform': uniform_prob * 100,
            'clustered': clustered_prob * 100,
            'reduction': reduction
        }
    
    def simulate_domain_expansion(self, num_tasks: int = 1000, 
                                  n: int = 30, f: int = 10, k: int = 3) -> dict:
        """
        Simulate domain expansion overhead over many tasks
        
        Args:
            num_tasks: Number of tasks to simulate
            n: Total nodes
            f: Byzantine nodes
            k: Initial domain size
            
        Returns:
            Expansion statistics
        """
        print("\n" + "="*70)
        print(f"Simulating Domain Expansion ({num_tasks} tasks)")
        print("="*70)
        
        distributor = ClusteredByzantineDistribution()
        
        # Generate clustered distribution
        byzantine_positions = distributor.generate_clustered_positions(
            num_byzantine=f,
            cluster_center=(2.5, 2.5),
            cluster_radius=2.0
        )
        
        honest_positions = []
        for _ in range(n - f):
            while True:
                x = np.random.uniform(0.5, 9.5)
                y = np.random.uniform(0.5, 9.5)
                if not (x < 5 and y < 5):
                    honest_positions.append(Position(x, y))
                    break
        
        all_positions = honest_positions + byzantine_positions
        is_byzantine = [False] * len(honest_positions) + [True] * len(byzantine_positions)
        
        # Simulate tasks
        avoiding_cluster = 0
        triggering_expansion = 0
        expansion_failures = 0
        
        messages_avoiding = []
        messages_expansion = []
        messages_failure = []
        
        for task_num in range(num_tasks):
            # Random task position
            task_x = np.random.uniform(0, 10)
            task_y = np.random.uniform(0, 10)
            task_pos = Position(task_x, task_y)
            
            # Find k nearest nodes
            distances = [task_pos.distance_to(pos) for pos in all_positions]
            nearest_indices = np.argsort(distances)[:k]
            
            # Count Byzantine nodes in initial domain
            byzantine_count_k = sum(1 for idx in nearest_indices if is_byzantine[idx])
            
            if byzantine_count_k < k / 3:
                # Avoids cluster - no expansion needed
                avoiding_cluster += 1
                messages_avoiding.append(27)  # k² + m² + mk = 9 + 9 + 9 = 27
            else:
                # Triggers expansion to k=7
                k_expanded = 7
                nearest_indices_expanded = np.argsort(distances)[:k_expanded]
                byzantine_count_k7 = sum(1 for idx in nearest_indices_expanded if is_byzantine[idx])
                
                if byzantine_count_k7 < k_expanded / 3:
                    # Expansion successful
                    triggering_expansion += 1
                    # Messages: original 27 + expansion overhead 28 = 55
                    messages_expansion.append(55)
                else:
                    # Expansion failed - fallback to PBFT
                    expansion_failures += 1
                    messages_failure.append(1770)  # PBFT with n=30
        
        # Calculate statistics
        total_messages = (
            sum(messages_avoiding) + 
            sum(messages_expansion) + 
            sum(messages_failure)
        )
        
        weighted_avg = total_messages / num_tasks
        reduction_vs_pbft = (1 - weighted_avg / 1770) * 100
        
        print(f"  Avoiding cluster: {avoiding_cluster} ({avoiding_cluster/num_tasks*100:.1f}%)")
        print(f"  Triggering expansion: {triggering_expansion} ({triggering_expansion/num_tasks*100:.1f}%)")
        print(f"  Expansion failures: {expansion_failures} ({expansion_failures/num_tasks*100:.1f}%)")
        print(f"  Weighted average messages: {weighted_avg:.1f}")
        print(f"  Reduction vs PBFT: {reduction_vs_pbft:.1f}%")
        
        return {
            'avoiding_cluster': avoiding_cluster,
            'triggering_expansion': triggering_expansion,
            'expansion_failures': expansion_failures,
            'messages_avoiding': 27,
            'messages_expansion': 55,
            'messages_failure': 1770,
            'weighted_avg_messages': weighted_avg,
            'reduction_vs_pbft': reduction_vs_pbft
        }
    
    def run_all_experiments(self):
        """Run all clustered Byzantine experiments"""
        n = self.config['system']['n']
        f = self.config['system']['f']
        k = self.config['system']['k']
        
        # Experiment 1: Spatial distribution
        print("\n" + "="*70)
        print("EXPERIMENT 1: Spatial Distribution Analysis")
        print("="*70)
        self.results['spatial_distribution'] = self.generate_spatial_distribution(n, f)
        
        # Experiment 2: Violation probabilities
        print("\n" + "="*70)
        print("EXPERIMENT 2: Violation Probability Comparison")
        print("="*70)
        self.results['violation_probability'] = self.calculate_violation_probabilities(
            n, f, k, num_simulations=1000
        )
        
        # Experiment 3: Domain expansion overhead
        print("\n" + "="*70)
        print("EXPERIMENT 3: Domain Expansion Overhead")
        print("="*70)
        self.results['domain_expansion'] = self.simulate_domain_expansion(
            num_tasks=1000, n=n, f=f, k=k
        )
    
    def save_results(self, output_path: str = "data/clustered_byzantine.csv"):
        """Save results to CSV"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Create DataFrame for violation probabilities
        violation_data = {
            'distribution': ['uniform', 'clustered'],
            'violation_probability': [
                self.results['violation_probability']['uniform'],
                self.results['violation_probability']['clustered']
            ]
        }
        df_violation = pd.DataFrame(violation_data)
        
        # Create DataFrame for domain expansion
        expansion_data = {
            'scenario': ['avoiding_cluster', 'triggering_expansion', 'expansion_failures'],
            'count': [
                self.results['domain_expansion']['avoiding_cluster'],
                self.results['domain_expansion']['triggering_expansion'],
                self.results['domain_expansion']['expansion_failures']
            ],
            'messages': [
                self.results['domain_expansion']['messages_avoiding'],
                self.results['domain_expansion']['messages_expansion'],
                self.results['domain_expansion']['messages_failure']
            ]
        }
        df_expansion = pd.DataFrame(expansion_data)
        
        # Save
        df_violation.to_csv(output_path.replace('.csv', '_violation.csv'), index=False)
        df_expansion.to_csv(output_path.replace('.csv', '_expansion.csv'), index=False)
        
        print(f"\n✅ Results saved to {output_path}")
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print("\nViolation Probabilities:")
        print(df_violation.to_string(index=False))
        print("\nDomain Expansion:")
        print(df_expansion.to_string(index=False))
        print(f"\nWeighted Average Messages: {self.results['domain_expansion']['weighted_avg_messages']:.1f}")
        print(f"Reduction vs PBFT: {self.results['domain_expansion']['reduction_vs_pbft']:.1f}%")

if __name__ == "__main__":
    print("="*70)
    print("CTG-LC Clustered Byzantine Distribution Experiment")
    print("="*70)
    
    experiment = ClusteredByzantineExperiment()
    experiment.run_all_experiments()
    experiment.save_results()
    
    print("\n✅ Experiment completed!")