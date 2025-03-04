# Gas Boiler
The CHP model builds on top of the mosaik heat pump model. The base file *chp_mosaik.py* handles the scheduling and contains the other required mosaik methods.  
*gasboiler_model.py* details the functioning of the chp model.

# Parameters
The gas boiler model accepts 5 parameters.
~~~python
params_boiler = {'eta' : 0.98, 'hv' : HV, 
                 'nom_P_th' : [0, 74000, 148000, 222000, 296000, 370000], #Operating points of boiler, in W
                 'Set_Temp' : 75
                     }
~~~

- ***eta*** : Thermal efficiency of the CHP plant.
- ***hv*** : Lower Heating value of the fuel being used in the CHP.
- ***cp***(*optional*) : The specific heat capacity of medium can also be specified, defaults to 4184 J/kgK.
- ***nom_P_th*** : The power output of the gas boiler in Watts.
- ***Set_Temp*** : The setpoint temperature of the boiler output (in degree C).

# Working
The gas boiler recieves the power demand from the controller, and accordingly selects an operationg point from `nom_P_th`. Accordingly the mass flow rate is calculated. The instantaneous fuel consumption is also calculated as per the provided fuel heating value.
~~~python
self.inputs.mdot = self.P_th/((self.temp_out - self.inputs.temp_in) * self.cp)
self.fuel_m3 = (self.P_th*(self.inputs.step_size/3600))/(self.inputs.fuel_eta * self.inputs.heat_value)
~~~

