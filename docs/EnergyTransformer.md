# Transformer_base
This class provides the basic functionality of an energy transformer. This involves determining either the temperature or the mass flow rate at the outlet of the transformer.

# Parameters

- ***heat_out_caps*** : A list or array of the possible power stages.
- ***nom_P_th*** : Nominal heat output of the transformer.
- ***op_stages*** : Possible part-operation stages of the transformer.
- ***[cp]*** : The specific heat capacity of medium, defaults to 4184 J/kgK.
- ***set_temp*** : Setpoint temperature.
- ***set_flow*** : Setpoint flow.
- ***nom_eta*** : Fuel efficiency.
- ***heat_value*** : Heating value of fuel.

Both the setpoint temperature and mass flow rate should not be provided.

# Working
* Based on provided demand, an appropriate power level is selected from `heat_out_caps`. 
* If a setpoint temperature is specified, the flow rate for the corresponding power is determing, and vice-versa if setpoint flow rate is specified.
* With the provided efficiency, the fuel consumption is also calculated.
