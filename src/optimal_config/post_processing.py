import pandas as pd
import numpy as np
import json
import pickle

def postprocessing(sim_data, input_params, scenario):
    
    timestamps = list(sim_data['CSV-1.HEATLOAD_0']['Timestamp'].values())
    df = pd.DataFrame(index=pd.to_datetime(timestamps))
    df.index = pd.to_datetime(df.index)
    new_cols = {}

    for sim, headers in sim_data.items():
        for h, v in headers.items():
            vals = list(v.values())
            if all(isinstance(x, (int, float)) for x in vals):
                col_name = f"{sim}-{h}"
                new_cols[col_name] = vals

    df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
        
    # calculate costs
    """here I have to account for all investment and operational costs

        HP: investment, maintenance, electricity (from grid)
        chp: investment, maintenance, fuel, co2 tax, electricity negative (sold)
        boiler: investment, maintenance, fuel, co2 tax
        pv: investment, maintenance, electricity negative (sold)
        pipes: investment, maintenance
        """

    cost = {
        'hp':{
            'investment': 0,
            'maintenance': 0,
            'electricity':0, 
        }, 
        'chp':{
            'investment': 0,
            'maintenance': 0,
            'electricity': 0,
            'fuel': 0,
            'co2_tax': 0,
        },
        'boiler':{
            'investment': 0,
            'maintenance': 0,
            'fuel': 0,
            'co2_tax': 0,
        },
        'pv':{
            'investment': 0,
            'maintenance':0,
            'electricity': 0,
        }, 
        'pipes':{
            'investment': 0,
            'maintenance': 0,
        },
        'transformer':{
            'investment': 0,
            #? 'maintenance': 0, vernachlässigbar?
        },
    }

    # calculate CO2 emissions
    """here I have to account for all CO2 emissions for the entire lifecycle

        HP: manufacturing, operation (electricity mix)
        chp: manufacturing, operation (fuel), #? operation negative (electricity produced)??? 
        boiler: manufacturing, operation (fuel)
        pv: manufacturing, #? operation negative (electricity produced)
        pipes: manufacturing
        
        """

    co2 = {
        'hp':{
            'manufacturing': 0,
            'operation': 0,
        }, 
        'chp':{
            'manufacturing': 0,
            'operation': 0,
        },
        'boiler':{
            'manufacturing': 0,
            'operation': 0,
        },
        'pv':{
            'manufacturing': 0,
        }, 
        'pipes':{
            'manufacturing': 0,
            'operation': 0,
        },
        'households':{
            'electricity': 0,
        }
    }

    columnname = {'Power[w]': 'PV_P[W]', 'CSV-0.DNI_0-DNI': 'DNI', 'CSV-1.HEATLOAD_0-T_amb':'T_amb', 'HeatPumpSim-0.HeatPump_0-T_amb' : 'HP_Tamb', 'CSV-1.HEATLOAD_0-Heat Demand [kW]':'Heat Demand [KW]',
        'HeatPumpSim-0.HeatPump_0-Q_Demand' : 'HP_Q_Demand', 'CHPSim-0.CHP_0-Q_Demand':'CHP_Q_Demand',
        'HeatPumpSim-0.HeatPump_0-Q_Supplied' : 'HP_Q_Supplied',
        'HeatPumpSim-0.HeatPump_0-heat_source_T' : 'HP_heat_sourceT',
        'HeatPumpSim-0.HeatPump_0-cons_T' : 'HP_consT',
        'HeatPumpSim-0.HeatPump_0-P_Required': 'HP_P_Required', 'HeatPumpSim-0.HeatPump_0-COP':'HP_COP',
        'HeatPumpSim-0.HeatPump_0-cond_m':'HP_cond_m', 'HeatPumpSim-0.HeatPump_0-cond_in_T':'HP_cond_in_T',
        'HeatPumpSim-0.HeatPump_0-on_fraction':'HP_onfraction', 'HeatPumpSim-0.HeatPump_0-Q_evap' : 'HP_Q_Evap',
        'HotWaterTankSim-0.HotWaterTank_0-sensor_00.T':'HWTSim0_sensor0_T',
        'HotWaterTankSim-1.HotWaterTank_0-sensor_00.T':'HWTSim1_sensor0_T',
        'HotWaterTankSim-2.HotWaterTank_0-sensor_00.T':'HWTSim2_sensor0_T',
        'HotWaterTankSim-0.HotWaterTank_0-sensor_01.T':'HWTSim0_sensor1_T',
        'HotWaterTankSim-1.HotWaterTank_0-sensor_01.T':'HWTSim1_sensor1_T',
        'HotWaterTankSim-2.HotWaterTank_0-sensor_01.T':'HWTSim2_sensor1_T',
        'HotWaterTankSim-0.HotWaterTank_0-sensor_02.T':'HWTSim0_sensor2_T',
        'HotWaterTankSim-1.HotWaterTank_0-sensor_02.T':'HWTSim1_sensor2_T',
        'HotWaterTankSim-2.HotWaterTank_0-sensor_02.T':'HWTSim2_sensor2_T',
        'HotWaterTankSim-0.HotWaterTank_0-heat_out.T':'HWTSim0_heatout_T',
        'HotWaterTankSim-1.HotWaterTank_0-heat_out.T':'HWTSim1_heatout_T',
        'HotWaterTankSim-2.HotWaterTank_0-heat_out.T':'HWTSim2_heatout_T',
        'HotWaterTankSim-0.HotWaterTank_0-heat_out.F':'HWTSim0_heatout_F',
        'HotWaterTankSim-1.HotWaterTank_0-heat_out.F':'HWTSim1_heatout_F',
        'HotWaterTankSim-2.HotWaterTank_0-heat_out.F':'HWTSim2_heatout_F',
        'HotWaterTankSim-0.HotWaterTank_0-hp_in.T':'HWTSim0_hp_in_T',
        'HotWaterTankSim-1.HotWaterTank_0-hp_in.T':'HWTSim1_hp_in_T',
        'HotWaterTankSim-2.HotWaterTank_0-hp_in.T':'HWTSim2_hp_in_T',
        'HotWaterTankSim-0.HotWaterTank_0-hp_in.F':'HWTSim0_hp_in_F',
        'HotWaterTankSim-1.HotWaterTank_0-hp_in.F':'HWTSim1_hp_in_F',
        'HotWaterTankSim-2.HotWaterTank_0-hp_in.F':'HWTSim2_hp_in_F',
        'HotWaterTankSim-0.HotWaterTank_0-hp_out.T':'HWTSim0_hp_out_T',
        'HotWaterTankSim-1.HotWaterTank_0-hp_out.T':'HWTSim1_hp_out_T',
        'HotWaterTankSim-2.HotWaterTank_0-hp_out.T':'HWTSim2_hp_out_T',
        'HotWaterTankSim-0.HotWaterTank_0-hp_out.F':'HWTSim0_hp_out_F',
        'HotWaterTankSim-1.HotWaterTank_0-hp_out.F':'HWTSim1_hp_out_F',
        'HotWaterTankSim-2.HotWaterTank_0-hp_out.F':'HWTSim2_hp_out_F',
        'HotWaterTankSim-0.HotWaterTank_0-heat_in.T':'HWTSim0_heatin_T',
        'HotWaterTankSim-1.HotWaterTank_0-heat_in.T':'HWTSim1_heatin_T',
        'HotWaterTankSim-2.HotWaterTank_0-heat_in.T':'HWTSim2_heatin_T',
        'HotWaterTankSim-0.HotWaterTank_0-heat_in.F':'HWTSim0_heatin_F',
        'HotWaterTankSim-1.HotWaterTank_0-heat_in.F':'HWTSim1_heatin_F',
        'HotWaterTankSim-2.HotWaterTank_0-heat_in.F':'HWTSim2_heatin_F',
        'HotWaterTankSim-0.HotWaterTank_0-T_mean':'HWTSim0_Tmean',
        'HotWaterTankSim-1.HotWaterTank_0-T_mean':'HWTSim1_Tmean',
        'HotWaterTankSim-2.HotWaterTank_0-T_mean':'HWTSim2_Tmean', 'CHPSim-0.CHP_0-eff_el':'CHP_eff',
        }

    boiler_columns = [i for i in df.columns if 'Boiler' in i]
    boiler_translations = {c : 'Boiler_' + c.rsplit('-', 1)[1] for c in boiler_columns}

    chp_columns = [i for i in df.columns if 'CHP' in i] # TODO read eidprefix from chp params!
    chp_translations = {c : 'CHP_' + c.rsplit('-', 1)[1] for c in chp_columns}

    controller_columns = [i for i in df.columns if 'Controller' in i] 
    controller_translations = {c : c.rsplit('-', 1)[1] for c in controller_columns}

    columnname.update(boiler_translations)
    columnname.update(chp_translations)
    columnname.update(controller_translations)

    oldcolumns = df.columns
    column_translate = np.asarray(list(columnname.keys()))

    n = np.setdiff1d(oldcolumns,column_translate)  
    # print(f'translation not defined for :\n {n}') 

    df.rename(columns = columnname, inplace = True)
    # print(f'{len(df.columns)-len(columnname.keys())} columns were not translated!')

    """ Electricity balance """

    clone_df = df.copy(deep=True)
    clone_df['Household_demand'] = scenario['demand']['electricity']
    producers = {
        'PV': clone_df['pv_gen'],
        'BHKW': clone_df['CHP_P_el']}

    users = {
        'Haushaltsstrom': clone_df['Household_demand'],
        'Wärmepumpe': clone_df['HP_P_Required'],
        'Heizstäbe': clone_df['hwt2_hr_1']/0.98  #assuming heating rods efficiency 98
        # TODO: collect tank variables  in main_sim.py -> consider heating rods
    }
    users_keys = list(users.keys())
    producers_keys = list(producers.keys())
    # elec_links_df = pd.DataFrame(columns=[f'Netz:{u_key}' for u_key in users_keys] + [f'{p_key}:Netz' for p_key in producers_keys])
    elec_links_df = pd.DataFrame({})
    
    for r in range(len(clone_df)):
        supply = {k: producers[k].iloc[r] for k in producers}
        demand = {k: users[k].iloc[r] for k in users}

        for u_key in users_keys:
            for p_key in producers_keys:
                if demand[u_key] == 0:
                    continue
                if supply[p_key] == 0:
                    continue

                flow = min(demand[u_key], supply[p_key])
                col_name = f'{p_key}:{u_key}'
                if col_name not in elec_links_df.columns:
                    elec_links_df[col_name] = [None] * len(clone_df)
                
                elec_links_df.at[r, f'{p_key}:{u_key}'] = flow

                supply[p_key] -= flow
                demand[u_key] -= flow

            # If unmet demand remains, take from grid
            if demand[u_key] > 0:
                elec_links_df.at[r, f'Netz:{u_key}'] = demand[u_key]
            else:
                elec_links_df.at[r, f'Netz:{u_key}'] = float(0)

        # Any leftover production goes to grid
        for p_key in producers_keys:
            if supply[p_key] > 0:
                elec_links_df.at[r, f'{p_key}:Netz'] = supply[p_key]
            else:
                elec_links_df.at[r, f'{p_key}:Netz'] = float(0)

    step_size = (df.index[1] - df.index[0]).seconds
    elec_links = {k: [elec_links_df[k].sum() * step_size/3600, 'springgreen'] for k in elec_links_df.columns}
    elec_links_df.index = df.index


    sim_period = (df.index[-1] - df.index[0]).days / 365 # simulation period in years
    am_period = 25 # amortization period in years
    dfh = df.resample('h').mean(numeric_only=True).fillna(0)
    elec_links_dfh = elec_links_df.resample('h').mean(numeric_only=True).fillna(0)
    # #--------------------------------------------- annuity method -------------------------------------------------------------------------------------
    # """calculation of economic efficiency using the annuity method of VDI 2067"""

    # "capital-related costs"
    # A_0 = -999 # investment amount 
    # A_1_n = np.zeros(T-1) # cash value of the first, second, ..., nth procured replacement

    # for n in range(len(A_1_n)):
    #     n = n+1
    #     A_1_n[n-1] = A_0 * (r**(n*T_N))/(q**(n*T_N))

    # T_N = -999 # service life (in years) of the installation component 
    # T = 25 # observation period
    # q = -999 # interest factor
    # r = -999 # price range factor
    # n = -999# number of replacements procured within the observation period

    # R_W = A_0 * r**(n*T_N) * ((n+1)*T_N-T)/(T_N) * (1/q**T) # residual value (A_0 * price at time of purchase * straight-line depriciation * discounted to beginning)
    # # kann man evtl. streichen
    # a = (q-1) / (1-q**-T) # annuity factor 
    # b = (1-(r/q)**T) / (q-r) # price dynamic cash value factor 

    # A_NK = (A_0 + A_1_n.sum() - R_W) * a # annuity of the capital related costs

    # "demand-related costs"
    # A_V1 = -999 # demand-related costs in the first year 
    # b_V = -999 # price dynamic cash value factor for demand-related costs 

    # #TODO calculate from energy timeseries A_V1 = ...
    # A_V1 = (elec_links_dfh['Netz:Haushaltsstrom'] + elec_links_dfh['Netz:Wärmepumpe']) * scenario['raw_material']['electricity']

    # A_NV = A_V1 * a * b_V # annuity of the demand-related costs 

    # "operation-related costs"
    # A_B1 = -999 # operation-related costs in first year for actual operation 
    # b_B = -999 # price dynamic cash value factor for operation-related costs 
    # b_IN = -999 # price dynamic cash value factor for maintenance 
    # f_WInsp= -999 # factor for servicing and inspection effort 
    # f_Inst = -999 # factor for servicing and inspection effort 

    # A_NB = A_B1 * a * b_B + A_IN * a * b_IN # annuity of the operation-related costs 
    # A_IN = A_0 * (f_Inst + f_WInsp) # operation-related costs in first year for maintenance

    # "other costs" 
    # A_S1 = -999 # other costs in the first year 
    # b_S = -999 # price dynamic cash value factor for other costs 

    # A_NS = A_S1 * a * b_S  # annuity of other costs 

    # "proceeds" 
    # E_1 = -999 # proceeds in the first year 
    # b_E = -999 # price dynamic cash value factor for proceeds 

    # A_NE = E_1 * a * b_E # annuity of the proceeds 

    # # annuity of total annual payments 
    # A_N = A_NE - (A_NK + A_NV + A_NB + A_NS)

    #--------------------------------------------- allocate costs -------------------------------------------------------------------------------------
    cost['hp']['electricity'] = sum(dfh['HP_P_Required'] * scenario['raw_material']['electricity'])
    cost['hp']['investment'] = float(input_params['hp']['hp_model'][4:6]) * scenario['investment']['hp'] / am_period # TODO: here we need a new parameter in input_params.json: hp: nom_P_th
    cost['hp']['maintenance'] = sim_period * scenario['maintenance']['hp']

    cost['chp']['co2_tax'] = sum(dfh['generators.chp_supply']/input_params['params_chp']['efficiency']) / (input_params['params_chp']['heating_value']*1000) * scenario['co2']['tax']
    cost['chp']['electricity'] = sum(elec_links_dfh['BHKW:Netz'] * scenario['feedin']['chp']) *-1

    cost['chp']['fuel'] = sum((dfh['generators.chp_supply']/input_params['params_chp']['efficiency']) * scenario['raw_material']['natural_gas'])
    cost['chp']['investment'] = (input_params['params_chp']['heat_out'][-1]/1000) * scenario['investment']['chp'] / am_period
    cost['chp']['maintenance'] = sum(scenario['maintenance']['chp'] * dfh['CHP_P_el'])

    cost['boiler']['co2_tax'] = sum(dfh['Boiler_P_th']/input_params['params_boiler']['efficiency']) / (input_params['params_boiler']['heating_value']*1000) * scenario['co2']['tax']
    cost['boiler']['fuel'] = sum((dfh['Boiler_P_th']/input_params['params_boiler']['efficiency']) * scenario['raw_material']['natural_gas'])
    cost['boiler']['investment'] = (input_params['params_boiler']['heat_out'][-1]/1000) * scenario['investment']['boiler'] / am_period
    cost['boiler']['maintenance'] = scenario['maintenance']['boiler'] * sim_period

    cost['pipes']['investment'] = scenario['investment']['pipes'][input_params['ctrl']['supply_config']] / am_period

    cost['pv']['electricity'] = sum(elec_links_dfh['PV:Netz'])/1000 * scenario['feedin']['pv'] *-1 

    cost['pv']['investment'] = (scenario['investment']['pv'] * input_params['pv']['nom_power']/1000) / am_period
    cost['pv']['maintenance'] = (scenario['maintenance']['pv'] * input_params['pv']['nom_power']/1000) / am_period

    cost['transformer']['investment'] = scenario['investment']['transformer'] / am_period

    #--------------------------------------------- allocate CO2 -------------------------------------------------------------------------------------
    # co2['boiler']['manufacturing'] = 
    co2['boiler']['operation'] = scenario['co2']['natural_gas'] * sum(dfh['Boiler_P_th']/input_params['params_boiler']['efficiency'])

    # co2['chp']['manufacturing'] = 
    co2['chp']['operation'] = scenario['co2']['natural_gas'] * sum(dfh['CHP_P_th']/input_params['params_chp']['efficiency'])

    # co2['hp']['manufacturing'] = 
    co2['hp']['operation'] = scenario['co2']['electricity_mix'] * sum(elec_links_dfh['Netz:Wärmepumpe'])

    # co2['pv']['manufacturing'] =
    co2['households']['electricity'] = scenario['co2']['electricity_mix'] * sum(elec_links_dfh['Netz:Haushaltsstrom'])
    # co2['pipes']['manufacturing'] =  
    #? co2['pipes']['operation'] =  simulate pumps for disctrict heating system?

    def sum_numeric(d):
        total = 0
        if isinstance(d, dict):  # if it's a dict, go deeper
            for v in d.values():
                total += sum_numeric(v)
        elif isinstance(d, list):  # if it's a list, iterate
            for v in d:
                total += sum_numeric(v)
        elif isinstance(d, (int, float)):  # if it's a number, add it
            total += d
        # ignore other types (str, bool, None, etc.)
        return total

    return round(sum_numeric(cost), 0), round(sum_numeric(co2), 1), dfh['IdealHrodsum'].sum()

if __name__ == "__main__":  
    
    from pathlib import Path
    import sys
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))  # so 'src' is importable
    from src.main_sim import run_DES

    with open('../../data/inputs/input_params.json', 'r') as file:
        input_params = json.load(file)

    with open('../../data/inputs/scenario.pkl', "rb") as f:
            scenario = pickle.load(f)

    sim_data = run_DES(input_params, collect=True)
    cost, co2, aux_heat = postprocessing(sim_data, input_params, scenario) 
    print(f"Cost: {cost} €")
    print(f"CO2 emissions: {co2} tons CO2")
    print(f"Auxiliary heat: {aux_heat} kWh")
