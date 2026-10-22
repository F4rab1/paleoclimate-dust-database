
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import pandas as pd
import argparse
import os

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_csv', required=True, help='Path to all_sites_with_coords.csv')
    parser.add_argument('--output_dir', required=True, help='Directory to save the map')
    args = parser.parse_args()
    
    input_csv = args.input_csv
    output_dir = args.output_dir
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    print(f"Reading {input_csv}...")
    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        print(f"Error: File not found: {input_csv}")
        return

    # Filter invalid coords
    df = df.dropna(subset=['latitude', 'longitude'])
    # Ensure numerical
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    df = df.dropna(subset=['latitude', 'longitude'])
    
    print(f"dataset size with coords: {len(df)}")
    
    # Define colors
    colors = {
        'D_only': 'blue',
        'D_plus_A': 'green',
        'D_plus_X': 'orange',
        'D_plus_A_plus_X': 'red'
    }
    
    # Calculate stats
    total_sites = len(df)
    stats = {}
    for cat in colors.keys():
        count = len(df[df['category'] == cat])
        pct = (count / total_sites * 100) if total_sites > 0 else 0
        stats[cat] = {'count': count, 'pct': pct}

    labels = {
        'D_only': f'D (Dust Only) (n={stats["D_only"]["count"]}, {stats["D_only"]["pct"]:.1f}%)',
        'D_plus_A': f'D + A (Dust + Age) (n={stats["D_plus_A"]["count"]}, {stats["D_plus_A"]["pct"]:.1f}%)',
        'D_plus_X': f'D + X (Structure) (n={stats["D_plus_X"]["count"]}, {stats["D_plus_X"]["pct"]:.1f}%)',
        'D_plus_A_plus_X': f'D + A + X (All) (n={stats["D_plus_A_plus_X"]["count"]}, {stats["D_plus_A_plus_X"]["pct"]:.1f}%)'
    }

    # Plot
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Robinson())
    
    ax.add_feature(cfeature.LAND, facecolor='#eeeeee')
    ax.add_feature(cfeature.OCEAN, facecolor='#e0e0e0')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5, edgecolor='#cccccc')
    ax.gridlines(draw_labels=True, linestyle='--')
    
    for cat, color in colors.items():
        subset = df[df['category'] == cat]
        if not subset.empty:
            ax.scatter(subset['longitude'], subset['latitude'], 
                       color=color, label=labels.get(cat, cat),
                       transform=ccrs.PlateCarree(), s=30, alpha=0.7, edgecolors='black', linewidth=0.5)
            
    plt.legend(loc='lower center', bbox_to_anchor=(0.5, -0.15), ncol=2, frameon=False)
    plt.title(f'Global Distribution of Mineral Dust Deposition Data Sites (N={total_sites})')
    
    output_path = os.path.join(output_dir, 'global_site_map.png')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Map saved to {output_path}")

if __name__ == "__main__":
    main()
