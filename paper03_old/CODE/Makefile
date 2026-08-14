# ========================================
# CTG-LC Experimental Framework Makefile
# ========================================

.PHONY: help install install-dev clean test lint format run-all run-exp1 run-exp2 plot-all

# Default target
help:
	@echo "CTG-LC Experimental Framework"
	@echo "=============================="
	@echo ""
	@echo "Available targets:"
	@echo "  install       - Install dependencies"
	@echo "  install-dev   - Install development dependencies"
	@echo "  clean         - Remove generated files"
	@echo "  test          - Run tests"
	@echo "  lint          - Run linters"
	@echo "  format        - Format code with black"
	@echo "  run-all       - Run all experiments"
	@echo "  run-exp1      - Run baseline decomposition experiment"
	@echo "  run-exp2      - Run comparative performance experiment"
	@echo "  run-exp3      - Run robustness experiment"
	@echo "  run-exp4      - Run clustered Byzantine experiment"
	@echo "  run-exp5      - Run cross-domain attack experiment"
	@echo "  run-exp6      - Run scalability experiment"
	@echo "  run-exp7      - Run simulation vs testbed experiment"
	@echo "  run-exp8      - Run ablation study"
	@echo "  plot-all      - Generate all plots"

# Install dependencies
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

# Clean generated files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache/ .mypy_cache/ .coverage htmlcov/
	@echo "Cleaned generated files"

# Run tests
test:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

# Linting
lint:
	flake8 src/ experiments/ plots/
	pylint src/ experiments/ plots/

# Code formatting
format:
	black src/ experiments/ plots/
	isort src/ experiments/ plots/

# Run all experiments
run-all:
	@echo "Running all CTG-LC experiments..."
	cd experiments && python exp1_baseline_decomposition.py
	cd experiments && python exp2_comparative.py
	cd experiments && python exp3_robustness.py
	cd experiments && python exp4_clustered_byzantine.py
	cd experiments && python exp5_cross_domain_attack.py
	cd experiments && python exp6_scalability.py
	cd experiments && python exp7_simulation_vs_testbed.py
	cd experiments && python exp8_ablation.py
	@echo "All experiments completed!"

# Individual experiments
run-exp1:
	cd experiments && python exp1_baseline_decomposition.py

run-exp2:
	cd experiments && python exp2_comparative.py

run-exp3:
	cd experiments && python exp3_robustness.py

run-exp4:
	cd experiments && python exp4_clustered_byzantine.py

run-exp5:
	cd experiments && python exp5_cross_domain_attack.py

run-exp6:
	cd experiments && python exp6_scalability.py

run-exp7:
	cd experiments && python exp7_simulation_vs_testbed.py

run-exp8:
	cd experiments && python exp8_ablation.py

# Generate all plots
plot-all:
	@echo "Generating all plots..."
	cd plots && python plot_baseline.py
	cd plots && python plot_comparative.py
	cd plots && python plot_robustness.py
	cd plots && python plot_clustered_byzantine.py
	cd plots && python plot_cross_domain_attack.py
	cd plots && python plot_scalability.py
	cd plots && python plot_simulation_vs_testbed.py
	cd plots && python plot_ablation.py
	@echo "All plots generated!"

# Quick start (install + run + plot)
quickstart: install run-all plot-all
	@echo "Quickstart completed! Check results/ for figures."