import rasterio
from matplotlib import pyplot as plt
from rasterio.plot import show
from pyproj import Transformer
import numpy as np
from matplotlib_map_utils import scale_bar
from matplotlib.patches import Rectangle
import rasterio
from rasterio.plot import show
from pyproj import Transformer
from matplotlib_map_utils import scale_bar
from matplotlib.patches import Rectangle

def add_grid_lines(target_crs, limits, ax, grid_step, fontsize=12, linecolour="white"):
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

    for lon in grid_lons:
        x, y = to_map.transform(
            np.full_like(line_lats, lon),
            line_lats,
        )

        ax.plot(x, y, color=linecolour, linewidth=0.6, alpha=0.45, linestyle="--", zorder=2)

        label_x, label_y = to_map.transform(lon, north)
        ax.text(
            label_x,
            label_y,
            f"{lon:.4g}°E",
            fontsize=fontsize,
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

        ax.plot(x, y, color=linecolour, linewidth=0.6, alpha=0.45, linestyle="--", zorder=2)

        # Label latitude near the western map boundary.
        label_x, label_y = to_map.transform(west, lat)
        ax.text(
            label_x,
            label_y,
            f"{lat:.4g}°N",
            fontsize=fontsize,
            color="white",
            ha="left",
            va="center",
            zorder=10,
            bbox={"facecolor": "black", "alpha": 0.45, "pad": 1.5},
        )

    ax.set_xticks([])
    ax.set_yticks([])

def plot_background_map(title, limits, target_crs, grid_step = 1.0, darkening_factor = 0.7, fig_ax=None, fontsize=12):
    if fig_ax is None:
        fig, ax = plt.subplots(figsize=(12, 10))
    else:
        fig, ax = fig_ax
    ax.set_axis_off()
    ax.set_title(title)
    with rasterio.open("figures/poland_satellite_background.tif") as src:
        bounds = src.bounds
        ax.add_patch(Rectangle((bounds.left, bounds.bottom), bounds.right - bounds.left, bounds.top - bounds.bottom, facecolor="black", edgecolor="none", zorder=0))
        show(src, ax=ax, alpha=darkening_factor)

    add_grid_lines(target_crs, limits, ax, grid_step)

    ax.text(
        0.01,
        0.01,
        "Imagery © Esri and its data providers",
        transform=ax.transAxes,
        fontsize=fontsize,
        color="white",
        bbox={"facecolor": "black", "alpha": 0.85, "pad": 3},
    )

    scale_bar(ax=ax, location="lower right", style="boxes",
              bar={"projection":target_crs[-4:],"minor_type":"none", "edgecolors":["white"]},
              labels={"style":"first_last"},
              text={"fontweight": "bold", "stroke_color": "black", "stroke_width":3, "textcolor": "white"})
    return fig, ax


def plot_spectra_labels(wavelengths, band_names, ax, fontsize=10):
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Normalised reflectance")
    for i in range(len(wavelengths)):
        ax.axvline(x=wavelengths[i], color='gray', linestyle='--', alpha=0.5)
        ax.text(wavelengths[i], ax.get_ylim()[0], band_names[i], rotation=90, verticalalignment='bottom', horizontalalignment='center', fontsize=fontsize)

def normalise_rgb(rgb):
    low, high = np.percentile(rgb, (2, 98))
    return np.clip((rgb - low) / (high - low), 0, 1)