# CHP model

The CHP model builds on top of the mosaik heat pump model. The base file *chp_mosaik.py* handles the scheduling and contains the other required mosaik methods.  
*chp_model.py* details the functioning of the chp model.  

# Parameters
The chp model accepts 6 parameters :
~~~python
params_chp = {'eff_el': 0.54,
                'nom_P_th': 92_000,
                'mdot': 4.0,
                'startup_coeff' : [-2.63, 3.9, 0.57], 
                'eta' : 0.5897, 
                'hv' : HV
                }
~~~
- ***eff_el*** : Specifies the electricity generated as a fraction of the heat output.
- ***nom_P_th*** : The nominal power output of the chp plant in Watts.
- ***mdot*** : The nominal flow rate of the water circuit (in kg/s).
- ***startup_coeff*** : The coefficients to describe the ramp up phase of the CHP; in the order Intercept, x^1, X^2. Higher order models can be implemented by passing the respective coefficents.
- ***eta*** : Thermal efficiency of the CHP plant.
- ***hv*** : Lower Heating value of the fuel being used in the CHP.
- ***cp***(*optional*) : The specific heat capacity of medium can also be specified, defaults to 4184 J/kgK.

# Structure :
The model consists of three classes : `CHP_State`, `CHPInputs`, `CHP`.

The `init` method of `CHP` creates an object of the `CHPInputs` class, initialized with the passed parameters.  
The `step` method is called by mosaik at each step.  
This method calculated the power output of the CHP plant. The attribute `reglimit` specifies how long it takes (in minutes) for the CHP to reach the nominal power output. The ramp up model with `startup_coeff` is applied only during this time duration.  
The `step` method also calculates the electrical power generated as well as the fuel consumed corresponding to the power output and the step size.
 
`CHP_State` stores the attributes at the end of each step, making it available to shared with other models, or printed to csv.