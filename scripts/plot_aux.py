import rasterio
from matplotlib import pyplot as plt
from rasterio.plot import show
from pyproj import Transformer

def plot_background_map(title, limits, target_crs):
    with rasterio.open("figures/poland_satellite_background.tif") as src:
        fig, ax = plt.subplots(figsize=(12, 10))
        show(src, ax=ax)

    ax.set_axis_off()

    ax.text(
        0.01,
        0.01,
        "Imagery © Esri and its data providers",
        transform=ax.transAxes,
        fontsize=8,
        color="white",
        bbox={"facecolor": "black", "alpha": 0.85, "pad": 3},
    )

    ax.set_title(title)

    transformer = Transformer.from_crs("EPSG:4326", target_crs, always_xy=True,)

    west, south, east, north = limits
    xmin, ymin = transformer.transform(west, south)
    xmax, ymax = transformer.transform(east, north)

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)

    plt.tight_layout()
    return fig, ax