import pandas as pd
import numpy as np
import json
import pickle

def postprocessing(output_path, input_path, scenario_path):
    
    df = pd.read_csv(output_path, index_col='date')
    df.index = pd.to_datetime(df.index)

    with open(input_path, 'r') as file:
        input_params = json.load(file)
    
    # if power stages are given as int or float, turn them into a list
    input_params['chp']['nom_P_th'] = np.atleast_1d(input_params['chp']['nom_P_th']).tolist()
    input_params['boiler']['nom_P_th'] = np.atleast_1d(input_params['boiler']['nom_P_th']).tolist()
        
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
    }

    with open(scenario_path, "rb") as f:
        scenario = pickle.load(f)


    columnname = {'Power[w]': 'PV_P[W]', 'CSV-0.DNI_0-DNI': 'DNI', 'CSV-1.HEATLOAD_0-T_amb':'T_amb', 'HeatPumpSim-0.HeatPump_0-T_amb' : 'HP_Tamb', 'CSV-1.HEATLOAD_0-Heat Demand [kW]':'Heat Demand [KW]',
        'HeatPumpSim-0.HeatPump_0-Q_Demand' : 'HP_Q_Demand', 'CHPSim-0.CHP_0-Q_Demand':'CHP_Q_Demand',
        'HeatPumpSim-0.HeatPump_0-Q_Supplied' : 'HP_Q_Supplied',
        'HeatPumpSim-0.HeatPump_0-heat_source_T' : 'HP_heat_sourceT',
        'HeatPumpSim-0.HeatPump_0-cons_T' : 'HP_consT',
        'HeatPumpSim-0.HeatPump_0-P_Required': 'HP_P_Required', 'HeatPumpSim-0.HeatPump_0-COP':'HP_COP',
        'HeatPumpSim-0.HeatPump_0-cond_m':'HP_cond_m', 'HeatPumpSim-0.HeatPump_0-cond_in_T':'HP_cond_in_T',
        'HeatPumpSim-0.HeatPump_0-on_fraction':'HP_onfraction', 'HeatPumpSim-0.HeatPump_0-Q_evap' : 'HP_Q_Evap',
        # 'ControllerSim-0.Controller_0-heat_demand':'heat_demand',
        # 'ControllerSim-0.Controller_0-heat_supply':'heat_supply',
        # 'ControllerSim-0.Controller_0-hp_demand':'hp_demand',
        # 'ControllerSim-0.Controller_0-hp_supply':'hp_supply',
        # 'ControllerSim-0.Controller_0-chp_demand':'chp_demand',
        # 'ControllerSim-0.Controller_0-chp_supply':'chp_supply',
        # 'ControllerSim-0.Controller_0-heat_in_F':'heatin_F',
        # 'ControllerSim-0.Controller_0-heat_in_T':'heatin_T',
        # 'ControllerSim-0.Controller_0-heat_out_F':'heatout_F',
        # 'ControllerSim-0.Controller_0-heat_out_T':'heatout_T',
        # 'ControllerSim-0.Controller_0-chp_in_F':'chpin_F',
        # 'ControllerSim-0.Controller_0-chp_in_T':'chpin_T',
        # 'ControllerSim-0.Controller_0-chp_out_F':'chpout_F',
        # 'ControllerSim-0.Controller_0-chp_out_T':'chpout_T',
        # 'ControllerSim-0.Controller_0-hp_out_F':'hpout_F',
        # 'ControllerSim-0.Controller_0-hp_out_T':'hpout_T',
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
        # 'CHPSim-0.CHP_0-nom_P_th':'CHP_nom_Pth', 'CHPSim-0.CHP_0-mdot':'CHP_mdot',
        # 'CHPSim-0.CHP_0-mdot_neg':'CHP_mdot_neg', 'CHPSim-0.CHP_0-temp_in':'CHP_tempin',
        # 'CHPSim-0.CHP_0-temp_out':'CHP_tempout', 'CHPSim-0.CHP_0-P_th':'CHP_Pth', , 'CHPSim-0.CHP_0-P_el' : 'CHP_el',
        # 'EnergyTransformer-0.CHP0-P_el' : 'CHP_el', 'EnergyTransformer-0.CHP0-nom_P_th':'CHP_nom_Pth', 'EnergyTransformer-0.CHP0-mdot':'CHP_mdot',
        # 'EnergyTransformer-0.CHP0-mdot_neg':'CHP_mdot_neg', 'EnergyTransformer-0.CHP0-temp_in':'CHP_tempin',
        # 'EnergyTransformer-0.CHP0-temp_out':'CHP_tempout', 'EnergyTransformer-0.CHP_0-P_th':'CHP_Pth'
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

    columnnew = df.columns
    targetcolumn = np.asarray(list(columnname.values()))

    """ Electricity balance """

    clone_df = df.copy(deep=True)
    clone_df['Household_demand'] = scenario['demand']['electricity']
    producers = {
        'PV': clone_df['pv_gen'],
        'BHKW': clone_df['CHP_P_el']}

    users = {
        'Haushaltstrom': clone_df['Household_demand'],
        'Wärmepumpe': clone_df['HP_P_Required'],
        'Heizstäbe': clone_df['HotWaterTankSim-2.HotWaterTank_0-hr_1.P_th']/0.98  #assuming heating rods efficiency 98, further work later
    }
    users_keys = list(users.keys())
    producers_keys = list(producers.keys())
    elec_links_df = pd.DataFrame({})

    for r in range(len(clone_df)):
        supply = {k: producers[k][r] for k in producers}
        demand = {k: users[k][r] for k in users}

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

        # Any leftover production goes to grid
        for p_key in producers_keys:
            if supply[p_key] > 0:
                elec_links_df.at[r, f'{p_key}:Netz'] = supply[p_key]

    step_size = (df.index[1] - df.index[0]).seconds
    elec_links = {k: [elec_links_df[k].sum() * step_size/3600, 'springgreen'] for k in elec_links_df.columns}
    elec_links_df.index = df.index


    sim_period = (df.index[-1] - df.index[0]).days / 365 # simulation period in years
    dfh = df.resample('H').mean(numeric_only=True)
    elec_links_dfh = elec_links_df.resample('H').mean(numeric_only=True).fillna(0)

    cost['hp']['electricity'] = sum(dfh['HP_P_Required'] * scenario['raw_material']['electricity'])
    cost['hp']['investment'] = 60 * scenario['investment']['hp'] # TODO: here we need a new parameter in input_params.json: hp: nom_P_th
    cost['hp']['maintenance'] = sim_period * scenario['maintenance']['hp']

    cost['chp']['co2_tax'] = sum(dfh['chp_supply']/input_params['chp']['eta']) / (input_params['chp']['hv']*1000) * scenario['co2']['tax']
    cost['chp']['electricity'] = sum(elec_links_dfh['BHKW:Netz'] * scenario['feedin']['chp']) *-1

    cost['chp']['fuel'] = sum((dfh['chp_supply']/input_params['chp']['eta']) * scenario['raw_material']['natural_gas'])
    cost['chp']['investment'] = (input_params['chp']['nom_P_th'][-1]/1000) * scenario['investment']['chp']
    cost['chp']['maintenance'] = sum(scenario['maintenance']['chp'] * dfh['CHP_P_el'])

    cost['boiler']['co2_tax'] = sum(dfh['Boiler_P_th']/input_params['boiler']['eta']) / (input_params['boiler']['hv']*1000) * scenario['co2']['tax']
    cost['boiler']['fuel'] = sum((dfh['Boiler_P_th']/input_params['boiler']['eta']) * scenario['raw_material']['natural_gas'])
    cost['boiler']['investment'] = (input_params['boiler']['nom_P_th'][-1]/1000) * scenario['investment']['boiler']
    cost['boiler']['maintenance'] = sum(scenario['maintenance']['boiler'] * dfh['Boiler_P_th'])

    cost['pipes']['investment'] = scenario['investment']['pipes'][input_params['ctrl']['supply_config']]

    cost['pv']['electricity'] = sum(elec_links_dfh['PV:Netz'])/1000 * scenario['feedin']['pv'] *-1 

    cost['pv']['investment'] = scenario['investment']['pv'] * 50 #TODO: integrate pv config in input_params.json
    cost['pv']['maintenance'] = scenario['maintenance']['pv'] * 50 #TODO: same as above

    cost['transformer']['investment'] = scenario['investment']['transformer'] 

    # co2['boiler']['manufacturing'] = 
    co2['boiler']['operation'] = scenario['co2']['natural_gas'] * sum(dfh['Boiler_P_th']/input_params['boiler']['eta'])

    # co2['chp']['manufacturing'] = 
    co2['chp']['operation'] = scenario['co2']['natural_gas'] * sum(dfh['CHP_P_th']/input_params['chp']['eta'])

    # co2['hp']['manufacturing'] = 
    co2['hp']['operation'] = scenario['co2']['electricity_mix'] * sum(dfh['HP_Q_Supplied']/input_params['chp']['eta'])

    # co2['pv']['manufacturing'] =

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

    return round(sum_numeric(cost), 0), round(sum_numeric(co2), 1)

if __name__ == "__main__":  
   
    post_processing('DES_data.csv', 'input_params.json', 'scenario.pkl') 