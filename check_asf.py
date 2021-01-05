"""
Checks downloaded folder against ASF query.

Finds:
    - missing files (creates CSV for download)
    - surplus files (moves to a desired folder)

"""
import glob
import shutil
import time
from os import makedirs
from os.path import join, basename

import pandas as pd
import requests


def check_asf(aoi, src_pth, copy_to_folder, year=None, month=None,
              start_date=None, end_date=None):
    makedirs(copy_to_folder, exist_ok=True)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # a) Initiate log file for saving results

    timestr = time.strftime("%Y%m%d-%H%M%S")
    logname = "check_dwn-asf_"
    if start_date and end_date:
        logname = f"{logname}-interval-{start_date}_{end_date}--{timestr}"
    elif month is None:
        logname = logname + f"{year}-all--{timestr}"
    else:
        logname = logname + f"{year}-{month:02}--{timestr}"

    logname = join(src_pth, logname + ".txt")
    logfile = open(logname, 'w')

    logfile.write(time.strftime("%Y-%m-%d-%H:%M:%S") + "\n")
    logfile.write("CHECK IF ALL FILES HAVE BEEN DOWNLOADED FROM ASF\n\n")
    logfile.write(f"Year: {year}\n")
    logfile.write(f"Month: {month}\n")
    logfile.write(f"Source folder: {src_pth}\n")
    logfile.write("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n\n")

    # b) Build url
    if start_date and end_date:
        qs = (start_date[0:4], start_date[4:5], start_date[5:6])
        qe = (end_date[0:4], end_date[4:5], end_date[5:6])
        q_start = f"&start={qs[0]}-{qs[1]}-{qs[2]}T00:00:00Z"
        q_end = f"&end={qe[0]}-{qe[1]}-{qe[2]}T23:59:59.99Z"
    elif month is None:
        q_start = f"&start={year}-01-01T00:00:00Z"
        q_end = f"&end={year + 1}-01-01T00:00:00Z"
    else:
        q_start = f"&start={year}-{month:02}-01T00:00:00Z"
        if month == 12:
            q_end = f"&end={year + 1}-01-01T00:00:00Z"
        else:
            q_end = f"&end={year}-{month + 1:02}-01T00:00:00Z"

    url = ("https://api.daac.asf.alaska.edu/services/search/param?"
           "platform=Sentinel-1"
           f"&polygon={aoi}"
           f"{q_start}{q_end}"
           "&processingLevel=SLC"
           "&output=JSON")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # SEARCH FOLDER FOR ALREADY DOWNLOADED
    if start_date and end_date:
        # TODO: search for specific interval (probably have to loop glob with all dates)
        search_zip_files = f"*{year}*.zip"
    elif month is None:
        search_zip_files = f"*{year}*.zip"
    else:
        search_zip_files = f"*{year}{month:02}*.zip"

    q = join(src_pth, search_zip_files)
    downloaded = glob.glob(q)
    in_folder_files = [a[-8:-4] for a in downloaded]
    logfile.write(f"Number of files in folder: {len(in_folder_files)}\n")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # GET LIST OF FILES FROM SERVER
    res = requests.get(url)
    res_json = res.json()[0]
    on_server_codes = [file['sceneId'][-4:] for file in res_json]
    logfile.write(f"Number of files on server: {len(on_server_codes)}\n")
    logfile.write("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n\n")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # COMPARE AND CREATE THREE LISTS: downloaded, missing and to be moved

    already_downloaded = []
    have_to_download = []
    have_to_download_codes = []
    for product in res_json:
        if product['sceneId'][-4:] in in_folder_files:
            already_downloaded.append(product['sceneId'][-4:])
        else:
            have_to_download.append(product['granuleName'])
            have_to_download_codes.append(product['sceneId'][-4:])

    # Files not covering NL AOI,probably Denmark
    files_not_needed = list(set(in_folder_files) - set(on_server_codes))

    logfile.write(f"Already downloaded files: {len(already_downloaded)}\n")
    logfile.write("----\n")
    logfile.write(f"Missing {len(have_to_download_codes)} files:\n")
    if have_to_download:
        [logfile.write(f"{text}\n") for text in have_to_download]
    else:
        logfile.write("None\n")
    logfile.write("----\n")
    logfile.write(f"There are {len(files_not_needed)} surplus files:\n")
    if files_not_needed:
        [logfile.write(f"{text}\n") for text in files_not_needed]
    else:
        logfile.write("None\n")
    logfile.write("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n\n")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Create CSV file, do another request and filter out the dataframe for
    # only the files that are missing from the folder
    if have_to_download:
        asf_df = pd.read_csv(url[:-4] + "CSV")
        asf_df = asf_df[asf_df["Granule Name"].isin(have_to_download)]

        if not asf_df.empty:
            if month is None:
                csv_name = f"missing_ASF_{year}-all--{timestr}"
            else:
                csv_name = f"missing_ASF_{year}-{month}--{timestr}"

            csv_name = join(src_pth, csv_name + ".csv")
            asf_df.to_csv(csv_name, index=False)

            logfile.write("Created CSV file for bulk download of missing data:\n")
            logfile.write(f" {csv_name}\n")
            logfile.write("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n\n")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # MOVE FILES TO DK FOLDER
    if files_not_needed:
        logfile.write("The following files have been moved:\n")
        for i, undesired in enumerate(files_not_needed):
            q = join(src_pth, f"*{undesired}*.zip")
            src = glob.glob(q)[0]
            dst = join(copy_to_folder, basename(src))
            print(f"Moving file {i+1}/{len(files_not_needed)}")
            try:
                shutil.move(src, dst)
            except shutil.Error as err:
                logfile.write(f"Error while moving {src}: {err.args[0]}\n")
            finally:
                logfile.write(f" {src} --> {dst}\n")
        logfile.write("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n\n")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # CLEAN-UP

    logfile.close()

    return f"Finished {year} {month}!"


if __name__ == "__main__":
    # Polygon for Netherlands (AOI)
    netherlands = ("6.525,53.5239,5.1388,53.3312,4.6883,52.9431,3.6671,51.4616,"
                   "3.701,51.3604,3.8892,51.2786,4.0315,51.2907,4.6536,51.5139,"
                   "5.728,51.2399,5.7943,50.993,6.0069,50.9678,5.9937,51.0297,"
                   "6.1438,51.2544,6.0052,51.8934,6.7445,51.9148,7.0795,52.4108,"
                   "6.6637,52.5374,6.7445,52.6497,7.068,52.6497,7.2066,53.3174,"
                   "6.525,53.5239")

    denmark = ("10.0693,57.2364,9.78960,56.7982,9.3374,55.4055,11.9976,55.0468,"
               "14.7275,55.0286,12.6518,55.2160,12.4555,55.5703,11.1882,56.2079,"
               "10.7409,56.8055,10.6702,57.2158,10.0693,57.2364")

    # Folder containing downloaded files
    # in_src_pth = "r:\\Sentinel-1_SLC_aitlas_NL_2017"
    in_src_pth = "r:\\Sentinel-1_SLC_aitlas_NL_2019-02"
    # in_src_pth = "r:\\Sentinel-1_SLC_aitlas_NL_2019-08-12"
    # in_src_pth = "r:\\Sentinel-1_SLC_aitlas_DK_2017"

    # Where to move files that are not in the desired AOI:
    # in_sur_pth = "r:\\Sentinel-1_SLC_aitlas_DK_2017"
    in_sur_pth = "r:\\Sentinel-1_SLC_aitlas_DK_2019"
    # in_sur_pth = "r:\\Sentinel-1_SLC_aitlas_DK_2019"
    # in_sur_pth = "r:\\Sentinel-1_SLC_to_delete"

    in_polygon = netherlands
    in_year = 2019
    in_month = 2  # Set month to None to search entire year

    out = check_asf(in_polygon, in_src_pth, in_sur_pth, in_year, in_month)
    print(out)
