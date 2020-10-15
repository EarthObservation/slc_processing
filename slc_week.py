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
vi ) Resample (nearest neighbor) and target aligned pixels to match with S-2 raster
vii) Create mean weekly mosaic from all resampled images for that week
"""

import glob
import os
import time
from datetime import datetime, timedelta
from shutil import rmtree

import numpy as np
from osgeo import gdal
from scipy.ndimage import binary_dilation

from composite_dask import composite


class WeekList:
    """Creates an object that contains a list of time intervals required for
    weekly mosaics for S-1 SLC data.
    """
    def __init__(self, start, end, step):
        self.start = start
        self.end = end
        self.step = step

        start_date = datetime.strptime(start, "%Y%m%d")
        end_date = datetime.strptime(end, "%Y%m%d")

        interval_start = start_date
        week_no = 0
        week_list = []
        while interval_start <= end_date:
            interval_end = interval_start + timedelta(days=step - 1)
            week_no += 1
            week_list.append({
                "week": week_no,
                "start": interval_start,
                "end": interval_end
            })
            interval_start += timedelta(days=step)

        self.week_list = week_list
        self.number_of_weeks = len(week_list)

    def days_in_week(self, w_no):
        """Return a list of all days (string) contain in that week."""
        one_week = self.week_list[w_no]
        delta = one_week["end"] - one_week["start"]  # as timedelta
        list_of_days = []
        for i in range(delta.days + 1):
            day = one_week["start"] + timedelta(days=i)
            list_of_days.append(day.strftime("%Y%m%d"))

        return list_of_days


def make_save_folder(week_from_dict, save_path):
    """Creates and returns path to a sub-folder for saving weekly products."""
    start_date = week_from_dict["start"].strftime("%Y%m%d")
    end_date = week_from_dict["end"].strftime("%Y%m%d")
    save_name = f"weekly_{start_date}_{end_date}"
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
            src_month = os.path.join(src, f"*{dt}*{one_month}*")
        else:
            src_month = src

        search_day = os.path.join(src_month, one_day + f"*{direction}*{dt}*")
        all_available = glob.glob(search_day)
        sole_images = []
        if all_available:
            # FIND INDIVIDUAL IMAGES
            for sole in all_available:
                sole_name = os.path.basename(sole)[:24]
                if sole_name not in sole_images:
                    sole_images.append(sole_name)

            # FIND ALL PATHS TO ONE INDIVIDUAL IMAGE
            for image in sole_images:
                matching = [s for s in all_available if image in s]
                out_image_with_list.append((image, matching))

    return out_image_with_list


def pre_process_bursts(bursts_list, polarity, folder_pth):
    """Prepares input images (bursts) for processing and returns list of paths.

        For each burst:
        i)   Sets path to pre-processed image
        ii)  Deal with nodata (all nodata should be 0)
        iii) Erode the edges of the raster (remove dark pixels)
    """
    paths = []
    for burst in bursts_list:
        # REM: burst = bursts[1]
        p = os.path.join(burst, f"*{polarity}.img")
        burst_file = glob.glob(p)[0]
        image_name = os.path.basename(burst_file)[:-4] + ".tif"

        out_burst = os.path.join(folder_pth, image_name)
        paths.append(out_burst)

        # Set all nodata to 0 (there are both 0 and nan values present)
        gdal.Warp(out_burst, burst_file, srcNodata=np.nan, dstNodata=0)

        # Remove dark pixels on the edge of each raster (erode by 10 pixels)
        r = gdal.Open(out_burst, gdal.GA_Update)
        raster_arr = np.array(r.GetRasterBand(1).ReadAsArray())

        nodata_mask = raster_arr == 0
        dilated_mask = binary_dilation(nodata_mask, iterations=10)
        raster_arr[dilated_mask] = 0

        r.GetRasterBand(1).WriteArray(raster_arr)
        # noinspection PyUnusedLocal
        r = None

        print(f"X ", end="")

    return paths


def get_weekly_slc(dt_start, dt_end, dt_step, data_type, src_folder, save_loc):
    # Create object for finding time intervals for processing
    my_weeks = WeekList(dt_start, dt_end, dt_step)

    # PROCESS FOR ONE WEEK
    for this_i, this_week in enumerate(my_weeks.week_list):
        # REM: this_week = my_weeks.week_list[0]
        # REM: this_i = 0

        # CREATE NEW FOLDER FOR SAVING WEEKLY PRODUCTS
        week_path = make_save_folder(this_week, save_loc)

        tta_week = time.time()
        print(f"\nProcessing {os.path.basename(week_path)}")

        # LOOP OVER ALL 4 PRODUCT COMBINATIONS
        # combinations = [("ASC", "VV"), ("ASC", "VH")]  # REM
        combinations = [("DES", "VV"), ("DES", "VH"), ("ASC", "VV"), ("ASC", "VH")]
        for direct, polar in combinations:
            tta_combo = time.time()
            print(f"  Now processing combo: {direct} {polar}")

            # Create folder for saving
            product_folder = os.path.join(week_path, direct + "_" + polar)
            os.makedirs(product_folder, exist_ok=True)

            # Filter list for dates within this week
            diw = my_weeks.days_in_week(this_i)  # diw = Days In Week (list)

            # Find individual images for that day
            to_aggregate = find_individual_images(diw, src_folder, direct, data_type)

            # Process all individual images (warp to single file)
            # REM: product = to_aggregate[0]
            for product, bursts in to_aggregate:
                tta1 = time.time()
                print(f"\n     Pre-processing {product}")

                # Pre-process "bursts" for warping into a single image
                print(f"        - consists of {len(bursts)} bursts\n        ", end="")
                to_be_warped = pre_process_bursts(bursts, polar, product_folder)

                # WARP BURSTS INTO SINGLE IMAGE
                out_image = os.path.join(product_folder, product + f"_{direct}_{polar}.tif")
                print(f"\n        - warping into a single image")
                gdal.Warp(out_image, to_be_warped,
                          xRes=10, yRes=10,
                          dstNodata=0, targetAlignedPixels=True)

                # REMOVE TEMPORARY FILES ("bursts")
                for file in to_be_warped:
                    os.remove(file)

                tta1 = time.time() - tta1
                print(f"     --- Time: {tta1} sec. ---")

            tta_combo = time.time() - tta_combo
            print(f"  --- Time for combo {direct} {polar}: {tta_combo} sec. ---")

            # CREATE COMPOSITE
            tta2 = time.time()
            print(f"Creating composite for {direct} {polar} {data_type} in {diw[0]}")
            q = os.path.join(product_folder, "*.tif")
            paths_for_composite = glob.glob(q)
            # print(paths_for_composite)  # REM

            if paths_for_composite:
                composite_name = f"{diw[0]}_SLC_{direct}_{polar}_{data_type}"
                # This bbox is outline of SLO with 5 km buffer in EPSG:32633
                bbox = [368930, 5024780, 627570, 5197200]
                composite(
                    paths_for_composite,
                    week_path,
                    composite_name,
                    "mean",
                    bbox)
                # print(f"Making composite {composite_name}")  # REM
            else:
                print("No images available for this week!")

            tta2 = time.time() - tta2
            print(f"--- Time: {tta2} sec. ---")

            # Remove temporary folder
            rmtree(product_folder, ignore_errors=True)

        tta_week = time.time() - tta_week
        tw = this_week["start"].strftime("%Y%m%d")
        print(f"--- Time for week {tw}: {tta_week} sec. ---")

    return "\n################ Finished processing! ################"


if __name__ == "__main__":
    # ----- INPUT ------------------------------------------------------------------
    # Create list of weekly intervals (6 days per week)
    in_start = "20170301"
    in_end = "20170307"
    in_step = 6

    in_type = "COH"  # COH or SIG

    # Source folder
    in_src = "d:\\slc\\"
    # in_src = "t:\\ZRSVN_Travinje\\*"

    # Save location
    in_save = "d:\\slc\\coherence"
    # ------------------------------------------------------------------------------

    result = get_weekly_slc(in_start, in_end, in_step, in_type, in_src, in_save)
    print(result)
