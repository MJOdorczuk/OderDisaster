import rasterio
from matplotlib import pyplot as plt
from rasterio.plot import show
from pyproj import Transformer
import numpy as np

def plot_background_map(title, limits, target_crs, grid_step = 1.0):
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.set_axis_off()
    ax.set_title(title)
    ax.set_facecolor("black")
    with rasterio.open("figures/poland_satellite_background.tif") as src:
        show(src, ax=ax, alpha=0.4)


    transformer = Transformer.from_crs("EPSG:4326", target_crs, always_xy=True,)

    west, south, east, north = limits
    xmin, ymin = transformer.transform(west, south)
    xmax, ymax = transformer.transform(east, north)

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)

    to_map = Transformer.from_crs(
        "EPSG:4326",
        target_crs,
        always_xy=True,
    )

    grid_lons = np.arange(
        np.ceil(west / grid_step) * grid_step + grid_step,
        east,
        grid_step,
    )
    grid_lats = np.arange(
        np.ceil(south / grid_step) * grid_step + grid_step,
        north,
        grid_step,
    )
    line_lats = np.linspace(south, north, 200)
    line_lons = np.linspace(west, east, 200)

    # Draw longitude (meridian) lines.
    for lon in grid_lons:
        x, y = to_map.transform(
            np.full_like(line_lats, lon),
            line_lats,
        )

        ax.plot(x, y, color="white", linewidth=0.6, alpha=0.45, linestyle="--", zorder=2)

        # Label longitude near the southern map boundary.
        label_x, label_y = to_map.transform(lon, south)
        ax.text(
            label_x,
            label_y,
            f"{lon:.0f}°E",
            fontsize=8,
            color="white",
            ha="center",
            va="top",
            zorder=10,
            bbox={"facecolor": "black", "alpha": 0.45, "pad": 1.5},
        )

    # Draw latitude (parallel) lines.
    for lat in grid_lats:
        x, y = to_map.transform(
            line_lons,
            np.full_like(line_lons, lat),
        )

        ax.plot(x, y, color="white", linewidth=0.6, alpha=0.45, linestyle="--", zorder=2)

        # Label latitude near the western map boundary.
        label_x, label_y = to_map.transform(west, lat)
        ax.text(
            label_x,
            label_y,
            f"{lat:.0f}°N",
            fontsize=8,
            color="white",
            ha="left",
            va="center",
            zorder=10,
            bbox={"facecolor": "black", "alpha": 0.45, "pad": 1.5},
        )

    # Hide projected-coordinate tick labels; the degree labels above replace them.
    ax.set_xticks([])
    ax.set_yticks([])

    ax.text(
        0.01,
        0.01,
        "Imagery © Esri and its data providers",
        transform=ax.transAxes,
        fontsize=8,
        color="white",
        bbox={"facecolor": "black", "alpha": 0.85, "pad": 3},
    )

    plt.tight_layout()
    return fig, ax