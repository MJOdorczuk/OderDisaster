from contextlib import ExitStack
import numpy as np
import rasterio
import os
import pandas as pd
import geopandas as gpd
from rasterio.enums import Resampling
from rasterio.merge import merge
from rasterio.vrt import WarpedVRT
from rasterio.features import geometry_mask
from shapely.geometry import box
from shapely.ops import unary_union
from rasterio.windows import Window
from rasterio.windows import transform as window_transform

def create_masked_band_mosaic(
    input_files,
    aoi_geometry,
    output_file,
    resolution,
    resampling_method,
    target_crs,
    nodata_value=0
):
    with ExitStack() as stack:

        warped_sources = []

        for input_file in input_files:

            source = stack.enter_context(rasterio.open(input_file))

            vrt = stack.enter_context(
                WarpedVRT(
                    source,
                    crs=target_crs,
                    resolution=resolution,
                    resampling=resampling_method,
                    src_nodata=nodata_value,
                    nodata=nodata_value,
                    init_dest_nodata=True
                )
            )

            warped_sources.append(vrt)

        tile_footprints = [
            box(source.bounds.left, source.bounds.bottom, source.bounds.right, source.bounds.top)
            for source in warped_sources
        ]

        available_coverage = unary_union(tile_footprints)

        clip_geometry = aoi_geometry.intersection(available_coverage)

        if clip_geometry.is_empty:
            return False

        mosaic, transform = merge(
            warped_sources,
            bounds=clip_geometry.bounds,
            res=resolution,
            nodata=nodata_value,
            method="first",
            masked=True
        )

        mosaic_band = mosaic[0]

        inside_aoi = geometry_mask(
            [clip_geometry],
            out_shape=mosaic_band.shape,
            transform=transform,
            invert=True
        )

        mosaic_band[~inside_aoi] = nodata_value

        valid_pixels = (
            inside_aoi &
            (mosaic_band != nodata_value)
        )

        if not np.any(valid_pixels):
            return False

        valid_rows, valid_cols = np.where(valid_pixels)

        row_min = valid_rows.min()
        row_max = valid_rows.max()
        col_min = valid_cols.min()
        col_max = valid_cols.max()

        crop_window = Window(
            col_off=col_min,
            row_off=row_min,
            width=col_max - col_min + 1,
            height=row_max - row_min + 1
        )

        mosaic_band = mosaic_band[
            row_min:row_max + 1,
            col_min:col_max + 1
        ]

        transform = window_transform(crop_window, transform)

        profile = {
            "driver": "GTiff",
            "height": mosaic_band.shape[0],
            "width": mosaic_band.shape[1],
            "count": 1,
            "dtype": mosaic_band.dtype,
            "crs": target_crs,
            "transform": transform,
            "nodata": nodata_value,
            "compress": "lzw",
            "tiled": True
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)

        with rasterio.open(output_file, "w", **profile) as destination:
            destination.write(mosaic_band, 1)
        return True


def create_stack(input_band_files, output_file, band_descriptions, nodata_value=0):

    with rasterio.open(input_band_files[0]) as first_raster:

        profile = first_raster.profile.copy()

        profile.update(
            count=len(input_band_files),
            compress="lzw",
            tiled=True,
            nodata=nodata_value
        )

        output_file.parent.mkdir(parents=True, exist_ok=True)

        with rasterio.open(output_file, "w", **profile) as stack:

            for output_band_number, input_file in enumerate(
                input_band_files,
                start=1
            ):

                with rasterio.open(input_file) as source:
                    stack.write(source.read(1), output_band_number)

                stack.set_band_description(
                    output_band_number,
                    band_descriptions[output_band_number - 1]
                )


def process_resolution_for_aoi(
    date_text,
    band_files,
    aoi_name,
    aoi_geometry,
    resolution_label,
    bands,
    output_root,
    target_crs="EPSG:3035"
):

    resolutions = {
        "10m": 10,
        "20m": 20
    }

    nodata_value = 0

    resolution = resolutions[resolution_label]

    aoi_output_folder = output_root / date_text / aoi_name

    created_band_files = []

    for band in bands:

        input_files = band_files.get(date_text, {}).get(band, [])

        if not input_files:
            return

        output_file = (
            aoi_output_folder /
            f"{band}_{resolution_label}.tif"
        )

        if band == "SCL":
            resampling_method = Resampling.nearest
        else:
            resampling_method = Resampling.bilinear

        band_created = create_masked_band_mosaic(
            input_files=input_files,
            aoi_geometry=aoi_geometry,
            output_file=output_file,
            resolution=resolution,
            resampling_method=resampling_method,
            target_crs=target_crs,
            nodata_value=nodata_value
        )

        if not band_created:
            return

        created_band_files.append(output_file)


    stack_file = (
        aoi_output_folder /
        f"{resolution_label}_Stack.tif"
    )

    create_stack(
        input_band_files=created_band_files,
        output_file=stack_file,
        band_descriptions=bands,
        nodata_value=nodata_value
    )

def sample_points(data_dir, line_geometry, sample_spacing, sample_class=6):
    stack_files10 = [data_dir / segment / "10m_Stack.tif" for segment in os.listdir(data_dir)]
    stack_files20 = [data_dir / segment / "20m_Stack.tif" for segment in os.listdir(data_dir)]
    stack_files = zip(stack_files10, stack_files20)

    band_names10 = ["B02 Blue", "B03 Green", "B04 Red", "B08 NIR"]
    band_names20 = ["B05 RedEdge1", "B11 SWIR1", "SCL SceneClassification"]

    line_length = line_geometry.length

    distances = np.arange(0, line_length + sample_spacing, sample_spacing)
    distances = np.clip(distances, 0, line_length)
    distances = np.unique(distances)
    sample_points = [line_geometry.interpolate(distance) for distance in distances]
    coordinates = [(point.x, point.y) for point in sample_points]

    sampled_values10 = None
    sampled_values20 = None

    for stack_file10, stack_file20 in stack_files:
        with rasterio.open(stack_file10) as src10:
            with rasterio.open(stack_file20) as src20:

                local_sampled_values10 = np.array(list(src10.sample(coordinates))).astype("float32")
                local_sampled_values20 = np.array(list(src20.sample(coordinates))).astype("float32")

                if sampled_values10 is None:
                    sampled_values10 = local_sampled_values10
                if sampled_values20 is None:
                    sampled_values20 = local_sampled_values20
                local_sampled_values10[(local_sampled_values10 == src10.nodata)] = np.nan
                local_sampled_values20[(local_sampled_values20 == src20.nodata)] = np.nan
                nanmask10 = ~np.isnan(local_sampled_values10)
                nanmask20 = ~np.isnan(local_sampled_values20)
                sampled_values10[nanmask10] = local_sampled_values10[nanmask10]
                sampled_values20[nanmask20] = local_sampled_values20[nanmask20]

    profile = pd.concat(
        [
            pd.DataFrame(sampled_values10, columns=band_names10),
            pd.DataFrame(sampled_values20, columns=band_names20),
            pd.DataFrame(coordinates, columns=["x", "y"])
        ],
        axis=1
    )

    profile.insert(0, "distance_m", distances)
    profile.insert(1, "distance_km", distances / 1000)

    scl = profile["SCL SceneClassification"]
    if sample_class is not None:
        profile = profile[(scl==sample_class)]
    return profile