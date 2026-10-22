
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import pandas as pd
import os
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_csv', required=True)
    parser.add_argument('--output_dir', required=True)
    parser.add_argument('--data_tables_dir', required=True)
    args = parser.parse_args()
    
    df = pd.read_csv(args.input_csv)
    
    # Check status
    statuses = []
    reasons = []
    
    for idx, row in df.iterrows():
        doi = row['doi']
        safe_id = doi.split('.')[-1]
        site_name = f"PANGAEA_{safe_id}"
        category = row['category']
        
        path = os.path.join(args.data_tables_dir, site_name)
        
        path = os.path.join(args.data_tables_dir, site_name)
        # Check if folder exists AND contains the main data table
        ds_table_path = os.path.join(path, f"{site_name}_DS_table.txt")
        
        if category in ['D_plus_A', 'D_plus_A_plus_X']:
            if os.path.exists(path) and os.path.exists(ds_table_path):
                statuses.append('Success')
                reasons.append('Remapped')
            else:
                statuses.append('Failed')
                reasons.append('Download/Process Error')
        else:
            statuses.append('Skipped')
            reasons.append(f'Category: {category}')
            
    df['status'] = statuses
    df['reason'] = reasons
    
    # Save CSV
    df.to_csv(os.path.join(args.output_dir, 'remapping_diagnostics.csv'), index=False)
    
    # Plot
    fig = plt.figure(figsize=(15, 10))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Robinson())
    
    ax.add_feature(cfeature.LAND, facecolor='#f5f5f5')
    ax.add_feature(cfeature.OCEAN, facecolor='#eefcfd')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.BORDERS, linewidth=0.3, alpha=0.5)
    
    # subsets
    success = df[df['status'] == 'Success']
    failed = df[df['status'] == 'Failed']
    skipped = df[df['status'] == 'Skipped']
    
    n_success = len(success)
    n_failed = len(failed)
    # n_skipped = len(skipped)
    total_processed = n_success + n_failed # + n_skipped
    
    pct_success = (n_success / total_processed * 100) if total_processed > 0 else 0
    pct_failed = (n_failed / total_processed * 100) if total_processed > 0 else 0
    
    # Plot Skipped (small)
    # ax.scatter(skipped['longitude'], skipped['latitude'], transform=ccrs.PlateCarree(),
    #            color='gray', s=10, alpha=0.3, label='Skipped (Not D+A)', zorder=1)
               
    # Plot Failed
    ax.scatter(failed['longitude'], failed['latitude'], transform=ccrs.PlateCarree(),
               color='red', s=40, marker='x', label=f'Failed (n={n_failed}, {pct_failed:.1f}%)', zorder=2)
               
    # Plot Success
    ax.scatter(success['longitude'], success['latitude'], transform=ccrs.PlateCarree(),
               color='green', s=40, marker='o', edgecolors='white', linewidth=0.5, label=f'Successfully Remapped (n={n_success}, {pct_success:.1f}%)', zorder=3)
               
    ax.legend(loc='lower center', ncol=3, bbox_to_anchor=(0.5, -0.1))
    plt.title(f"Data Remapping Status (Total Processed: {total_processed})", fontsize=16)
    
    out_path = os.path.join(args.output_dir, 'remapping_diagnostic_map.png')
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    print(f"Diagnostic map saved to {out_path}")

if __name__ == "__main__":
    main()
