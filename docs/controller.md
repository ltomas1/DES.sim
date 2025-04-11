# Controller DES model

The controller builds on top of the basic mosaik controller model.
The controller is responsible for the deciding the operation of the Heat pump, Combined heat and power plant, Gas boiler and the inbuilt heating rods.
The controller is also responsible for balancing the mass flow rates between the three storage tanks.

## Calculating heat supply
Based on the required heating, the mass flow rate of the hot water outlet is calculated.

## Mass balancing
The controller is also responsible for balancing mass flows between the storage tanks.  
*In the current configuration : *  
Return line from Network is connected to the first tank, as well as the inflow to the heat pump. The difference between this dictates the flow between the first and second tank. This flow could be in either direction, depending on the heat demand, i.e the flow rate of the Network return line.  
The second tank recieves the hot water from the Heat pump, this along with the balancing flow between first and second tanks, dictates the flow into the third tank.  
The third tank recieves flow from the CHP and the gas boiler, both of which form a closed loop with the third tank.  


![Storage Schematic](Storage_scheme.png)


## Controller Logic - Heating mode
### Heat Pump

The heat pump has two operation modes based on the season, *summer* and *winter*. The heat pump operation is further classified into *daytime* and *nighttime* operation. 
The heat pump is also operated in a surplus mode, when the electricity generation from PV and CHP exceeds the predicted electricity demand.

### CHP and Gas Boiler
The CHP is turned on when the top layer of the third storage tank is below the upper setpoint temperature, this setpoint temperature takes in to consideration a small buffer over the minimum hot water supply requirement temperature . The CHP continues running until the bottom layer of the third tank is above the setpoint temperature as well. 
The Gas boiler operates with a similar logic, but turning on only when the temperature remains below the setpoint for more than *10 mins* **(dt)**. 
Then the gas boiler runs in conjuction with the CHP until the bottom layer of the third tanks is above the upper threshold temperature.
 

![Flowchart](<Controller logic.png>)


