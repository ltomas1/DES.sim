The following files constitute the validation setup used to simulate the energy center in Building 4 of the housing district in Durlach, Karlsruhe.  

**Files:**  
* `main_sim.py`
* `input_params.json`  

**How to run the simulation**
1. Place files in the correct directories
    * Move/paste `main_sim.py` in the `src` directory.
    * Move/paste `input_params.json` in the `data/inputs` directory
2. Prepare the heatload time-series
    * In line 191 of `main_sim.py`, update the name of the file containing the heatload timeseries.  
    *Note*: Due to confidentiality reasons, the actual time-series inputs used in the project cannot be shared.   
    * Follow the columns names as in line 232 in `main_sim.py`.  
3. Run the simulation
    * Run `main_sim.py` from the directory `src`.