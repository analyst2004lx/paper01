#!/bin/bash

# ========================================
# CTG-LC Quick Start Script
# ========================================

set -e  # Exit on error

echo "=========================================="
echo "CTG-LC Experimental Framework Quick Start"
echo "=========================================="

# Check Python version
echo ""
echo "Checking Python version..."
python3 --version

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

# Create directories
echo ""
echo "Creating directories..."
mkdir -p data
mkdir -p results
mkdir -p logs

# Run experiments
echo ""
echo "Running experiments (this may take 30-60 minutes)..."
make run-all

# Generate plots
echo ""
echo "Generating plots..."
make plot-all

echo ""
echo "=========================================="
echo "Quick start completed!"
echo "=========================================="
echo ""
echo "Results:"
echo "  - Data files: data/"
echo "  - Figures: results/"
echo ""
echo "To view results:"
echo "  cd results"
echo "  open baseline_decomposition.pdf"
echo ""