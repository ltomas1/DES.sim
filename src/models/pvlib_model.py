import pvlib
import pandas as pd
import numpy as np

def sim():
    coordinates = [(49.1, 8.5, 'Stutensee', 110, 'Etc/GMT-1')]

    sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')

    sapm_inverters = pvlib.pvsystem.retrieve_sam('cecinverter')

    module = sandia_modules['Canadian_Solar_CS5P_220M___2009_']

    inverter = sapm_inverters['ABB__MICRO_0_25_I_OUTD_US_208__208V_']

    temperature_model_parameters = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']

    # df, metadata = pvlib.iotools.read_tmy3(r"C:\INES\GitHub\des_sim\data\inputs\Braunschweig_meteodata_2022_15min.csv")
    raw = pd.read_csv(r'C:\INES\GitHub\des_sim\data\inputs\Braunschweig_meteodata_2022_15min.csv', sep = ',', skiprows = 1, index_col=0)

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

    )

    system = PVSystem(arrays=[array], inverter_parameters=inverter)
    mc = ModelChain(system, location)
    mc.run_model(weather)
    annual_energy = mc.results.ac.sum()
    energies[name] = annual_energy

    weather['Power[w]'] = mc.results.ac

    weather.to_csv('PVlib_output.csv')
    print('PVlib simulation finished!')