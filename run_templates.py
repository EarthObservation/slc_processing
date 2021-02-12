# ==============================================================================
# BATCH CONVERT
from tif2jpg import batch_convert

# my_folder = "o:\\aitlas_slc_SI_sigma"
my_folder = "d:\\aitlas_slc_test_NL"
# my_folder = "d:\\slc\\test_tif2jpg"
my_shape = ".\\shapes\\nl_border_Amersfoort.shp"
# my_shape = ".\\shapes\\si_border_UTM.shp"
batch_convert(my_folder, my_shape)
print("DONE!")


# ==============================================================================
# MAKE WEEKLY COMPOSITES
from slc_week import loop_weeks

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
in_bbox = [0, 305400, 287100, 625100]

# Shapefile for preview
my_shp = ".\\shapes\\nl_border_Amersfoort.shp"
# my_shp = ".\\shapes\\si_border_UTM.shp"

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
in_src = "r:\\Sentinel-1_SLC_products_AiTLAS_NL_sigma_10m_Amersfoort"

# Save location
# in_save = "d:\\aitlas_slc_test_NL"
# in_save = "o:\\aitlas_slc_SI_coherence"
# in_save = "o:\\aitlas_slc_SI_sigma"
# in_save = "o:\\aitlas_slc_NL_coherence"
in_save = "o:\\aitlas_slc_NL_sigma"
# --------------------------------------------------------------------------

result = loop_weeks(in_start, in_end, in_step, in_bbox,
                    in_type, in_src, in_save,
                    combinations=in_comb, country_border=my_shp)
print(result)


# ==============================================================================
# CHECK ASF
from check_asf import check_asf

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

# ==============================================================================
# COMPOSITE DASK
from composite_dask import composite
import time
# ========================================================================
# TEMPORARY INPUT
# ========================================================================
# Select from: mean, median, max, min
in_method = 'mean'

in_save_loc = ".\\composite_test_01"
in_save_nam = "test_03"

# List of paths to input files
in_fps = ["C:\\Users\\ncoz\\GitHub\\slc_processing\\tmp2\\one_image_38C8_ASC_VV.tif",
          "C:\\Users\\ncoz\\GitHub\\slc_processing\\tmp2\\second_image_DD0A_ASC_VV.tif"]

# Run composite with timer
t_tim_b = time.time()
composite(in_fps, in_save_loc, in_save_nam, in_method, dt="SIG")
t_tim_b = time.time() - t_tim_b
print(f"\n~~~~~ Total time: {t_tim_b:.2f} seconds ~~~~~\n")
