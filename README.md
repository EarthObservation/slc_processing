# slc_processing

Routines for processing and preparation of Sentinel-1 SLC data for project 
AiTLAS.

## Introduction

To import Sentinel-1 SLC data into EO Patch, the raw SLC products have to first
be transformed into an appropriate format.
This routine picks up SLC data that have already been pre-processed 
(atmospheric and geometric corrections, reprojection to UTM), for which we have
 then calculated Coherence and Sigma (Backscattering intensity).

> **The coherence** of the interferometric pair is an important parameter,
that combined with the more usual **backscatter amplitudes**,
leads to useful images segmentation.
([ESA: An Overview of SAR Interferometry](https://earth.esa.int/workshops/ers97/program-details/speeches/rocca-et-al/))

The mosaicking step is performed independently for the two passes 
(Ascending and Descending) and for the two polarimetry (VV and VH) for the
Coherence and the Backscattering. It therefore results in 8 independent time 
series of:
1. Coherence – Ascending – VV
2. Coherence – Ascending – VH
3. Coherence – Descending – VV
4. Coherence – Descending – VH
5. Backscattering intensity – Ascending – VV
6. Backscattering intensity – Ascending – VH
7. Backscattering intensity – Descending – VV
8. Backscattering intensity – Descending – VH

The data is saved in GeoTIF format.

## Routine

Preparation of data is preformed by running the slc_week.py script. The following
parameters are required at input:

```python
    # YYYYmmdd start of the interval
    in_start = "20170301"
    
    # YYYYmmdd end of the interval
    in_end = "20170307"
    
    # Number of days in one week (default=6)
    in_step = 6
    
    # Coherence and Sigma are processed separately
    in_type = "COH"  # COH or SIG

    # Path to source files
    in_src = "o:\\ZRSVN_Travinje\\"
    # in_src = "t:\\ZRSVN_Travinje\\"

    # Path to save location
    in_save = "d:\\slc\\coherence"
```

The preparation of data is preformed in several steps:

1. Split time period into weeks (default is 6 day week)
2. Find all files within a week
3. Filter for direction (ASC, DES) and polarization (VV, VH)
4. Within one week find all files with the same timestamp
5. Stitch together all time stamps into a single image
   - use gdal warp to deal with nodata (both 0 and nan are present as nodata in source images)
6. Resample (nearest neighbor) and target aligned pixels to match with S-2 raster
   - again using gdal warp
7. Create mean weekly mosaic from all resampled images for that week
   - run the `composite_dask.py` routine
   
The final products for each data type (COH or SIG) respectively are saved into 
weekly folders:
 
```
.\Results_folder
    \Coherence
        \Week_20200101_20200107
            \20200101_20200107_COH_ASC_VH.tif
            \20200101_20200107_COH_ASC_VV.tif
            \20200101_20200107_COH_DES_VH.tif
            \20200101_20200107_COH_DES_VV.tif
        \Week_20200108_20200113
            \20200108_20200113_COH_ASC_VH.tif
            \20200108_20200113_COH_ASC_VV.tif
            \20200108_20200113_COH_DES_VH.tif
            \20200108_20200113_COH_DES_VV.tif
    \Sigma
        \Week_20200101_20200107
            \20200101_20200107_SIG_ASC_VH.tif
            \20200101_20200107_SIG_ASC_VV.tif
            \20200101_20200107_SIG_DES_VH.tif
            \20200101_20200107_SIG_DES_VV.tif
        \Week_20200108_20200113
            \20200108_20200113_SIG_ASC_VH.tif
            \20200108_20200113_SIG_ASC_VV.tif
            \20200108_20200113_SIG_DES_VH.tif
            \20200108_20200113_SIG_DES_VV.tif
```


### USEFUL FOR DEBUGGING

Weekly mosaic that contains "nodata" stripes
```
in_start = "20170113"
in_end = "20170118"
in_step = 6
```


#Download from ASF
The ASF (Alaska satellite facility) repository is used for downloading missing
data and/or data not available directly from copernicus OpenHUB (for example
archived data - LTA). There are a few options for downloading using the [ASF API](https://asf.alaska.edu/api/).
All available files can also be queried manually through the online GUI:

https://search.asf.alaska.edu/#/

a) To download the data you first need to create an account with the ASF service!

b) To query through ASF API, you first need to install the [curl](https://curl.se/)
or [aria2](https://aria2.github.io/) tools
and add them to path (Windows), so the tools can be called from cmd.

###Option 1 - curl + python
####1. Set CURL to env path

`$>set PATH=%PATH%;D:\nejc\curl\bin`

`$>echo %PATH%`

####2. Run query using curl

Run query using the `curl` tool and save results to csv, metalink, or json file.
Below is an example of a query that look for all Sentinel-1 SLC files over the
region of the Netherlands (as polygon) for acquisitions from 2017:

```
C:\Users\ncoz\Desktop>curl "https://api.daac.asf.alaska.edu/services/search/param?platform=Sentinel-1&polygon=6.525,53.5239,5.1388,53.3312,4.6883,52.9431,3.6671,51.4616,3.701,51.3604,3.8892,51.2786,4.0315,51.2907,4.6536,51.5139,5.728,51.2399,5.7943,50.993,6.0069,50.9678,5.9937,51.0297,6.1438,51.2544,6.0052,51.8934,6.7445,51.9148,7.0795,52.4108,6.6637,52.5374,6.7445,52.6497,7.068,52.6497,7.2066,53.3174,6.525,53.5239&start=2017-01-01T00:00:00Z&end=2017-12-31T23:59:00Z&processingLevel=SLC&output=CSV" > example_download_list.csv
```
the structure of the query:

URL: `https://api.daac.asf.alaska.edu/services/search/param?`
   
Platform: `platform=Sentinel-1`

AOI: `polygon=6.525,53.5239,5.1388,53.3312,4.6883,52.9431,...`

Time interval: `start=2017-01-01T00:00:00Z&end=2017-12-31T23:59:00Z`

Product: `processingLevel=SLC`

Export to csv: `"...&output=CSV" > example_download_list.csv`

For more keywords check the [API user guide](https://asf.alaska.edu/api/).

You can edit the csv or metalink file to select only specific products before starting the download.



####3. Download python bulk-download script from ASF

https://bulk-download.asf.alaska.edu/

Copy/save the python script to the folder where csv or metalink files are located.
Thi will also be the target folder for download.

####4. Run the python script with the csv or metalink file
`$>python download-all.py example_download_list.csv`

####5. Optional
If you need more control over the download of the files you can modify the python script
to fit your needs.

###Option 2 - check_asf.py
The download list (CSV) can alternatively be obtained using the check_asf.py script.

This script was created to perform a check for missing files in the download folder.
The script can also move unwanted (but already downloaded) files to a different folder.
It produces a log file, listing all the products that were checked and produces
a csv file with a list of missing products. The csv file can than be run together with
the python script, the same way as presented in Option 1.

###Option 3 - Aria2 (query & download with one command line)
Example:

```
aria2c --max-concurrent-downloads=100 --auto-file-renaming=false --check-certificate=false --http-auth-challenge=true --http-user=myusername --http-passwd="mypassword" "https://api.daac.asf.alaska.edu/services/search/param?platform=Sentinel-1&polygon=6.525,53.5239,5.1388,53.3312,4.6883,52.9431,3.6671,51.4616,3.701,51.3604,3.8892,51.2786,4.0315,51.2907,4.6536,51.5139,5.728,51.2399,5.7943,50.993,6.0069,50.9678,5.9937,51.0297,6.1438,51.2544,6.0052,51.8934,6.7445,51.9148,7.0795,52.4108,6.6637,52.5374,6.7445,52.6497,7.068,52.6497,7.2066,53.3174,6.525,53.5239&start=2018-07-01T00:00:00Z&end=2018-08-01T00:00:00Z&processingLevel=SLC&output=METALINK"
```

Note: replace `myusername` and `mypasssword` with your ASF credentials!
