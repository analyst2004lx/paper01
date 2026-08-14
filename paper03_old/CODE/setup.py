"""
Setup script for CTG-LC experimental framework
"""

from setuptools import setup, find_packages
import os

# Read README for long description
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ''

# Read requirements
def read_requirements(filename='requirements.txt', _seen=None):
    """Read a pip requirements file and resolve any recursive '-r other.txt' includes.

    Returns a flat list of requirement specifiers (comments and empty lines removed).
    """
    if _seen is None:
        _seen = set()

    req_path = os.path.join(os.path.dirname(__file__), filename)
    requirements = []
    if not os.path.exists(req_path):
        return requirements

    # Avoid cycles
    if req_path in _seen:
        return requirements
    _seen.add(req_path)

    with open(req_path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            # Support '-r other_requirements.txt' includes
            if line.startswith('-r ') or line.startswith('--requirement '):
                parts = line.split(None, 1)
                if len(parts) == 2:
                    ref = parts[1]
                    # Resolve relative paths
                    ref_path = os.path.join(os.path.dirname(req_path), ref)
                    # Convert to relative filename for recursive call
                    try:
                        rel = os.path.relpath(ref_path, os.path.dirname(__file__))
                    except Exception:
                        rel = ref
                    requirements.extend(read_requirements(rel, _seen))
                continue
            requirements.append(line)
    return requirements

setup(
    name='ctg-lc-experiments',
    version='1.0.0',
    author='CTG-LC Research Team',
    author_email='your-email@example.com',
    description='Experimental framework for CTG-LC protocol evaluation',
    long_description=read_readme(),
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/ctg-lc-experiments',
    packages=find_packages(exclude=['tests', 'experiments', 'plots']),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],
    python_requires='>=3.8',
    install_requires=read_requirements(),
    extras_require={
        'dev': read_requirements('requirements-dev.txt'),
    },
    entry_points={
        'console_scripts': [
            'ctg-lc-run=experiments.run_all:main',
        ],
    },
    include_package_data=True,
    package_data={
        'experiments': ['config.yaml'],
    },
)