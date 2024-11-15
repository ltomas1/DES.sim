This is a simulation model for a heat pump energy central with a CHP and two TES based on the mosaik library. 

The CHP model was written by me, all other models are mosaik.components models. 

heat pump model:
Parametrized using the "Air_60kW" model in COP_m_data.csv.

TES model:
hotwatertank model in mosaik.components

CHP model:
Modelled using an energy balance and assuming a constant thermal power, electrical efficiency and mass flow. 
(disconnected in this version)

controller:
*updated controller model based on mosaik.components.controller*

PV model:
pv model in mosaik_components.pv.pvsimulator

