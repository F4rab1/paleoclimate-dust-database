#!/usr/bin/env python
# coding: utf-8

# In[1]:


# Python workflow to organize the Dust Deposition Database (D3) version 1

# Author: Samuel Albani

# History:
# First created: 13/04/2021
#  ...


# In[2]:


# Import a few libraries

import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
import pandas as pd
from tqdm import tqdm
import csv
import more_itertools

from matplotlib.collections import PatchCollection
from matplotlib.patches import Rectangle
import matplotlib.gridspec as gridspec
import seaborn as sns

#import xarray as xr
import cartopy.crs as crs
import cartopy.feature as cfeature


# In[3]:


# Define a few constants (and their relative uncertainties where appropriate)

# Decay constant of 230Th
marine_lambda230 = 0.009170554
marine_lambda230_RE = 0.11/75.584 # assumed to be the same as RE of Half-life of 230Th (ka)

# Production rate of Th230 from U234 [dpm/m3/a] from Kienast et al. 2016
marine_beta230 = 0.0255529
marine_beta230_RE = 0.0005 / marine_beta230

# Activity of Th230 per gram [dpm/g] from Kienast et al. 2016
ATh230tomass = 246186
ATh230tomass_RE = 0.

# Th232 in dust (ppb)
Th232todust = 13 * 1e-6
Th232todust_RE = 3 / 10.7 #(Th232todust/1e-6)

# ...


# ...


# In[4]:


# Define a few short names for identifying columns

# GENERAL

Atop = 'Age top [ka B.P.]'
AtopRE = 'Age top R.E. [frac., 2σ]'
Abot = 'Age bottom [ka B.P.]'
AbotRE = 'Age bottom R.E. [frac., 2σ]'
Ac = 'Age center [ka B.P.]'
AcRE= 'Age center R.E. [frac., 2σ]'

Dtop = 'Depth top [m]'
Dbot = 'Depth bottom [m]'
Dc = 'Depth center [m]'


# MARINE SEDIMENTS

Th230 = 'ATh230 [dpm/g]'
Th230re = 'ATh230 R.E. [frac., 2σ]'
Th232 = 'ATh232 [dpm/g]'
Th232re = 'ATh232 R.E. [frac., 2σ]'
U234 = 'AU234 [dpm/g]'               # in fact, A234U is not used for calculations!
U234re = 'AU234 R.E. [frac., 2σ]'    # in fact, A234U is not used for calculations!
U238 = 'AU238 [dpm/g]'
U238re = 'AU238 R.E. [frac., 2σ]'

Th230lith = 'ATh230 (lith) [dpm/g]'
Th230lithRE = 'ATh230 (lith) R.E. [frac., 2σ]'
U238auth = 'AU238 (auth) [dpm/g]'
U238authRE = 'AU238 (auth) R.E. [frac., 2σ]'
Th230auth = 'ATh230 (auth) [dpm/g]'
Th230authRE = 'ATh230 (auth) R.E. [frac., 2σ]'
Th230xs = 'Th230xs [dpm/g]'
Th230xsRE = 'Th230xs R.E. [frac., 2σ]'
Th230xs0 = 'Th230xs0 [dpm/g]'
Th230xs0RE = 'Th230xs0 R.E. [frac., 2σ]'
SBMAR = 'SBMAR [g/m2/a]'
SBMARRE = 'SBMAR R.E. [frac., 2σ]'
Th232mr = 'Th232 [g/g]'
Th232mrRE = 'Th232 R.E. [frac., 2σ]'
EC = 'EC [g/g]'
ECRE = 'EC R.E. [frac., 2σ]'
DMAR = 'DMAR [g/m2/a]'
DMARRE = 'DMAR R.E. [frac., 2σ]'


# In[5]:

import argparse

# Parse command-line arguments for flexible I/O paths
parser = argparse.ArgumentParser()
parser.add_argument('--data_dir', default='../data', help='Directory containing sites_table.txt and remapped_tables/')
parser.add_argument('--output_dir', default='../data/analysis_output', help='Directory for output CSVs and PDFs')
args = parser.parse_args()

DATA_DIR = args.data_dir
OUTPUT_DIR = args.output_dir

import os
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

EDGE_NEAR_ZERO_TOL = 0.1
LOW_CONFIDENCE_THRESHOLD = 0.75


def load_mapping_provenance(site_prefix):
    prov_path = site_prefix + '_mapping_provenance.csv'
    if os.path.exists(prov_path):
        try:
            return pd.read_csv(prov_path)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def provenance_lookup(prov_df):
    lookup = {}
    if prov_df is None or prov_df.empty:
        return lookup
    for _, row in prov_df.iterrows():
        field = str(row.get('target_field', ''))
        if field and field not in lookup:
            lookup[field] = row.to_dict()
    return lookup


def get_prov_value(meta, key, default=''):
    if meta is None:
        return default
    value = meta.get(key, default)
    if pd.isna(value):
        return default
    return value


def has_low_confidence_or_ambiguity(meta):
    if meta is None:
        return True
    try:
        conf = float(get_prov_value(meta, 'mapping_confidence', 0.0))
    except Exception:
        conf = 0.0
    ambiguous = str(get_prov_value(meta, 'ambiguous_candidates', '')).strip()
    return conf < LOW_CONFIDENCE_THRESHOLD or ambiguous != ''


def has_unit_issue(meta):
    if meta is None:
        return True
    unit_class = str(get_prov_value(meta, 'unit_class', ''))
    status = str(get_prov_value(meta, 'status', ''))
    return unit_class != 'activity_supported' or status != 'Mapped'


def classify_negative_root_cause(u238_val, th232_val, lith_corr, ath232_meta, au238_meta):
    unit_issue = has_unit_issue(ath232_meta) or has_unit_issue(au238_meta)
    if unit_issue:
        detail = (
            f"ATh232(unit_class={get_prov_value(ath232_meta, 'unit_class', 'NA')},"
            f" status={get_prov_value(ath232_meta, 'status', 'NA')}); "
            f"AU238(unit_class={get_prov_value(au238_meta, 'unit_class', 'NA')},"
            f" status={get_prov_value(au238_meta, 'status', 'NA')})"
        )
        return 'SUSPECT_UNIT_MAPPING', detail

    if has_low_confidence_or_ambiguity(ath232_meta) or has_low_confidence_or_ambiguity(au238_meta):
        detail = (
            f"ATh232(conf={get_prov_value(ath232_meta, 'mapping_confidence', 'NA')}, "
            f"ambiguous={get_prov_value(ath232_meta, 'ambiguous_candidates', '')}); "
            f"AU238(conf={get_prov_value(au238_meta, 'mapping_confidence', 'NA')}, "
            f"ambiguous={get_prov_value(au238_meta, 'ambiguous_candidates', '')})"
        )
        return 'SUSPECT_COLUMN_MAPPING', detail

    try:
        balance_diff = float(u238_val) - (float(th232_val) * float(lith_corr))
    except Exception:
        return 'INSUFFICIENT_METADATA', 'Unable to evaluate U238 - ATh232*Lith.Corr balance'

    if abs(balance_diff) <= EDGE_NEAR_ZERO_TOL:
        return 'EDGE_NEAR_ZERO_BALANCE', f'|U238 - ATh232*Lith.Corr|={abs(balance_diff):.4f} <= {EDGE_NEAR_ZERO_TOL}'

    if (float(th232_val) * float(lith_corr)) > float(u238_val):
        return 'LITHOGENIC_DOMINANCE', f'ATh232*Lith.Corr={float(th232_val) * float(lith_corr):.4f} > AU238={float(u238_val):.4f}'

    return 'INSUFFICIENT_METADATA', 'Negative U238auth with valid units but no dominant deterministic condition'


def interpolate_age_entry(age_table, target_depth):
    if pd.isna(target_depth):
        return np.nan, np.nan

    depth_col = age_table['Depth [m]']
    age_col = age_table['Age [ka B.P.]']
    age_re_col = age_table['Age R.E. [frac., 2σ]']

    dd = (depth_col - target_depth).abs().dropna()
    if dd.empty:
        return np.nan, np.nan

    nearest = dd.nsmallest(2)
    idxs = nearest.index.tolist()

    if len(idxs) == 1:
        idx = idxs[0]
        return float(age_col.loc[idx]), float(age_re_col.loc[idx])

    i1, i2 = idxs[0], idxs[1]
    d1, d2 = float(depth_col.loc[i1]), float(depth_col.loc[i2])
    a1, a2 = float(age_col.loc[i1]), float(age_col.loc[i2])
    r1, r2 = float(age_re_col.loc[i1]), float(age_re_col.loc[i2])

    if d1 == d2:
        age_val = float(np.nanmean([a1, a2]))
    else:
        if d1 > d2:
            d1, d2 = d2, d1
            a1, a2 = a2, a1
        age_val = float(np.interp(target_depth, [d1, d2], [a1, a2]))

    age_re_val = float(np.sqrt(np.square(r1) + np.square(r2)))
    return age_val, age_re_val

# Read the table with the list of sites and information on the the path to follow for processing

sites = pd.read_csv(os.path.join(DATA_DIR, 'sites_table.txt'), sep='\t')
print(sites)
ns=len(sites.index)
negative_u238auth_rows = []

# Process each site in the list, by performing the following operations:
  # Read A-Samples   
  # Read D-Samples 
  # Assign names, depths to the new df "calculations" 
  # Read age_model
  # Interpolate depths of D-Samples to the corresponding ages
  # Add ages, age uncertainties of D-Samples to the df "calculations" 
  # According to the specific template, complete "calculations" with SBMAR, EC, DMAR, and relative uncertainties
  # Evaluate size range ...
  # Copy key information to the main table
  # Print the tables to excel
  # Print the main table to text
  # Print pdf with record description and metadata


for nsi in tqdm(range(0,ns)):

  try:
    print('******',sites["Site"][nsi])    
    curn = os.path.join(DATA_DIR, 'remapped_tables', sites["Site"][nsi], sites["Site"][nsi])
    provenance_df = load_mapping_provenance(curn)
    prov_lookup = provenance_lookup(provenance_df)
    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')   


  #-# Read Site_info (to keep input more readable, need to go through a few passages to transpose table)

    with open(curn+'_info_table.txt') as f:
      info00 = [[x for x in ln.split(sep='\t')] for ln in f]

    info01 = more_itertools.unzip(info00) # a tuple of generators.
    info01 = list(map(list, info01))      # a list of lists

    info = pd.DataFrame(info01)
    info.rename(columns=info.iloc[0], inplace = True)
    info=info.tail(-1)
    info.replace('\n','', regex=True,inplace=True)  

    print(info)
    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')   


  #-# Read A-Samples

    try:
      AS_table = pd.read_csv(curn+'_AS_table.txt',sep='\t')
      AS_flag=0
      print(AS_table.head())

    except:  
      print('A-Samples not available')
      AS_flag=1


    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')     



  #-# Read X-Samples

    try:
      XS_table = pd.read_csv(curn+'_XS_table.txt',sep='\t')
      XS_flag=0
      print(XS_table.head())

    except:  
      print('X-Samples not available')
      XS_flag=1


    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')     


  #-# Read D-Samples  

    DS_table = pd.read_csv(curn+'_DS_table.txt',sep='\t')
    print(DS_table.head())  
    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~') 


  #-# Read age_model

    Age_table = pd.read_csv(curn+'_Age_model_table.txt',sep='\t')
    if len(Age_table) < 2:
        print("Skipping site: Age table insufficient (rows < 2)")
        continue
    print(Age_table.head())  
    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~') 


  #-# Assign names, depths to the new df "calculations", and create columns for ages 

    calc_table = pd.DataFrame(DS_table.iloc[:,:4])
    calc_table[Atop]=np.nan
    calc_table[AtopRE]=np.nan
    calc_table[Abot]=np.nan
    calc_table[AbotRE]=np.nan
    calc_table[Ac]=np.nan
    calc_table[AcRE]=np.nan
    #print(calc_table.head())
    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~') 


  #-# Interpolate depths of D-Samples to the corresponding ages (top, bottom, center) and propagate uncertainties
    # Add to the "calculations" df

    for di in range(0,len(DS_table.index)):
      depth_center = DS_table.at[di, Dc]
      depth_top = DS_table.at[di, Dtop]
      depth_bottom = DS_table.at[di, Dbot]

      if pd.isna(depth_center):
        if not (pd.isna(depth_top) and pd.isna(depth_bottom)):
          depth_center = np.nanmean([depth_top, depth_bottom])

      if pd.isna(depth_top):
        depth_top = depth_center
      if pd.isna(depth_bottom):
        depth_bottom = depth_center

      age_c, age_c_re = interpolate_age_entry(Age_table, depth_center)
      age_t, age_t_re = interpolate_age_entry(Age_table, depth_top)
      age_b, age_b_re = interpolate_age_entry(Age_table, depth_bottom)

      calc_table.at[di, Ac] = age_c
      calc_table.at[di, AcRE] = age_c_re
      calc_table.at[di, Atop] = age_t
      calc_table.at[di, AtopRE] = age_t_re
      calc_table.at[di, Abot] = age_b
      calc_table.at[di, AbotRE] = age_b_re

    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~') 


  #-# According to the specific template, complete "calculations" with SBMAR, EC, DMAR, and relative uncertainties

    # (Here I could define specific classes, alternatively)

    # MARINE SEDIMENTS (Type 1)

    if (sites['Type'][nsi]==1):  

      # Replicate DS columns
      calc_table[Th230] = DS_table[Th230]
      calc_table[Th230re] = DS_table[Th230re]    
      calc_table[Th232] = DS_table[Th232]
      calc_table[Th232re] = DS_table[Th232re]    
      calc_table[U234] = DS_table[U234]
      calc_table[U234re] = DS_table[U234re]    
      calc_table[U238] = DS_table[U238]
      calc_table[U238re] = DS_table[U238re]    

      # Create & populate new columns
      calc_table[Th230lith] = calc_table[Th232] * float(info['Lith. Corr.'])  # Costa20_eq3
      calc_table[Th230lithRE] = np.sqrt(np.square(calc_table[Th232re])+
                                        np.square(float(info['Lith. Corr. Abs. Err.'])/float(info['Lith. Corr.'])))   
      calc_table[U238auth] = calc_table[U238] - calc_table[Th230lith]  # Costa20_eq4
      calc_table[U238authRE] = np.sqrt(np.square(calc_table[U238re])+
                                      np.square(calc_table[Th230lithRE]))   
      
      # Validate U238auth - always flag and classify negative values deterministically.
      neg_mask = calc_table[U238auth] < 0
      calc_table['U238auth_flag'] = np.where(neg_mask, 'NEGATIVE', 'OK')
      calc_table['U238auth_root_cause'] = ''
      calc_table['U238auth_root_cause_detail'] = ''

      ath232_meta = prov_lookup.get('ATh232')
      au238_meta = prov_lookup.get('AU238')

      if neg_mask.any():
          for idx in calc_table.index[neg_mask]:
              cause, detail = classify_negative_root_cause(
                  calc_table.at[idx, U238],
                  calc_table.at[idx, Th232],
                  float(info['Lith. Corr.'].values[0]),
                  ath232_meta,
                  au238_meta,
              )
              calc_table.at[idx, 'U238auth_root_cause'] = cause
              calc_table.at[idx, 'U238auth_root_cause_detail'] = detail

              sample_id = ''
              if 'Sample ID' in DS_table.columns:
                  sample_id = DS_table.at[idx, 'Sample ID']

              negative_u238auth_rows.append(
                  {
                      'Site': sites['Site'][nsi],
                      'Row index': int(idx),
                      'Sample ID': sample_id,
                      'Depth center [m]': calc_table.at[idx, Dc],
                      'ATh232 [dpm/g]': calc_table.at[idx, Th232],
                      'AU238 [dpm/g]': calc_table.at[idx, U238],
                      'Lith. Corr.': float(info['Lith. Corr.'].values[0]),
                      'ATh230 (lith) [dpm/g]': calc_table.at[idx, Th230lith],
                      'AU238 (auth) [dpm/g]': calc_table.at[idx, U238auth],
                      'U238auth_root_cause': cause,
                      'U238auth_root_cause_detail': detail,
                      'ATh232_source_column': get_prov_value(ath232_meta, 'source_column', ''),
                      'ATh232_unit_class': get_prov_value(ath232_meta, 'unit_class', ''),
                      'ATh232_mapping_confidence': get_prov_value(ath232_meta, 'mapping_confidence', ''),
                      'AU238_source_column': get_prov_value(au238_meta, 'source_column', ''),
                      'AU238_unit_class': get_prov_value(au238_meta, 'unit_class', ''),
                      'AU238_mapping_confidence': get_prov_value(au238_meta, 'mapping_confidence', ''),
                  }
              )

      if neg_mask.any():
          neg_count = int(neg_mask.sum())
          high_th232 = int((calc_table.loc[neg_mask, Th232] > 5).sum())
          low_u238 = int((calc_table.loc[neg_mask, U238] < 3).sum())
          cause_counts = calc_table.loc[neg_mask, 'U238auth_root_cause'].value_counts().to_dict()
          
          print(f"WARNING: {sites['Site'][nsi]} has {neg_count} negative U238auth values")
          print(f"  Root cause analysis:")
          print(f"    - High ATh232 (>5 dpm/g): {high_th232} samples")
          print(f"    - Low AU238 (<3 dpm/g): {low_u238} samples")
          for cause_name, cause_n in cause_counts.items():
              print(f"    - {cause_name}: {cause_n} samples")
          
          report_path = os.path.join(OUTPUT_DIR, sites["Site"][nsi]+'_validation_report.txt')
          with open(report_path, 'w') as f:
              f.write(f"Validation Report: {sites['Site'][nsi]}\n")
              f.write(f"{'='*50}\n\n")
              f.write(f"Negative U238auth samples: {neg_count} / {len(calc_table)}\n")
              f.write(f"\nRoot Cause Analysis:\n")
              f.write(f"  - High ATh232 (>5 dpm/g): {high_th232} samples\n")
              f.write(f"  - Low AU238 (<3 dpm/g): {low_u238} samples\n")
              f.write(f"  - Lith.Corr: {info['Lith. Corr.'].values[0]}\n")
              for cause_name, cause_n in cause_counts.items():
                  f.write(f"  - {cause_name}: {cause_n} samples\n")
              f.write(f"\nNegative Sample Rows:\n")
              for idx in calc_table.index[neg_mask]:
                  sample_id = ''
                  if 'Sample ID' in DS_table.columns:
                      sample_id = DS_table.at[idx, 'Sample ID']
                  f.write(
                      f"  - row={idx}, sample={sample_id}, depth={calc_table.at[idx, Dc]}, "
                      f"U238auth={calc_table.at[idx, U238auth]:.4f}, "
                      f"cause={calc_table.at[idx, 'U238auth_root_cause']}\n"
                  )

      calc_table[Th230auth] = calc_table[U238auth] * (1.-np.exp(-marine_lambda230*calc_table[Ac]))  # Costa20_eq5a
      calc_table[Th230authRE] = np.sqrt(np.square(calc_table[U238authRE])+
                                        np.square(marine_lambda230_RE)+
                                        np.square(calc_table[AcRE]))       
      calc_table[Th230xs] = calc_table[Th230]-calc_table[Th230auth]-calc_table[Th230lith]  # Costa20_eq2
      calc_table[Th230xsRE] = np.sqrt(np.square(calc_table[Th230re])+
                                      np.square(calc_table[Th230authRE])+
                                      np.square(calc_table[Th230lithRE]))       
      calc_table[Th230xs0] = calc_table[Th230xs] * np.exp(marine_lambda230*calc_table[Ac])    # Costa20_eq6
      calc_table[Th230xs0RE] = np.sqrt(np.square(calc_table[Th230xsRE])+
                                      np.square(marine_lambda230_RE)+
                                      np.square(calc_table[AcRE]))       
      calc_table[SBMAR] = -1*float(info['Elevation [m]']) * marine_beta230 / calc_table[Th230xs0] # Costa20_eq7
      calc_table[SBMARRE] = np.sqrt(np.square(calc_table[Th230xs0RE])+
                                    np.square(marine_beta230_RE))       
      calc_table[Th232mr] = calc_table[Th232] / ATh230tomass      #
      calc_table[Th232mrRE] = np.sqrt(np.square(calc_table[Th232re])+
                                      np.square(ATh230tomass_RE))       
      calc_table[EC] = calc_table[Th232mr] / Th232todust      #
      calc_table[ECRE] = np.sqrt(np.square(calc_table[Th232mrRE])+
                                np.square(Th232todust_RE))           
      calc_table[DMAR] = calc_table[EC] * calc_table[SBMAR]
      calc_table[DMARRE] = np.sqrt(np.square(calc_table[ECRE])+
                                  np.square(calc_table[SBMARRE]))           




    print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~') 



  #-# ...

    print(calc_table.head())
    calc_table.to_csv(os.path.join(OUTPUT_DIR, sites["Site"][nsi]+'_calc_table.csv'))



  #-# Make summary plot

    #- Set multipanel plot

    fig = plt.figure(figsize=(12,7),constrained_layout=True)

    gs0 = fig.add_gridspec(nrows=2,ncols=2,height_ratios=[1.5,2], width_ratios=[3,1])

    gs00 = gs0[0,0].subgridspec(nrows=1, ncols=3) # map ; text/titles for A/D/X samples 
    gs000 = gs00[0,0].subgridspec(nrows=1, ncols=1) # map
    gs001 = gs00[0,1].subgridspec(nrows=2, ncols=1) # resolution statistics (boxplots)
    gs002 = gs00[0,2].subgridspec(nrows=1, ncols=1) # text/titles for A/D/X samples

    gs01 = gs0[0,1].subgridspec(nrows=3, ncols=1) # depth profiles of A/D/X samples
    gs11 = gs0[1,1].subgridspec(nrows=2, ncols=1) # profile of EC and SBMAR
    gs10 = gs0[1,0].subgridspec(nrows=1, ncols=1) # Time series of DMAR

    # Add map and title  

    smap = fig.add_subplot(gs000[0, 0],projection=crs.PlateCarree())
    smap.set_title(sites["Site"][nsi])
    smap.coastlines()
    smap.set_global()
    #smap.add_feature(cfeature.LAND)
    #smap.add_feature(cfeature.OCEAN)
    #ocean_10m = cfeature.NaturalEarthFeature('physical', 'ocean', '10m',
    #                                      edgecolor='face', facecolor=cfeature.COLORS['water'])
    #smap.add_feature(ocean_10m)
    smap.plot(sites["Longitude E"][nsi],sites["Latitide N"][nsi],
            color='red', marker='o', markersize=5)

    # Add time resolution & span statistics

    pstat1 = fig.add_subplot(gs001[0, 0])
    pstat1.set_title('Every sample integrates ... [ka]')
    pstat1.boxplot(calc_table[Abot]-calc_table[Atop],vert=False)

    pstat2 = fig.add_subplot(gs001[1, 0])
    pstat2.set_title('One sample every ... [ka]')
    pstat2.boxplot(calc_table[Ac].diff().dropna(),vert=False)


    # Add depth profiles of A/D/X samples 
  # This could be one plot for all, with "If" to check what's available

    # DS first

    pDS = fig.add_subplot(gs01[1, 0]) 
    # also check: axs[0, 0].eventplot(
    slices = [Rectangle((top, 0), bot-top, 1) for top,bot in zip(calc_table[Dtop],calc_table[Dbot])]
    pc = PatchCollection(slices,edgecolor=None,color='peru')
    pDS.add_collection(pc)
    pDS.set_ylabel('DS')
    pDS.set_yticks([])
    pDS.set_xlabel('Depth [m]')
    core_depth = calc_table[Dbot].max()
    pDS.set_xlim(0,core_depth)
    pDS.use_sticky_edges = False  # has no effect apperently
    #pDS.plot(calc_table[Dc],[0.5]*len(calc_table[Dc]),linestyle='None')   # to make sure axis is constant


    # AS

    colbar_AS=['black','crimson','lightgray']

    if (AS_flag ==0):
      #tAS = fig.add_subplot(gs002[0, 0]) 
      pAS = fig.add_subplot(gs01[0, 0]) 

      slices = [Rectangle((top, 0), bot-top, 1, color=colbar_AS[ty],edgecolor=None) 
                for top,bot,ty in zip(AS_table[Dtop],AS_table[Dbot],AS_table['Type'])]
      pc = PatchCollection(slices, match_original=True)
      pAS.add_collection(pc)
      pAS.set_ylabel('AS')
      pAS.set_yticks([])
      pAS.set_xlabel('Depth [m]')
      pAS.set_xlim(0,core_depth)

  # Age samples: not all age samples may be used for the age model: should we plot them all ??
  # This is the case for absolute ages treated as outliers by fitting algorithms, 
  #  but also happens with e.g. d18O, for which only a few samples are tagged and used as stratigraphic 
  #  markers for wiggle-matching to a stack (SPECMAP, LR04, ...)

  # ** The solution for now is to mark only the tie-points and absolute ages **


    # XS

    if (XS_flag ==0):   
      #tXS = fig.add_subplot(gs002[2, 0])
      pXS = fig.add_subplot(gs01[2, 0])  



    # Add age model 
    # (shohuld it be only the portion of interest ??)

    colbar_AS=['black','crimson','lightgray']

    pAM = fig.add_subplot(gs002[0, 0]) 
    pAM.set_xlim(0,core_depth)  # limit to portion of interest (i.e. existing dust data)
    pAM.set_title('Age model')
    pAM.set_ylabel('Age [ka B.P.]')
    pAM.set_xlabel('Depth [m]') 
    pAM.plot(Age_table['Depth [m]'],Age_table['Age [ka B.P.]'],marker='.',linestyle=':',alpha=0.5)   
    if (AS_flag ==0):
      for nai in range(0,len(AS_table[Dc])):
        pAM.plot(AS_table[Dc][nai],AS_table['Age [ka B.P.]'][nai],colbar_AS[AS_table['Type'][nai]],marker='+')      


    # Add profile of EC and SBMAR

    pSBMAR = fig.add_subplot(gs11[0, 0]) 
    pSBMAR.set_xlabel(Dc)
    pSBMAR.set_ylabel(SBMAR)
    pSBMAR.fill_between(calc_table[Dc], calc_table[SBMAR]-calc_table[SBMAR]*calc_table[SBMARRE], 
                        calc_table[SBMAR]+calc_table[SBMAR]*calc_table[SBMARRE],alpha=0.3)
    pSBMAR.plot(calc_table[Dc],calc_table[SBMAR])

    pEC = fig.add_subplot(gs11[1, 0]) 
    pEC.set_xlabel(Dc)
    pEC.set_ylabel(EC)
    pEC.fill_between(calc_table[Dc], calc_table[EC]-calc_table[EC]*calc_table[ECRE], 
                        calc_table[EC]+calc_table[EC]*calc_table[ECRE],alpha=0.3)
    pEC.plot(calc_table[Dc],calc_table[EC])

    # Add time series of DMAR vs Age

    pDMAR = fig.add_subplot(gs10[0, 0])  

    # Simulate data from a bivariate Gaussian
  #  n = 10000
  #  for si in range(0,len(calc_table[Ac])):
  #    bvg_mean = [calc_table[Ac][si], calc_table[DMAR][si]]  ;print(bvg_mean)
  #    cov = [(calc_table[AcRE][si], calc_table[DMARRE][si]), (calc_table[DMARRE][si], calc_table[AcRE][si])]
  #    rng = np.random.RandomState(0)
  #    x, y = rng.multivariate_normal(bvg_mean[si], cov[si], n).T
      #sns.kdeplot(x=x, y=y, levels=5, color="w", linewidths=1)


    pDMAR.set_xlabel(Ac)
    pDMAR.set_ylabel(DMAR)

    pDMAR.plot(calc_table[Ac]-0.5*calc_table[Ac]*calc_table[AcRE],calc_table[DMAR],color='tan',alpha=0.5,linestyle=':')  
    pDMAR.plot(calc_table[Ac]+0.5*calc_table[Ac]*calc_table[AcRE],calc_table[DMAR],color='tan',alpha=0.5,linestyle=':')  
    pDMAR.plot(calc_table[Ac]-1*calc_table[Ac]*calc_table[AcRE],calc_table[DMAR],color='tan',alpha=0.2,linestyle=':')  
    pDMAR.plot(calc_table[Ac]+1*calc_table[Ac]*calc_table[AcRE],calc_table[DMAR],color='tan',alpha=0.2,linestyle=':')  

  #  pDMAR.fill_between(calc_table[Ac], calc_table[DMAR]-calc_table[DMAR]*calc_table[DMARRE], 
  #                     calc_table[DMAR]+calc_table[DMAR]*calc_table[DMARRE],alpha=0.3)
  #  pDMAR.fill_betweenx(calc_table[DMAR], calc_table[Ac]-calc_table[Ac]*calc_table[AcRE], 
  #                      calc_table[Ac]+calc_table[Ac]*calc_table[AcRE],alpha=0.3,color='yellow')#,interpolate=True )

  #  pDMAR.plot([calc_table[Ac]-calc_table[Ac]*calc_table[AcRE],calc_table[Ac]+calc_table[Ac]*calc_table[AcRE]],
  #             [calc_table[DMAR],calc_table[DMAR]],color='gold',linewidth=0.1)
  #  pDMAR.plot([calc_table[Ac],calc_table[Ac]],
  #             [calc_table[DMAR]-calc_table[DMAR]*calc_table[DMARRE], 
  #              calc_table[DMAR]+calc_table[DMAR]*calc_table[DMARRE]],color='grey',linewidth=0.1)

  #  pDMAR.plot(calc_table[Ac],calc_table[DMAR],linestyle="None",markersize=5,marker="+",color='r')


    slices1 = [Rectangle((Atop,Dmin),Abot-Atop,Dmax-Dmin)
               for Atop,Abot,Dmin,Dmax in zip(calc_table[Atop],calc_table[Abot],
                                              calc_table[DMAR]-calc_table[DMARRE]*calc_table[DMAR],
                                              calc_table[DMAR]+calc_table[DMARRE]*calc_table[DMAR])]
    slices2 = [Rectangle((Atop,Dmin),Abot-Atop,Dmax-Dmin)
               for Atop,Abot,Dmin,Dmax in zip(calc_table[Atop],calc_table[Abot],
                                              calc_table[DMAR]-0.5*calc_table[DMARRE]*calc_table[DMAR],
                                              calc_table[DMAR]+0.5*calc_table[DMARRE]*calc_table[DMAR])]

    pc1 = PatchCollection(slices1,color='peru',alpha=0.2,edgecolor=None)
    pc2 = PatchCollection(slices2,color='peru',alpha=0.5,edgecolor=None)
    pDMAR.add_collection(pc1) ; pDMAR.add_collection(pc2)

  #twilight bw should be good for 1D SD i.e. for DMAR

  # https://stackoverflow.com/questions/10958835/matplotlib-color-gradient-in-patches    
  # https://stackoverflow.com/questions/66837477/how-to-gradient-fill-drawn-shapes

    pDMAR.plot(calc_table[Ac],calc_table[DMAR],color='peru',linestyle=':')
    pDMAR.plot([calc_table[Abot],calc_table[Atop]],[calc_table[DMAR],calc_table[DMAR]],color='r')


    # Further improvemenets:
    # - confidence level
    # - boxplot with age uncertainty?
    # - test case with A-Samples info
    # - test case with Size-Samples
    # - consider case for multiple X-Samples (e.g. elemental, mineralogical, isotopical composition)



    #fig.tight_layout()
    #plt.show()
    plt.savefig(os.path.join(OUTPUT_DIR, sites["Site"][nsi]+'_summary.pdf'))  



    # Also, needs to print an info page for each record, including the text information

    # https://tex.stackexchange.com/questions/885/how-can-i-use-latex-from-python 





  except Exception as e:
      print(f"ERROR processing site {sites['Site'][nsi]}: {e}")
      continue

diagnostics_columns = [
    'Site',
    'Row index',
    'Sample ID',
    'Depth center [m]',
    'ATh232 [dpm/g]',
    'AU238 [dpm/g]',
    'Lith. Corr.',
    'ATh230 (lith) [dpm/g]',
    'AU238 (auth) [dpm/g]',
    'U238auth_root_cause',
    'U238auth_root_cause_detail',
    'ATh232_source_column',
    'ATh232_unit_class',
    'ATh232_mapping_confidence',
    'AU238_source_column',
    'AU238_unit_class',
    'AU238_mapping_confidence',
]
pd.DataFrame(negative_u238auth_rows, columns=diagnostics_columns).to_csv(
    os.path.join(OUTPUT_DIR, 'u238auth_negative_diagnostics.csv'),
    index=False,
)
print(f"Saved global negative U238auth diagnostics to {os.path.join(OUTPUT_DIR, 'u238auth_negative_diagnostics.csv')}")

# In[6]:


# Write into json (geo-json) format
# and/or L


# In[7]:


# Notes


# I could add a zoomed-in google earth map showing the context (blue-marble, ocean bathymetry) of the site 
#  in a e.g. 3x3 deg. window

# https://developers.google.com/earth-engine/tutorials/community/intro-to-python-api-guiattard#get_a_static_map
# https://www.kaggle.com/carlmcbrideellis/bluemarble-and-etopo-in-cartopy?select=etopo.png
# https://scitools.org.uk/cartopy/docs/latest/gallery/web_services/image_tiles.html#sphx-glr-gallery-web-services-image-tiles-py

# adding cfeatures is not workin, and the pdf also looks empty
