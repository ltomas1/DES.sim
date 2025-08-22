import pvlib
import pandas as pd
import numpy as np
import os

def sim(params):
    # module library at https://github.com/pvlib/pvlib-python/blob/main/pvlib/data/sam-library-sandia-modules-2015-6-30.csv
    # local dataset at pvlib/data (see comments of retrieve_sam method for more details!)
    '''
        Standalone pvlib model.
    '''
    params_sample= {
        'calc_mode' : 'simple',
        'nom_power' : None,

    }
    if params['calc_mode'] == 'simple':
        # latitude = params.get('latitude')
        # longitude = params.get('longitude')
        nom_power = params.get('nom_power')
        coordinates = params.get('coordinates')
        data_path = params.get('irradiation_data') #Relative to the main_sim dir

        module_info = ['SandiaMod','SunPower_128_Cell_Module__2009__E__']
        inverter_info = ['cecinverter', 'AEconversion_GMbH__INV500_90US_xxxxx__208V_']
        nSnP = [1,1]
        power_ratio = nom_power/500 #The above config has a Pnom of 500 watts, scaling output according to user requested power.
        
    
    # coordinates = [(49.1, 8.5, 'Stutensee', 110, 'Etc/GMT-1')]

    modules_db = pvlib.pvsystem.retrieve_sam(module_info[0])

    sapm_inverters = pvlib.pvsystem.retrieve_sam(inverter_info[0])

    module = modules_db[module_info[1]] #replace BAD_CHARS = ' -.()[]:+/",' ; with simply _

    inverter = sapm_inverters[inverter_info[1]]

    temperature_model_parameters = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']

    latitude, longitude, name, altitude, timezone = coordinates

    # for loc in coordinates:
    #     latitude, longitude, name, altitude, timezone = loc
    
    # --------------------------npro weather-----------------------------------------
    raw = pd.read_csv(os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', '..', 'data', 'inputs', '2025-04-07-Project1-weather.csv')), 
                      sep=';', index_col='Time', encoding='cp1252')
    # raw = pd.read_csv(os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', data_path)), 
    #                   sep=';', index_col='Time', encoding='cp1252')

    weather = pd.DataFrame({
        'ghi' : raw['Global horizontal irradiance (W/m²)'],
        'dni' : raw['Direct normal irradiance (W/m²)'],
        'dhi' : raw['Horizontal infrared radiation (W/m²)'],
        'temp_air' : raw['Air temperature (°C)'],
        'wind_speed' : raw['Wind speed (m/s)']
    })

    
    weather.index = pd.to_datetime(raw.index, format = "%d.%m. %H:%M")
    weather.index = weather.index.tz_localize(timezone)
    weather.index.name=None

    weather.index = weather.index.map(lambda x:x.replace(year = 2022))

    weather = weather.resample('15min').interpolate(method='linear')
    

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
        modules_per_string=nSnP[0],
        strings=nSnP[1]
    )

    system = PVSystem(arrays=[array], inverter_parameters=inverter)
    mc = ModelChain(system, location)
    mc.run_model(weather)
    annual_energy = mc.results.ac.sum() * power_ratio # I believe this is no longer used, could remove it.
    energies[name] = annual_energy

    weather['Power[w]'] = mc.results.ac * power_ratio

    weather.index = weather.index.tz_localize(None)
    weather.to_csv('PVlib_output.csv')
    print('PVlib simulation finished!')

if __name__ == "__main__":   
    sim()

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