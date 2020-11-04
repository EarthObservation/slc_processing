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


# USEFUL FOR DEBUGGING

Weekly mosaic that contains "nodata" stripes
```
in_start = "20170113"
in_end = "20170118"
in_step = 6
```
