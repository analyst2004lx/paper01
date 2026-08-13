# CTG-LC Experimental Data Generation

This repository contains the implementation of CTG-LC (Context-Aware Trust Graph for Localized Consensus) and scripts to generate experimental data for the paper.

## 🚀 Quick Start

### 1. Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

2. Run Experiments
Experiment 1: Baseline Decomposition
cd experiments
python exp1_baseline_decomposition.py

Output:

data/baseline_decomposition.csv - Raw experimental data
Console output with statistics
Expected Runtime: ~10-15 minutes (50 runs per protocol)

Experiment 2: Comparative Performance
cd experiments
python exp2_comparative.py

Output:

data/comparative.csv - Raw experimental data
Console output with statistics
Expected Runtime: ~20-30 minutes (50 runs × 5 concurrent task levels × 2 protocols)

3. Generate Figures
Generate baseline_decomposition.pdf
cd plots
python plot_baseline.py
Output:

results/baseline_decomposition.pdf
results/baseline_decomposition.png
Generate comparative.pdf
cd plots
python plot_comparative.py
Output:

results/comparative.pdf
results/comparative.png

Experiments Overview
Experiment 1: Baseline Decomposition
Purpose: Decompose CTG-LC's performance gains into components

Protocols Tested:

PBFT (n=30) - Global consensus baseline
PBFT-Local (k=3) - Domain localization only
CTG-LC (k=3, m=3) - Full CTG-LC with scheduler replication
CTG-LC-Global (k=30) - Validation of O(k²) → O(n²) degradation
Metrics:

Communication overhead (total messages)
Consensus latency (ms)
Throughput (tasks/sec)
Bandwidth utilization (%)
Key Results:

98.5% communication reduction (27 vs 1,770 messages)
60% latency reduction (152ms vs 382ms)
Linear throughput scaling vs PBFT saturation
Experiment 2: Comparative Performance
Purpose: Compare CTG-LC against state-of-the-art BFT protocols

Protocols:

CTG-LC (k=3, m=3)
PBFT (n=30)
Raft (n=30, simplified)
HotStuff (n=30, simplified)
Test Scenarios:

Concurrent tasks: 1, 2, 3, 4, 5
Measurement duration: 60 seconds per scenario
50 runs per configuration
Metrics:

Message overhead vs concurrent tasks
Latency breakdown (spatiotemporal + scheduler + agent)
Throughput scaling
Bandwidth utilization over time
⚙️ Configuration
Edit experiments/config.yaml to customize:

system:
  n: 30    # Total nodes
  k: 3     # Domain size
  m: 3     # Scheduler replicas
  f: 10    # Byzantine nodes

network:
  mean_delay: 0.03   # 30ms
  jitter: 0.01       # ±10ms
  packet_loss: 0.001 # 0.1%

experiments:
  baseline_decomposition:
    num_runs: 50
  comparative:
    num_runs: 50
    concurrent_tasks: [1, 2, 3, 4, 5]

## 📂 Directory Structure
CODE/
├── src/
│ ├── core/ # Core components
│ │ ├── message.py # Message definitions
│ │ ├── crypto.py # Cryptographic operations
│ │ ├── network.py # Network simulator
│ │ └── node.py # Base node class
│ ├── protocols/ # Protocol implementations
│ │ ├── ctg_lc.py # CTG-LC protocol
│ │ ├── pbft.py # PBFT baseline
│ │ └── raft.py # Raft baseline (simplified)
│ ├── utils/ # Utility modules
│ │ ├── spatiotemporal.py # Spatiotemporal validation
│ │ └── adaptive_weights.py # Adaptive weight management
│ └── attacks/ # Byzantine attack simulations
│ └── byzantine.py
├── experiments/ # Experiment scripts
│ ├── config.yaml # Configuration file
│ ├── exp1_baseline_decomposition.py
│ └── exp2_comparative.py
├── plots/ # Plotting scripts
│ ├── plot_baseline.py
│ └── plot_comparative.py
├── data/ # Generated CSV data
├── results/ # Generated PDF figures
├── requirements.txt
└── README.md


Implementation Details
Simplified Assumptions
This implementation uses simplified models for experimental feasibility:

Network Simulation:

Thread-based node simulation (not distributed)
Gaussian delay model (not full network stack)
Simplified packet loss (no congestion control)
Cryptography:

HMAC-SHA256 signatures (not Ed25519)
Shared secret (not public-key infrastructure)
Baseline Protocols:

Simplified PBFT (no view changes)
Raft/HotStuff simulated based on PBFT with scaling factors
Byzantine Attacks:

Not implemented in Experiments 1-2
Will be added in later experiments (robustness, clustered_byzantine, etc.)

##后续又添加了一些代码，为了完成：
plot_robustness
plot_clustered_byzantine
plot_cross_domain_attack
plot_scalability
plot_simulation_vs_testbed
plot_ablation

cd experiments

echo "Experiment 1: Baseline Decomposition"
python exp1_baseline_decomposition.py

echo "Experiment 2: Comparative Performance"
python exp2_comparative.py

echo "Experiment 3: Robustness"
python exp3_robustness.py

echo "Experiment 4: Clustered Byzantine"
python exp4_clustered_byzantine.py

echo "Experiment 5: Cross-Domain Attack"
python exp5_cross_domain_attack.py

echo "Experiment 6: Scalability"
python exp6_scalability.py

echo "Experiment 7: Simulation vs Testbed"
python exp7_simulation_vs_testbed.py

echo "Experiment 8: Ablation Study"
python exp8_ablation.py

cd ../plots

echo "Generating figures..."
python plot_baseline.py
python plot_comparative.py
python plot_robustness.py
python plot_clustered_byzantine.py
python plot_cross_domain_attack.py
python plot_scalability.py
python plot_simulation_vs_testbed.py
python plot_ablation.py

echo "All experiments completed!"

