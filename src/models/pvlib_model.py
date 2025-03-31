import pvlib
import pandas as pd
import numpy as np
import os

def sim():
    # module library at https://github.com/pvlib/pvlib-python/blob/main/pvlib/data/sam-library-sandia-modules-2015-6-30.csv
    # local dataset at pvlib/data (see comments of retrieve_sam method for more details!)
    
    coordinates = [(49.1, 8.5, 'Stutensee', 110, 'Etc/GMT-1')]

    modules_db = pvlib.pvsystem.retrieve_sam('SandiaMod')

    sapm_inverters = pvlib.pvsystem.retrieve_sam('cecinverter')

    module = modules_db['SunPower_128_Cell_Module__2009__E__'] #replace BAD_CHARS = ' -.()[]:+/",' ; with simply _

    inverter = sapm_inverters['Advanced_Energy_Industries__AE_1000NX__3159700_XXXX_']

    temperature_model_parameters = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']

    # df, metadata = pvlib.iotools.read_tmy3(r"C:\INES\GitHub\des_sim\data\inputs\Braunschweig_meteodata_2022_15min.csv")
    raw = pd.read_csv(os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', '..', 'data', 'inputs', 'Braunschweig_meteodata_2022_15min.csv'))
                      , sep = ',', skiprows = 1, index_col=0)

    for loc in coordinates:
        latitude, longitude, name, altitude, timezone = loc

    weather = pd.DataFrame({
        'ghi' : raw['GlobalRadiation'],
        'dni' : raw['DirectNormalRad'],
        'dhi' : raw['DiffRadiation'],
        'temp_air' : raw['AirTemperature'],
        'wind_speed' : raw['WindSpeed']
    })
    weather.index = pd.to_datetime(raw.index)
    weather.index = weather.index.tz_localize(timezone)
    weather.index.name=None


    from pvlib.pvsystem import PVSystem, Array, FixedMount
    from pvlib.modelchain import ModelChain
    from pvlib.location import Location



    location = Location(
            latitude,
            longitude,
            name=name,
            altitude=altitude,
            tz=timezone,

        )

    energies = {}
    mount = FixedMount(surface_tilt=latitude, surface_azimuth=180)

    array = Array(
        mount=mount,
        module_parameters=module,
        temperature_model_parameters=temperature_model_parameters,
        modules_per_string=20,
        strings=7
    )

    system = PVSystem(arrays=[array], inverter_parameters=inverter)
    mc = ModelChain(system, location)
    mc.run_model(weather)
    annual_energy = mc.results.ac.sum()
    energies[name] = annual_energy

    weather['Power[w]'] = mc.results.ac

    weather.to_csv('PVlib_output.csv')
    print('PVlib simulation finished!')

# sim()

# %%
def _normalize_sam_product_names(names):
    '''
    Replace special characters within the product names to make them more
    suitable for use as Dataframe column names.
    '''
    # Contributed by Anton Driesse (@adriesse), PV Performance Labs. July, 2019
    BAD_CHARS = ' -.()[]:+/",'
    GOOD_CHARS = '____________'

    mapping = str.maketrans(BAD_CHARS, GOOD_CHARS)
    names = pd.Series(data=names)
    norm_names = names.str.translate(mapping)
    return norm_names