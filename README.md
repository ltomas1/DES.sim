# District Energy System (DES)

[![PyPI version](https://badge.fury.io/py/DES-sim.svg)](https://pypi.org/project/DES-sim/)
![Python](https://img.shields.io/badge/python-3.10-blue)

A Python package for simulating district heating networks using the [mosaik](https://pypi.org/project/mosaik/) co-simulation framework. Models include heat pumps, CHP units, boilers, PV systems, battery storage, and thermal tanks.

Developed at Hochschule Offenburg – Institute for Sustainable Energy Systems [INES](https://www.hs-offenburg.de/forschung/institute/ines-institut-fuer-nachhaltige-energiesysteme).

## Installation

Create a new conda environment:

```
conda create --name des_sim python=3.10.13
conda activate des_sim
pip install DES-sim
```

*(If you plan to modify the core models in the `src/` folder, install in editable mode instead using `pip install -e .`)*

## Usage

Run the simulation from the project root:

```
python main_sim.py
```

Configuration is pulled from `data/inputs/input_params.json`, and outputs are saved to `data/outputs/`.

## Documentation

The documentation for the individual models is available [here](https://github.com/ltomas1/DES.sim/tree/main/docs).