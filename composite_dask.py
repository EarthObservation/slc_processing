# -*- coding: utf-8 -*-
"""
Created on Fri Oct 2 11:10:03 2020

@author: ncoz

A modified version of the compositing algorithm for creation of temporal mosaics
using the Dask Array package.
"""

import os
import pickle
import time

import dask.array as da
import rasterio
import xarray as xr

from tif2jpg import plot_preview


def composite(src_fps, save_loc, save_nam, method="mean", bbox=None, dt="default"):
    """"""
    # Make sure save location exists
    os.makedirs(save_loc, exist_ok=True)

    # Save TIFF metadata for output
    with rasterio.open(src_fps[0]) as rst:
        out_meta = rst.profile.copy()

    # Lazily load files into DASK ARRAYS
    print(f"#\n# Preparing Dask arrays...")
    chunks = {'band': 1, 'x': 1024, 'y': 1024}
    lazy_arrays = [xr.open_rasterio(fp, chunks=chunks) for fp in src_fps]
    stacked = da.concatenate(lazy_arrays, axis=0)

    # Calculate composite for selected method with dask
    print(f"# Compositing ({method}) using Dask...")
    bnd_time = time.time()
    if method == 'mean':
        comp_out = da.nanmean(stacked, axis=0, keepdims=True).compute()
    elif method == 'median':
        comp_out = da.nanmedian(stacked, axis=0, keepdims=True).compute()
    elif method == 'max':
        comp_out = da.nanmax(stacked, axis=0, keepdims=True).compute()
    elif method == 'min':
        comp_out = da.nanmin(stacked, axis=0, keepdims=True).compute()
    else:
        raise Exception('{} is not a valid compositing '
                        'method!'.format(method))

    # ----------------------------------------------------------------------------
    # SAVE RESULTS TO FILES
    # ----------------------------------------------------------------------------
    # Save composite to GeoTIFF
    tif_time = time.time()
    print("#\n# Saving composite image to TIFF...")

    out_nam = save_nam + ".tif"
    out_pth = os.path.join(save_loc, out_nam)
    out_meta.update(bigtiff="yes", compress='lzw')

    with rasterio.open(out_pth, "w", **out_meta) as dest:
        dest.write(comp_out)

    tif_time = time.time() - tif_time
    print(f"#  Time (TIFF): {tif_time:.2f} seconds")

    # Save preview file as JPEG
    jpg_time = time.time()
    print("#\n# Saving preview image to JPEG...")
    # Pickle array for passing it to plot_preview()
    spt = os.path.join(save_loc, "temp_array.p")
    with open(spt, "wb") as pf:
        pickle.dump(comp_out, pf)
    comp_out = None
    try:
        plot_preview(spt, dt, out_pth[:-3] + "jpg")
    except MemoryError as me:
        print("#  Memory error occurred, could not save to JPEG")
        print(me)
    finally:
        # delete pickle
        os.remove(spt)
    jpg_time = time.time() - jpg_time
    print(f"#  Time (JPEG): {jpg_time:.2f} seconds")


if __name__ == "__main__":
    # ========================================================================
    # TEMPORARY INPUT
    # ========================================================================
    # Select from: mean, median, max, min
    in_method = 'mean'

    in_save_loc = ".\\composite_test_01"
    in_save_nam = "test_02"

    # bbox = None
    #        # xL    # yD    # xR    # yU
    in_bbox = [0, 305400, 287100, 625100]

    # List of paths to input files
    in_fps = ["C:\\Users\\ncoz\\GitHub\\slc_processing\\tmp2\\one_image_38C8_ASC_VV.tif",
              "C:\\Users\\ncoz\\GitHub\\slc_processing\\tmp2\\second_image_DD0A_ASC_VV.tif"]

    # Run composite with timer
    t_tim_b = time.time()
    composite(in_fps, in_save_loc, in_save_nam, in_method, dt="SIG")
    t_tim_b = time.time() - t_tim_b
    print(f"\n~~~~~ Total time: {t_tim_b:.2f} seconds ~~~~~\n")
