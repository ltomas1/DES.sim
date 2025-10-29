# CHP
This model inherits from the `Transformer_base` class. 
# Parameters
- ***elec_share*** : (float)The ratio of electric power generation to thermal power generation.

# Structure
There are two classes : `CHP` and `TransformerSimulator`.
## CHP
This class is a child of the `Gboiler` class.
The electricity generation is defined here simply as a ratio of the thermal power generation.
## TransformerSimulator
A child class of `mosaik_api.Simulator` class. Contains the methods requried by mosaik.  

# Structure
![Structure](images/chp_uml.png)