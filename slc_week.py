# -*- coding: utf-8 -*-
"""
Created on Thu Oct 8 10:51:17 2020

@author: ncoz

Routine for preparation of SLC data for EO Patches in project AiTLAS.
It prepares mean weekly mosaics for Coherence and Sigma data. Each weekly
product will consist of 8 files:
- Coherence ASC VV
- Coherence ASC VH
- Coherence DES VV
- Coherence DES VH
- Sigma ASC VV
- Sigma ASC VH
- Sigma DES VV
- Sigma DES VH

Data preparation steps:
i  ) Split time period into weeks (default is 6 day week)
ii ) Find all files within a week
iii) Filter for direction (ASC, DES) and polarization (VV, VH)
iv ) Within one week find all files with the same timestamp
v  ) Stitch together all time stamps into a single image
vi ) Resample (bilinear) and target aligned pixels to match with S-2 raster
vii) Create mean weekly mosaic from all resampled images for that week
"""

import glob
import os
import rasterio
import time
from datetime import datetime, timedelta
from shutil import rmtree

import numpy as np
from osgeo import gdal
from scipy.ndimage import binary_dilation

from composite_dask import composite
from tif2jpg import tif2jpg


class WeekList:
    """Creates an object that contains a list of time intervals required for
    weekly mosaics for S-1 SLC data.
    """
    def __init__(self, start, end, step):
        # Boundary dates and time step (N-day week)
        self.start = start
        self.end = end
        self.step = step

        # Create a dictionary containing all N-day weeks in a selected year
        current_year = start[:4]
        start_yr = datetime.strptime(current_year + "0101", "%Y%m%d")
        end_yr = datetime.strptime(current_year + "1231", "%Y%m%d")
        st_dt = datetime.strptime(start, "%Y%m%d")
        en_dt = datetime.strptime(end, "%Y%m%d")

        interval_start = start_yr
        week_no = 0
        yr_wks = []
        while interval_start <= end_yr:
            interval_end = interval_start + timedelta(days=step - 1)
            # Set to 31-Dec if it overflows into the next year
            if interval_end.year != int(current_year):
                interval_end = end_yr
            week_no += 1
            yr_wks.append({
                "week": week_no,
                "start": interval_start,
                "end": interval_end
            })
            interval_start += timedelta(days=step)
        self.week_list_in_year = yr_wks

        # Filter out only the required weeks
        sel_wks = [a for a in yr_wks if (a['start'] >= st_dt and
                                         a['end'] <= en_dt)
                   or (a['start'] <= st_dt <= a['end'])
                   or (a['start'] >= en_dt >= a['end'])]
        self.week_list = sel_wks

        # Number of weeks selected for processing
        self.number_of_weeks = len(sel_wks)

        # Number of weeks in a calendar year
        self.number_of_weeks_in_year = len(yr_wks)


def days_in_week(one_week):
    """Return a list of all days (string) contain in that week."""
    # one_week = self.week_list[w_no]
    delta = one_week["end"] - one_week["start"]  # as timedelta
    list_of_days = []
    for i in range(delta.days + 1):
        day = one_week["start"] + timedelta(days=i)
        list_of_days.append(day.strftime("%Y%m%d"))

    return list_of_days


def make_save_folder(week_from_dict, dt, save_path):
    """Creates and returns path to a sub-folder for saving weekly products."""
    start_date = week_from_dict["start"].strftime("%Y%m%d")
    end_date = week_from_dict["end"].strftime("%Y%m%d")
    yr = week_from_dict["start"].strftime("%Y")[2:]
    wk = week_from_dict["week"]
    save_name = f"yr{yr}wk{wk:02}_SLC_{dt}_{start_date}_{end_date}_weekly"
    save_loc = os.path.join(save_path, save_name)
    os.makedirs(save_loc, exist_ok=True)

    return save_loc


def find_individual_images(list_of_days, src, direction, dt):
    """Returns a list of (DATE, IMAGE NAME) pairs and source folder path.

    For each DATE in a given week, the function searches the source folder and
    finds names of individual products. Each INDIVIDUAL PRODUCT consists of
    multiple sub-images (bursts).

    The reason why source folder path is returned is because of a slightly
    different folder structures between SIG and COH.
    """
    out_image_with_list = []
    for one_day in list_of_days:

        # For coherence first find the correct sub-folder
        if dt == "COH":
            one_month = one_day[:4] + "-" + one_day[4:6]
            src_month = os.path.join(src, f"*{dt}*{one_month}")
        else:
            one_year = one_day[:4]
            src_month = os.path.join(src, f"*{dt}*{one_year}")

        search_day = os.path.join(src_month, one_day + f"*{direction}*")
        all_available = glob.glob(search_day)
        # This step filters out .dim files, so we are only left with folders
        all_available = [fnm for fnm in all_available if not fnm.endswith('.dim')]
        sole_images = []
        if all_available:
            # FIND INDIVIDUAL IMAGES
            for sole in all_available:
                sole_name = os.path.basename(sole)[:32]
                if sole_name not in sole_images:
                    sole_images.append(sole_name)

            # FIND ALL PATHS TO ONE INDIVIDUAL IMAGE
            for image in sole_images:
                matching = [s for s in all_available if image in s]
                out_image_with_list.append((image, matching))

    return out_image_with_list


def pre_process_bursts(bursts_list, polarity, folder_pth, bbox=None):
    """Prepares input images (bursts) for processing and returns list of paths.

        For each burst:
        1)  Sets path to pre-processed image
        1a) Skips if image is out of bounds [time saving]
        1b) New output bounds if only partial overlap [time saving]
        2)  Deal with nodata (all nodata should be 0)
        3)  Test if there are any "nodata stripes" across the image
        3a) If yes, then first erode by a couple pixels
        3b) Use GDAL fill nodata to interpolate missing data
        4)  Erode the edges of the raster (remove dark pixels)
    """
    paths = []
    for i, burst in enumerate(bursts_list):
        print(f"{i+1}", end="")

        # Determine full file name
        p = os.path.join(burst, f"*{polarity}*.img")
        burst_file = glob.glob(p)[0]

        # Check if extents overlap with AOI (if bbox was assigned)
        if bbox:
            with rasterio.open(burst_file) as rio:
                # Extents of the burst
                bbr = rio.bounds
            is_overlapping = (
                    bbr.left < bbox[2] and bbox[0] < bbr.right and
                    bbr.bottom < bbox[3] and bbox[1] < bbr.top)
            out_bounds = list(bbr)
            if bbr.left < bbox[0]:
                out_bounds[0] = bbox[0]
            if bbr.bottom < bbox[1]:
                out_bounds[1] = bbox[1]
            if bbr.right > bbox[2]:
                out_bounds[2] = bbox[2]
            if bbr.top > bbox[1]:
                out_bounds[3] = bbox[3]
        else:
            is_overlapping = True
            out_bounds = None

        if is_overlapping:
            # Store paths of output, so they can be used in the nex step
            image_name = f"{i:02d}_" + os.path.basename(burst_file)[:-4] + ".tif"
            out_burst = os.path.join(folder_pth, image_name)
            paths.append(out_burst)

            # Set all nodata to 0 (there are both 0 and nan values present)
            ds = gdal.Warp(out_burst, burst_file, srcNodata=np.nan,
                           dstNodata=0, multithread=True,
                           outputBounds=out_bounds)
            ds = None

            # Open raster for further processing
            r = gdal.Open(out_burst, gdal.GA_Update)  # gdal.GA_Update: save output to the source file
            raster_arr = r.GetRasterBand(1).ReadAsArray()
            warp_iter = 10  # By default erode edges by 10 pixels

            # Test for nodata "stripes" (by reading a random column and counting nodata intervals
            test_column = raster_arr[:, raster_arr.shape[1] // 2]
            a_zeros = np.where(test_column == 0)[0]
            a_groups = np.split(a_zeros, np.where(np.diff(a_zeros) != 1)[0] + 1)

            # More than 2 nodata intervals means there is a nodata stripe present
            if len(a_groups) > 2:
                # Find the width of nodata pixels
                px_wid = len(a_groups[1])
                # First erode by 3 pixels to remove dark pixels on edge of strip
                nodata_mask = raster_arr == 0
                dilated_mask = binary_dilation(nodata_mask, iterations=3)
                raster_arr[dilated_mask] = 0

                # Prepare raster band to be used by fill nodata
                r.GetRasterBand(1).WriteArray(raster_arr)
                raster_bnd = r.GetRasterBand(1)
                # Preform fill nodata on the array
                ds = gdal.FillNodata(raster_bnd, maskBand=None,
                                     maxSearchDist=px_wid+3, smoothingIterations=0,
                                     callback=None)
                ds = None

                # Open band as array to be dilated in the next step
                raster_arr = raster_bnd.ReadAsArray()
                # Also erode pixels that were added with FillNodata
                warp_iter += px_wid

            # Remove dark pixels on the edge of each raster
            nodata_mask = raster_arr == 0
            dilated_mask = binary_dilation(nodata_mask, iterations=warp_iter)
            raster_arr[dilated_mask] = 0

            r.GetRasterBand(1).WriteArray(raster_arr)
            # noinspection PyUnusedLocal
            r = None

            print(f"X ", end="")
        else:
            # Message next to the burst number if image is out of bounds
            print(f":n/a ", end="")
    return paths


def make_individual_rasters(to_aggregate, direct, polar, tmp_folder, bbox=None):
    """Prepares all individual products from one week for compositing.

    Parameters
    ----------
    to_aggregate: list(tuple(str, list))
        List of tuples, with first element being a product and second a list of
        paths to all corresponding sub-products (folders containing *VV.img anf
        *VH.img files).
    direct : str
        Orbit direction, either ASC for Ascending or DES for Descending.
    polar : str
        Polarity, either VV or VH for S-1 SLC products
    tmp_folder : str
        Path for saving outputs.
    bbox : list
        Output extents in the [x_min, y_min, x_max, y_max] format

    Returns
    -------
    final_paths : list
        List of paths to the prepared products.

    Notes
    _____
        - reads rasters (.img format) from network drive
        - create temp intermediate products with pre_process_bursts()
            * use warp to set nodata
            * fill nodata lines between some bursts
            * dilate "nodata area", e.i. cut edges to remove dark pixels
        - temporary files are stored to local drive
        - final products are stored to local drive as GeoTIFFs

    """
    # Make sure output folder exist
    os.makedirs(tmp_folder, exist_ok=True)

    # Process all individual images (warp to single file)
    final_paths = []
    for product, bursts in to_aggregate:
        tta1 = time.time()
        print(f"\n     Pre-processing {product}")

        # Pre-process "bursts" for warping into a single image
        # to_be_warped is a LIST OF PATHS to individual product folders
        print(f"        - consists of {len(bursts)} bursts\n        ", end="")
        to_be_warped = pre_process_bursts(bursts, polar, tmp_folder, bbox=bbox)

        if to_be_warped:
            # WARP BURSTS INTO SINGLE IMAGE
            out_image = os.path.join(tmp_folder, product + f"_{direct}_{polar}.tif")
            final_paths.append(out_image)
            print(f"\n        - warping into a single image")

            # Resample to 10m using bilinear interpolation and align pixels to grid
            # Also crop to extents - all files should have the same extents (outputBounds)
            ds = gdal.Warp(out_image, to_be_warped,
                           xRes=10, yRes=10,
                           dstNodata=0, targetAlignedPixels=True,
                           resampleAlg=gdal.gdalconst.GRA_Bilinear,
                           multithread=True, outputBounds=bbox,
                           options=['TILED=YES', 'BLOCKXSIZE=512', 'BLOCKYSIZE=512'])
            ds = None

            # REMOVE TEMPORARY FILES ("bursts")
            for file in to_be_warped:
                os.remove(file)

            tta1 = time.time() - tta1
            print(f"        [Time (individual image): {tta1:.2f} sec.]")
        else:
            print(f"\n        - no images inside bounds... SKIPPING")

    return final_paths


def loop_weeks(dt_start, dt_end, dt_step, bbox, data_type,
               src_folder, save_loc,
               combinations=None, country_border=None):
    # Create object for finding time intervals for processing
    my_weeks = WeekList(dt_start, dt_end, dt_step)

    # PROCESS FOR ONE WEEK
    for this_week in my_weeks.week_list:
        tta_week = time.time()

        # CREATE NEW FOLDER FOR SAVING WEEKLY PRODUCTS
        week_path = make_save_folder(this_week, data_type, save_loc)
        temp_path = ".\\tmp2"

        print(f"\nProcessing {os.path.basename(week_path)}")

        # Initialize LOG
        timestr = time.strftime("%Y%m%d-%H%M%S")
        log_name = f"log_{timestr}.txt"
        log_name = os.path.join(week_path, log_name)
        with open(log_name, "w") as log:
            title_str = f"# Log of {os.path.basename(week_path)} #"
            log.write("#" * len(title_str) + "\n")
            log.write(title_str + "\n")
            log.write("#" * len(title_str) + "\n")

            current_time = time.strftime("%a, %d %b %Y %H:%M:%S")
            log.write("\n")
            log.write(f"Time started: {current_time}\n")

            log.write("\n")
            log.write("Save location:\n")
            log.write(week_path + "\n")
            log.write("\n")
            log.write("Geo. extents [minx, miny, maxx, maxy]:\n")
            log.write(f"{bbox}\n")
            log.write("\n")

        # LOOP OVER ALL 4 PRODUCT COMBINATIONS
        if combinations is None:
            combinations = [
                ("DES", "VV"),
                ("DES", "VH"),
                ("ASC", "VV"),
                ("ASC", "VH")
            ]
        for direct, polar in combinations:
            t_combo = time.time()
            print(f"  Now processing combo: {direct} {polar}")

            # Create folder for saving
            tmp_f = os.path.join(temp_path, direct + "_" + polar)
            os.makedirs(tmp_f, exist_ok=True)

            # Filter list for dates within this week
            diw = days_in_week(this_week)  # diw = Days In Week (list)

            # Find individual images for that day
            to_aggregate = find_individual_images(diw, src_folder, direct,
                                                  data_type)

            # LOG INPUT FILES
            with open(log_name, "a") as log:
                log.write(f"Source products for {direct} {polar}:\n")
                for prod1, prod2 in to_aggregate:
                    log.write(f" - {prod1}\n")
                    [log.write(f"   -> {a}\n") for a in prod2]
                log.write("\n")

            # ==================================================================
            # PROCESS INDIVIDUAL IMAGES
            paths_for_composite = make_individual_rasters(to_aggregate, direct,
                                                          polar, tmp_f, bbox=bbox)
            t_combo = time.time() - t_combo
            print(f"\n  Finished combo {direct} {polar} in {t_combo:.2f} sec.")

            # ==================================================================
            # CREATE COMPOSITE
            tta2 = time.time()
            if paths_for_composite:
                print(f"\nCreating composite for {direct} {polar} {data_type} in {diw[0]}")
                tww = this_week["week"]
                composite_name = f"{diw[0]}_{diw[-1]}_weekly_SLC_{data_type}" \
                                 f"_{direct}_{polar}_yr{diw[0][2:4]}wk{tww:02}"
                tif = composite(paths_for_composite, week_path, composite_name,
                                method="mean", dt=data_type)
                # CREATE JPG PREVIEW
                tif2jpg(tif, country_border)
                tta2 = time.time() - tta2
                print(f"#\n# Time (composite + preview file): {tta2:.2f} sec.\n")
            else:
                print("\nNo images available for this combo!\n# SKIPPED!\n")

            # Remove temporary folder
            rmtree(tmp_f, ignore_errors=True)

        # Print time for processing one week
        tta_week = time.time() - tta_week
        tw = this_week["start"].strftime("%Y%m%d")
        print(f"~~~~ Time for week {tw}: {tta_week:.2f} sec. ~~~~")

    return "\n################ Finished processing! ################"


if __name__ == "__main__":
    # ----- INPUT --------------------------------------------------------------
    # Create list of weekly intervals (6 days per week)
    # in_start = "20170301"
    # in_end = "20170301"
    in_start = "20170419"
    in_end = "20171231"
    in_step = 6

    in_type = "SIG"  # COH or SIG

    # MAKE SURE THE CORRECT CRS IS USED FOR EXTENTS!!!!
    # This bbox is outline of SLO with 5 km buffer in EPSG:32633
    # bbox = [368930, 5024780, 627570, 5197200]
    # bbox for Netherlands in EPSG:28992
    in_bbox = [0, 305400, 287100, 625100]  # NL full
    # in_bbox = [90000, 311000, 140000, 554591]  # NL partially out of bounds
    # in_bbox = [387200, 740000, 400000, 840000]  # NL completely out of bounds

    in_comb = None
    # combinations = [
    #   ("DES", "VV"),
    #   ("DES", "VH"),
    #   ("ASC", "VV"),
    #   ("ASC", "VH")
    # ]

    # Source folder
    # in_src = "d:\\slc\\S1_SLC_processing_COHERENCE_2017-03"
    # in_src = "o:\\ZRSVN_Travinje_SI_coh_UTM33N_13.91m"
    # in_src = "r:\\Sentinel-1_SLC_products_SI_coherence_13.91m_UTM33N"
    # in_src = "r:\\Sentinel-1_SLC_products_SI_sigma_10m_UTM33N"
    # in_src = "r:\\Sentinel-1_SLC_products_AiTLAS_NL_coh_10m_Amersfoort"
    in_src = "q:\\_S1_SLC_products_NL_sig_10m_Amersfoort"

    # Save location
    in_save = "d:\\aitlas_slc_test_NL_2"
    # in_save = "o:\\aitlas_slc_SI_coherence"
    # in_save = "o:\\aitlas_slc_SI_sigma"
    # in_save = "o:\\aitlas_slc_NL_coherence"
    # in_save = "o:\\aitlas_slc_NL_sigma"
    # --------------------------------------------------------------------------

    result = loop_weeks(in_start, in_end, in_step, in_bbox,
                        in_type, in_src, in_save, in_comb)
    print(result)
