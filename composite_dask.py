# -*- coding: utf-8 -*-
"""
Created on Fri Oct 2 11:10:03 2020

@author: ncoz

A modified version of the compositing algorithm for creation of temporal mosaics
using the Dask Array package.
"""

import math
import os
import pickle
import time
from shutil import rmtree

import dask.array as da
import numpy as np
import rasterio
from affine import Affine
from rasterio.windows import Window

from tif2jpg import plot_preview


def round_multiple(nr, x_left, pix):
    """Rounds to the nearest multiple of the raster."""
    return pix * round((nr - x_left) / pix) + x_left


def is_list_uniform(check_list, msg):
    """Checks if all items in the list are the same, and raises an exception
    if not;
    i.e. item[0] == item[1] == item[2] == etc.

    Parameters
    ----------
    check_list : list
        List that will be evaluated.
    msg : string
        Error message that will be displayed.

    Raises
    ------
    Exception
        Custom message for the exception.

    Returns
    -------
    None.

    """
    check = check_list.count(check_list[0]) == len(check_list)
    if not check:
        raise Exception(msg)


def output_image_extent(src_fps, bbox):
    """Determines the maximum extents of the output image, taking into account
    extents of all considered files and a user specified bounding box.

    Parameters
    ----------
    src_fps : list
        List of file paths to input TIFs.
    bbox : list
        Extents in order [xL, yD, xR, yU].

    Raises
    ------
    Exception
        Error is raised if bounding box doesn't overlap one of the images.
        Future plan: exclude that image from file list??

    Returns
    -------
    output : dictionary
        Contains extents of and other metadata required for final image.

    """
    geo_ext_time = time.time()
    print("# Evaluating geographical extents...")

    # Open TIF files as DataSets and evaluate properties
    tif_ext = []
    pix_res = []
    # src_all = []
    bnd_num = []

    for fp in src_fps:
        with rasterio.open(fp) as src:
            # src_all.append(src)

            # Read raster properties
            tif_ext.append([i for i in src.bounds])  # left, bottom, right, top
            pix_res.append(src.res)
            bnd_num.append(src.count)

    # Check if all images have the same pixel size
    is_list_uniform(pix_res, 'Pixel size of input images not matching.')

    # Check if all images have the same number of bands
    is_list_uniform(bnd_num, 'Number of bands in input images not matching.')

    # Pixel size
    pix_x, pix_y = pix_res[0]

    # FIND MAX EXTENTS AND DETERMINE SIZE OF OUTPUT IMAGE
    x_l_out = min((lst[0] for lst in tif_ext))
    x_r_out = max((lst[2] for lst in tif_ext))
    y_d_out = min((lst[1] for lst in tif_ext))
    y_u_out = max((lst[3] for lst in tif_ext))

    if bbox:
        # Round bbox to nearest multiple of raster
        x_l_bbox = round_multiple(bbox[0], x_l_out, pix_x)
        y_d_bbox = round_multiple(bbox[1], y_u_out, pix_y)
        x_r_bbox = round_multiple(bbox[2], x_l_out, pix_x)
        y_u_bbox = round_multiple(bbox[3], y_u_out, pix_y)

        # Break if bbox falls out of image extents
        chk_bbox = (x_l_out > x_r_bbox or y_d_out > y_u_bbox or
                    x_r_out < x_l_bbox or y_u_out < y_d_bbox)
        if chk_bbox:
            raise Exception('BBOX out of image extents')

        # Compare with image extents
        x_l_out = max(x_l_out, x_l_bbox)
        y_d_out = max(y_d_out, y_d_bbox)
        x_r_out = min(x_r_out, x_r_bbox)
        y_u_out = min(y_u_out, y_u_bbox)

    # Calculate size of output array
    tif_wide = int(math.ceil(x_r_out - x_l_out) / abs(pix_x))
    tif_high = int(math.ceil(y_u_out - y_d_out) / abs(pix_y))
    nr_bands = bnd_num[0]
    nr_image = len(src_fps)

    output = {'width': tif_wide,
              'height': tif_high,
              'bandsCount': nr_bands,
              'imgCount': nr_image,
              'bounds': [x_l_out, y_d_out, x_r_out, y_u_out],
              'pixels': (pix_x, pix_y)
              }

    # Time evaluating geo. extents
    geo_ext_time = time.time() - geo_ext_time
    print(f"#   time: {geo_ext_time:.2f} seconds")
    return output


def image_offset(out_ext, src_ds):
    # Output image extents
    x_l_out, y_d_out, x_r_out, y_u_out = out_ext

    # Load metadata from source dataset
    x_col = src_ds.meta['width']
    y_row = src_ds.meta['height']

    # Extents of image we are reading
    x_l, y_d, x_r, y_u = [xy for xy in src_ds.bounds]
    # Read pixel resolution
    pix_x, pix_y = src_ds.res

    # X-direction
    if x_l >= x_l_out:
        # Offset
        win_x = 0
        off_x = int((x_l - x_l_out) / abs(pix_x))

        # Width
        bbx = int((x_r_out - x_l) / pix_x)
        len_x = min(x_col, bbx)

    else:
        # Offset
        win_x = int((x_l_out - x_l) / pix_x)
        off_x = 0

        # Width
        bb1 = int((x_r - x_l_out) / pix_x)  # src < out
        bb2 = int((x_r_out - x_l_out) / pix_x)  # src > out
        len_x = min(bb1, bb2)

    # Y-direction
    if y_u <= y_u_out:
        # Offset
        win_y = 0
        off_y = int((y_u_out - y_u) / abs(pix_y))

        # Height
        bby = int((y_u - y_d_out) / pix_y)
        len_y = min(y_row, bby)

    else:
        # Offset
        win_y = int((y_u - y_u_out) / pix_y)
        off_y = 0

        # Height
        bb1 = int((y_u_out - y_d) / pix_y)
        bb2 = int((y_u_out - y_d_out) / pix_y)
        len_y = min(bb1, bb2)

    # Prepare Window for reading raster from TIF
    rd_win = Window(win_x, win_y, len_x, len_y)
    # Prepare intervals for slicing
    slicex = [off_x, (off_x + len_x)]
    slicey = [off_y, (off_y + len_y)]

    # Calculate index for inserting image into output array (and Window)
    return rd_win, slicex, slicey


def composite(src_fps, save_loc, save_nam, method="mean", bbox=None, dt="default"):
    """


    :param src_fps: list of paths
    :param save_loc:
    :param save_nam:
    :param method:
    :param bbox:
    :param dt:
    :return:
    """
    # CREATE SAVE LOCATION
    os.makedirs(save_loc, exist_ok=True)

    # Get extents
    main_extents = output_image_extent(src_fps, bbox)

    # Obtain properties of output array (same for all bands/images)
    out_extents = main_extents['bounds']
    x_l_out, y_d_out, x_r_out, y_u_out = out_extents
    out_w = main_extents['width']
    out_h = main_extents['height']
    nr_bands = main_extents['bandsCount']

    # Initiate output array
    comp_out = np.full((1, out_h, out_w), np.nan, dtype=np.float32)

    # Create temp dir if it doesn't exist
    sav_dir = '.\\tmp'
    if not os.path.exists(sav_dir):
        os.mkdir(sav_dir)

    # Save TIFF metadata for output
    with rasterio.open(src_fps[0]) as rst:
        out_meta = rst.profile.copy()

    # MAIN LOOP FOR COMPOSITING
    tmp_sav_pth = []
    for band in range(nr_bands):
        print(f"#\n# Creating composite for Band {band+1}")
        comp_stack = []
        # Loop all images
        for i, fp in enumerate(src_fps):
            img_time = time.time()
            print(f"#   Processing Image {i + 1}")

            # Open raster and read the correct subset of the image
            with rasterio.open(fp) as src:
                # Skip Reading the image if bbox is out of bounds
                x_l, y_d, x_r, y_u = [xy for xy in src.bounds]
                chk_bbox = (x_l > x_r_out or y_d > y_u_out or
                            x_r < x_l_out or y_u < y_d_out)
                if chk_bbox:
                    print(f"#   Image {i} not included (out of bounds)!")
                    break

                # Calculate offset for reading and slicing
                win, sl_x, sl_y = image_offset(out_extents, src)

                # Set offset Window for reading of TIF subset
                offset = win

                # Initiate array for output
                comp_band = np.full((out_h, out_w), np.nan, dtype=np.float32)

                # Read image and save to pickle
                print("#     Reading the image...")
                if band == 0:
                    tmp_read = src.read(window=offset)
                    for nc in range(1, nr_bands):
                        img_nam = ('img' + str(i+1).zfill(2) + "_b"
                                   + str(nc+1).zfill(2) + '.p')
                        img_pth = os.path.join(sav_dir, img_nam)
                        with open(img_pth, "wb") as pf:
                            pickle.dump(tmp_read[nc], pf)
                    tmp_read = tmp_read[0]
                else:
                    img_nam = ('img' + str(i+1).zfill(2) + "_b"
                               + str(band+1).zfill(2) + '.p')
                    img_pth = os.path.join(sav_dir, img_nam)
                    with open(img_pth, "rb") as pf:
                        tmp_read = pickle.load(pf)

                # Apply nodata mask
                nodata_mask = tmp_read == 0
                tmp_read[nodata_mask] = np.nan
                nodata_mask = None

                # Read the image into the array
                comp_band[sl_y[0]:sl_y[1], sl_x[0]:sl_x[1]] = tmp_read

                # Cleanup arrays
                tmp_read = None

            # Stack comp_band array into Dask Array
            comp_stack.append(da.from_array(comp_band, chunks=(1024, 1024)))

            # Close the array to save memory
            comp_band = None

            # Time processing single image
            img_time = time.time() - img_time
            print(f"#     Time: {img_time:.2f} seconds")

        # Stack all images into 1 array
        stacked = da.stack(comp_stack, axis=0)
        comp_stack = None

        # Calculate composite for selected method with dask
        print(f"# Compositing Band {band+1}")
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
        stacked = None
        bnd_time = time.time() - bnd_time
        print(f"#   Band {band+1} time: {bnd_time:.2f} seconds")

        # After one band is resolved, save to temp file and release memory by
        # deleting the array
        if nr_bands > 1:

            print(f"# Saving temporary composite file for this band.")

            # Create file name and save using pickle
            sav_fil = 'b_' + str(band+1).zfill(2) + '.p'
            sav_pth = os.path.join(sav_dir, sav_fil)
            with open(sav_pth, "wb") as pf:
                pickle.dump(comp_out, pf)

            # Add to savePth list with filenames
            tmp_sav_pth.append(sav_pth)

            #  Clean up workspace
            comp_out = None

    # ----------------------------------------------------------------------------
    # OUT OF THE COMPOSITE LOOP RESTORE SAVED FILES AND BUILD TIF
    # ----------------------------------------------------------------------------
    if nr_bands > 1:

        print("# Restoring saved bands.")
        rst_time = time.time()

        # Initiate output array
        comp_out = np.full((nr_bands, out_h, out_w), np.nan, dtype=np.float32)

        for bnd, pth in enumerate(tmp_sav_pth):
            with open(pth, "rb") as pf:
                comp_out[bnd, :, :] = pickle.load(pf)

        # Remove temporary folder
        rmtree(sav_dir, ignore_errors=True)
        rst_time = time.time() - rst_time
        print(f"   Restoration time: {rst_time:.2f} seconds")

    # ----------------------------------------------------------------------------
    # SAVE RESULTS TO TIF
    # ----------------------------------------------------------------------------
    print("#\n# Saving composite image to TIFF.")
    tif_time = time.time()

    # Save composite
    out_nam = save_nam + ".tif"
    out_pth = os.path.join(save_loc, out_nam)

    out_px = out_meta["transform"][0]
    out_py = out_meta["transform"][4]
    out_trans = Affine(out_px, 0.0, x_l_out, 0.0, out_py, y_u_out)

    out_meta.update(
        height=comp_out.shape[1], width=comp_out.shape[2],
        transform=out_trans, bigtiff="yes", compress='lzw'
        )

    with rasterio.open(out_pth, "w", **out_meta) as dest:
        dest.write(comp_out)

    tif_time = time.time() - tif_time
    print(f"#  Time (TIFF): {tif_time:.2f} seconds")

    jpg_time = time.time()
    print("#\n# Saving preview image to JPEG.")
    # Pickle array for passing it to plot_preview()
    spt = os.path.join(save_loc, "temp_array.p")
    with open(spt, "wb") as pf:
        pickle.dump(comp_out, pf)
    comp_out = None

    # ADD JPEG PREVIEW FILE
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

    in_save_loc = ".\\composite_test"
    in_save_nam = "test_01"

    # bbox = None
    #        # xL    # yD    # xR    # yU
    in_bbox = [432000, 5060000, 532000, 5160000]

    # List of paths to input files
    in_fps = ['d:\\slc\\coherence\\week_01__20170301\\DES_VV\\20170301T050959_S1A_3F87_DES_VV.tif',
              'd:\\slc\\coherence\\week_01__20170301\\DES_VV\\20170301T051024_S1A_4E67_DES_VV.tif',
              'd:\\slc\\coherence\\week_01__20170301\\DES_VV\\20170302T050117_S1B_A80C_DES_VV.tif',
              'd:\\slc\\coherence\\week_01__20170301\\DES_VV\\20170302T050142_S1B_A5C9_DES_VV.tif',
              'd:\\slc\\coherence\\week_01__20170301\\DES_VV\\20170306T051829_S1A_91F4_DES_VV.tif',
              'd:\\slc\\coherence\\week_01__20170301\\DES_VV\\20170306T051854_S1A_2222_DES_VV.tif']

    # Run composite with timer
    t_tim_b = time.time()
    composite(in_fps, in_save_loc, in_save_nam, in_method)
    t_tim_b = time.time() - t_tim_b
    print(f"\n~~~~~ Total time: {t_tim_b:.2f} seconds ~~~~~\n")
