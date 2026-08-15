"""Quick smoke test to import and run each experiment with minimal workload.
This runs each experiment's main path with reduced sizes to check for import/runtime errors.
"""

from experiments import exp1_baseline_decomposition as exp1
from experiments import exp2_comparative as exp2
from experiments import exp3_robustness as exp3
from experiments import exp4_clustered_byzantine as exp4
from experiments import exp5_cross_domain_attack as exp5
from experiments import exp6_scalability as exp6
from experiments import exp7_simulation_vs_testbed as exp7
from experiments import exp8_ablation as exp8


def run_smoke():
    failures = []
    import os
    os.makedirs('data', exist_ok=True)

    try:
        print('\n=== Smoke: Exp1 (short) ===')
        e1 = exp1.BaselineDecompositionExperiment(config_path='experiments/config.yaml')
        # Run reduced workload: override num_runs to 1 and call relevant functions
        e1.config['experiments']['baseline_decomposition']['num_runs'] = 1
        e1.run_all_experiments()
        # Save CSV results
        if hasattr(e1, 'save_results'):
            e1.save_results('data/baseline_decomposition.csv')
    except Exception as exc:
        print('Exp1 failed:', exc)
        failures.append(('exp1', exc))

    try:
        print('\n=== Smoke: Exp2 (short) ===')
        e2 = exp2.ComparativeExperiment(config_path='experiments/config.yaml')
        e2.config['experiments']['comparative']['num_runs'] = 1
        e2.config['experiments']['comparative']['concurrent_tasks'] = [1]
        e2.run_all_experiments()
        if hasattr(e2, 'save_results'):
            e2.save_results('data/comparative.csv')
    except Exception as exc:
        print('Exp2 failed:', exc)
        failures.append(('exp2', exc))

    try:
        print('\n=== Smoke: Exp3 (short) ===')
        e3 = exp3.RobustnessExperiment(config_path='experiments/config.yaml')
        # Call a light-weight method if available
        out3 = e3.run_weight_evolution_experiment(num_rounds=5)
        print('Exp3 weight evolution sample:', out3)
        if hasattr(e3, 'save_results'):
            # Some experiments split outputs; attempt a generic save if available
            try:
                e3.save_results('data/robustness.csv')
            except Exception:
                pass
    except Exception as exc:
        print('Exp3 failed:', exc)
        failures.append(('exp3', exc))

    try:
        print('\n=== Smoke: Exp4 (short) ===')
        e4 = exp4.ClusteredByzantineExperiment(config_path='experiments/config.yaml')
        out4 = e4.generate_spatial_distribution(n=10, f=3)
        print('Exp4 spatial sample:', out4['task_analysis'])
        # Compute small-scale violation probabilities and domain expansion to populate results
        vp = e4.calculate_violation_probabilities(n=10, f=3, k=3, num_simulations=10)
        de = e4.simulate_domain_expansion(num_tasks=100, n=10, f=3, k=3)
        e4.results['spatial_distribution'] = out4
        e4.results['violation_probability'] = vp
        e4.results['domain_expansion'] = de
        if hasattr(e4, 'save_results'):
            e4.save_results('data/clustered_byzantine.csv')
    except Exception as exc:
        print('Exp4 failed:', exc)
        failures.append(('exp4', exc))

    try:
        print('\n=== Smoke: Exp5 (short) ===')
        e5 = exp5.CrossDomainAttackExperiment(config_path='experiments/config.yaml')
        # Run small timeline and weight experiments and detection profile
        timeline = e5.run_timeline_experiment(duration=5, num_runs=1)
        weight = e5.run_weight_evolution_experiment(num_rounds=30)
        detection = e5.run_detection_vs_latency_experiment(latency_range=[10, 20])
        print('Exp5 detection sample:', detection)
        e5.results['timeline'] = timeline
        e5.results['weight_evolution'] = weight
        e5.results['detection_vs_latency'] = detection
        if hasattr(e5, 'save_results'):
            e5.save_results('data/cross_domain_attack.csv')
    except Exception as exc:
        print('Exp5 failed:', exc)
        failures.append(('exp5', exc))

    try:
        print('\n=== Smoke: Exp6 (short) ===')
        e6 = exp6.ScalabilityExperiment(config_path='experiments/config.yaml')
        # Run a single small scalability test
        n_values = [10, 20, 30]
        e6.results = { 'ctg_lc': [], 'pbft': [], 'raft': [], 'hotstuff': [] }
        for n in n_values:
            r_ctg = e6.run_scalability_test('ctg_lc', n=n, num_runs=1)
            r_pbft = e6.run_scalability_test('pbft', n=n, num_runs=1)
            e6.results['ctg_lc'].append(r_ctg)
            e6.results['pbft'].append(r_pbft)
        print('Exp6 sample (n=10):', e6.results['ctg_lc'][0])
        if hasattr(e6, 'save_results'):
            e6.save_results('data/scalability.csv')
    except Exception as exc:
        print('Exp6 failed:', exc)
        failures.append(('exp6', exc))

    try:
        print('\n=== Smoke: Exp7 (short) ===')
        e7 = exp7.SimulationVsTestbedExperiment(config_path='experiments/config.yaml')
        out7 = e7.run_simulation_experiment(num_tasks=5, concurrent_tasks=[1])
        out_tb = e7.run_testbed_experiment(num_tasks=5, concurrent_tasks=[1])
        e7.results['simulation'] = out7
        e7.results['testbed'] = out_tb
        print('Exp7 sample:', {'latency_mean': out7.get('latency_mean')})
        if hasattr(e7, 'save_results'):
            e7.save_results('data/simulation_vs_testbed.csv')
    except Exception as exc:
        print('Exp7 failed:', exc)
        failures.append(('exp7', exc))

    try:
        print('\n=== Smoke: Exp8 (short) ===')
        e8 = exp8.AblationStudyExperiment(config_path='experiments/config.yaml')
        e8.run_all_experiments()
        print('Exp8 completed')
        if hasattr(e8, 'save_results'):
            e8.save_results('data/ablation.csv')
    except Exception as exc:
        print('Exp8 failed:', exc)
        failures.append(('exp8', exc))

    print('\n=== Smoke Test Summary ===')
    if failures:
        for name, err in failures:
            print(f"  {name} failed: {err}")
    else:
        print('  All experiments imported and ran (short) without uncaught exceptions')


if __name__ == '__main__':
    run_smoke()
