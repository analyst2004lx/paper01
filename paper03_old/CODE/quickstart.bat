@echo off
REM ========================================
REM CTG-LC Quick Start Script (Windows)
REM ========================================

echo ==========================================
echo CTG-LC Experimental Framework Quick Start
echo ==========================================

REM Check Python version
echo.
echo Checking Python version...
python --version

REM Create virtual environment
echo.
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo.
echo Installing dependencies...
pip install -r requirements.txt

REM Create directories
echo.
echo Creating directories...
if not exist data mkdir data
if not exist results mkdir results
if not exist logs mkdir logs

REM Run experiments
echo.
echo Running experiments (this may take 30-60 minutes)...
cd experiments
python exp1_baseline_decomposition.py
python exp2_comparative.py
python exp3_robustness.py
python exp4_clustered_byzantine.py
python exp5_cross_domain_attack.py
python exp6_scalability.py
python exp7_simulation_vs_testbed.py
python exp8_ablation.py
cd ..

REM Generate plots
echo.
echo Generating plots...
cd plots
python plot_baseline.py
python plot_comparative.py
python plot_robustness.py
python plot_clustered_byzantine.py
python plot_cross_domain_attack.py
python plot_scalability.py
python plot_simulation_vs_testbed.py
python plot_ablation.py
cd ..

echo.
echo ==========================================
echo Quick start completed!
echo ==========================================
echo.
echo Results:
echo   - Data files: data\
echo   - Figures: results\
echo.
echo To view results:
echo   cd results
echo   start baseline_decomposition.pdf
echo.

pause