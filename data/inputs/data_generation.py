# -*- coding: utf-8 -*-
"""
Created on Mon Jun  3 13:00:24 2024

@author: leroytomas
"""

import pandas as pd
import matplotlib.pyplot as plt
import os 

# Set directory
Path = os.getcwd()
path = Path.replace(os.sep, '/')

#%%

file = 'Polysun_raw.csv'

df = pd.read_csv(file, sep=';', index_col='Datum', encoding='iso8859_2')
df = df.replace(',', '', regex=True)
df.index = pd.date_range(start='01.01.2022 00:00', end='31.12.2022 23:45', freq='15min')


#%%


rename_dict = {
    'Wetterdaten: Mittlere Aussentemperatur [°C] (Tamb)': 'T_amb',
    'Gebäude Space heating: demand 443 Mhw: Heizwärmebedarf [W] (Qdem)': 'Heat Demand SH [W]',
    'Gebäude Space heating: demand 443 Mhw: Soll-Raumtemperatur [°C]': 'T_room_set',
    'Elektrische Verbraucher Elec. Demand: 425 MWh: Elektrischer Verbrauch [W] (Ecs)': 'Electricity Demand [W]',
    'Wetterdaten: Normale Direktstrahlung  [W/m˛] (Bn)': 'DNI',
    'Wetterdaten: Diffusstrahlung, Jahressumme [W/m˛] (Dh)': 'diffuse_radiation',
    'Wetterdaten: Globalstrahlung, Jahressumme [W/m˛] (Gh)': 'global_radiation',
    'Warmwasserbedarf 343 MWh: Domestic hot water: Energiebedarf [W] (Qdem)': 'Heat Demand DHW [W]',
    'Wetterdaten: Windgeschwindigkeit [m/s] (Vwnd)': 'wind_speed'
}

# Subset and rename columns
df_mosaik = df.copy()
df_mosaik.columns = df_mosaik.columns.to_series().map(rename_dict)
df_mosaik = df_mosaik.loc[:, df_mosaik.columns.notna()] # delete all columns with nan headers
df_mosaik.DNI = pd.to_numeric(df_mosaik.DNI)

df_mosaik.head()