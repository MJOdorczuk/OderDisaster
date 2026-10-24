from contextlib import ExitStack
import numpy as np
import rasterio
import os
import pandas as pd
from zipfile import ZipFile
import shutil
import re
from pathlib import Path
from rasterio.enums import Resampling
from rasterio.merge import merge
from rasterio.vrt import WarpedVRT
from rasterio.features import geometry_mask
from shapely.geometry import box
from shapely.ops import unary_union
from rasterio.windows import Window
from rasterio.windows import transform as window_transform
from rasterio.warp import reproject, Resampling

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
    resolution,
    bands,
    output_root,
    target_crs="EPSG:3035"
):

    nodata_value = 0

    resolution_label = f"{resolution}m"

    aoi_output_folder = output_root / date_text / aoi_name

    if (aoi_output_folder / f"{resolution_label}_Stack.tif").exists():
        print(f"Stack file already exists for AOI {aoi_name} and resolution {resolution_label}. Skipping processing.")
        return

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

def sample_points(data_dir, line_geometry, sample_spacing, sample_class, band_names10, band_names20):
    stack_files10 = [data_dir / segment / "10m_Stack.tif" for segment in os.listdir(data_dir)]
    stack_files20 = [data_dir / segment / "20m_Stack.tif" for segment in os.listdir(data_dir)]
    stack_files = zip(stack_files10, stack_files20)

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
    # profile.insert(2, "distance_km_from_source", sample_to_length_km(distances / 1000))

    scl = profile["SCL SceneClassification"]
    if sample_class is not None:
        profile = profile[(scl==sample_class)]
    return profile

def extract_bands_from_zip(date, tile, zip_filename, bands10, bands20):
    temp_dir = Path(f"raw_data/tmp/{date}_{tile}")
    extracted_dir = Path(f"raw_data/extracted/{date}_{tile}")
    if extracted_dir.exists():
        print(f"Extracted directory already exists for {date}_{tile}. Skipping extraction.")
        return
    with ZipFile(f"raw_data/{zip_filename}", 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    data_dir = temp_dir / zip_filename[:-4] / "GRANULE"
    data_dir = data_dir / os.listdir(data_dir)[0] / "IMG_DATA"
    data10_dir = data_dir / "R10m"
    data20_dir = data_dir / "R20m"
    datafiles10 = os.listdir(data10_dir)
    datafiles20 = os.listdir(data20_dir)
    date_tile_dir = Path(f"raw_data/extracted/{date}_{tile}")
    (date_tile_dir / "R10m").mkdir(parents=True, exist_ok=True)
    (date_tile_dir / "R20m").mkdir(parents=True, exist_ok=True)
    for file in datafiles10:
        band = file[-11:-8]
        if band in bands10:
            data_output_path = date_tile_dir / "R10m" / f"{band}_10m.jp2"
            shutil.copy(data10_dir / file, data_output_path)
    for file in datafiles20:
        band = file[-11:-8]
        if band in bands20:
            data_output_path = date_tile_dir / "R20m" / f"{band}_20m.jp2"
            shutil.copy(data20_dir / file, data_output_path)
    shutil.rmtree(temp_dir)


def stacks_to_dataframe(
    stack_10m_path,
    bands_10m,
    stack_20m_path,
    bands_20m,
    scl_band_name="SCL",
    normalise_factor=10_000.0
):
    stack_10m_path = Path(stack_10m_path)
    stack_20m_path = Path(stack_20m_path)

    data = {}

    with rasterio.open(stack_10m_path) as src_10m:
        target_height = src_10m.height
        target_width = src_10m.width
        target_transform = src_10m.transform
        target_crs = src_10m.crs

        for name, band_index in bands_10m.items():
            band = src_10m.read(band_index).astype(np.float32) / normalise_factor

            if src_10m.nodata is not None:
                band[band == src_10m.nodata] = np.nan

            data[name] = band.ravel()

        rows, cols = np.indices((target_height, target_width))

        xs, ys = rasterio.transform.xy(
            target_transform,
            rows,
            cols,
            offset="center",
        )

        data["x"] = np.asarray(xs).ravel()
        data["y"] = np.asarray(ys).ravel()

    with rasterio.open(stack_20m_path) as src_20m:
        for name, band_index in bands_20m.items():
            source = src_20m.read(band_index)

            if name == scl_band_name:
                resampling_method = Resampling.nearest
            else:
                source = source.astype(np.float32) / normalise_factor
                resampling_method = Resampling.bilinear

            destination = np.full(
                (target_height, target_width),
                np.nan,
                dtype=np.float32,
            )

            reproject(
                source=source,
                destination=destination,
                src_transform=src_20m.transform,
                src_crs=src_20m.crs,
                src_nodata=src_20m.nodata,
                dst_transform=target_transform,
                dst_crs=target_crs,
                dst_nodata=np.nan,
                resampling=resampling_method,
            )

            data[name] = destination.ravel()

    df = pd.DataFrame(data)

    df = df.dropna(subset=list(bands_10m.keys()), how="all")

    if scl_band_name in df.columns:
        df[scl_band_name] = df[scl_band_name].round().astype("Int16")

    return df, f"{target_crs}"