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

file = 'scenario_data_year.csv'

df_long = pd.read_csv(file, sep=',', skiprows=1, index_col='Time')
df_long.index = pd.to_datetime(df_long.index)

# df_long = df.reindex(pd.date_range(start='2022-01-01', end='2023-01-01', freq='15T'))

# df_long.fillna(method='ffill', inplace=True)
# df_long = df_long.iloc[:-1]

#%%

file_weather = '2022_weather.csv'

weather = pd.read_csv(file_weather, sep=';', index_col='timestamp')
weather.index = pd.to_datetime(weather.index)

#%%

file_sh = 'space_heating.csv'

df_sh = pd.read_csv(file_sh, sep=',')
df_sh['SH [W]'] = df_sh['SH [W]']/1000 # convert W in kW
df_sh.rename(columns={'SH [W]':'SH Demand [kW]'}, inplace=True)
df_sh.index = pd.date_range(start='2022-01-01', end='2022-12-31 23:45', freq='15T')

#%%

file_dhw = 'dhw.csv'

df_dhw = pd.read_csv(file_dhw, sep=';', index_col='seconds')
df_dhw.index = pd.date_range(start='2022-01-01', end='2022-12-31 23:45', freq='H')
df_dhw = df_dhw.resample('15T').asfreq().interpolate()/4 # converts hourly values of l/h into 15 min values of l/h, yearly consumption sum stays the same

df_dhw.rename(columns={'dhw':'DHW Demand [L]'}, inplace=True)

#%%

file_polysun = 'Polysun.csv'

df_poly = pd.read_csv(file_polysun, sep=',', index_col='Time', skiprows=1)
df_poly.index = df_long.index

df_poly.rename(columns={'Energiebedarf thermisch [W]':'Heat Demand [W]'}, inplace=True)

#%% paste all data into df_long 

df_long.T_amb = weather['air_temperature']
# df_long['DHW Demand [L]'] = df_dhw['DHW Demand [L]']*2
# df_long['DHW Demand [L]'] = df_long['DHW Demand [L]'].ffill()
# df_long['SH Demand [kW]'] = df_sh['SH Demand [kW]']
# df_long['CHP Demand [kW]'] = df_sh['SH Demand [kW]']
df_long['Heat Demand [kW]'] = df_poly['Heat Demand [W]']/(1000*4)

df_long = df_long[['Heat Demand [kW]', 'T_amb']]
df_long['null'] = 0

#%%

# df_long['DHW Demand [L]_0'] = 0
# df_long['dhw_in_T_0'] = 0

# df_long['SH Demand [kW]_0'] = 0
# df_long['CHP Demand [kW]_0'] = 0

