import pickle
from os.path import dirname, basename, join

import matplotlib.pyplot as plt
import rasterio
from mpl_toolkits.axes_grid1 import make_axes_locatable


def set_type(typ):
    if typ == "SIG":
        typ_long = "SIGMA"
        v_min = 0
        v_max = 0.2
    elif typ == "COH":
        typ_long = "COHERENCE"
        v_min = 0
        v_max = 1
    else:
        print(f"Type {typ} is not defined, using defaults.")
        typ_long = "default"
        v_min = None
        v_max = None

    return typ_long, v_min, v_max


def plot_preview(array_pickle, typ, save_path):
    array = pickle.load(open(array_pickle, "rb"))
    array = array.squeeze()

    # Set some parameters for plotting
    typ_long, v_min, v_max = set_type(typ)

    # Create figure and plot raster
    f = plt.figure(figsize=(9.6, 7.2))
    ax = f.add_subplot(111)
    my_raster = ax.imshow(array, vmax=v_max, vmin=v_min)
    title = ax.set_title(f"Overview - {typ_long} {array.shape}")

    # Add colorbar that fits nicely
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    clb = plt.colorbar(my_raster, cax=cax)

    # Save as JPG
    plt.savefig(save_path, bbox_inches='tight')


def tif2jpg(path_in, typ):
    # File path
    file_save = ".\\test_coh3.jpg" # file_orig[:-4] + ".png"

    file_orig = path_in
    file_save = join(dirname(path_in), "preview_" + basename(path_in)[:-3] + "jpg")

    # Open file and read array
    with rasterio.open(file_orig, "r") as src:
        array = src.read()
        array = array.squeeze()

    # Set some parameters for plotting
    typ_long, v_min, v_max = set_type(typ)

    # Create figure and plot raster
    f = plt.figure(figsize=(9.6,7.2))
    ax = f.add_subplot(111)
    my_raster = ax.imshow(array, vmax=v_max, vmin=v_min)
    title = ax.set_title(f"Overview - {typ_long} {array.shape}")

    # Add colorbar that fits nicely
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    clb = plt.colorbar(my_raster, cax=cax)

    # Save as JPG
    plt.savefig(file_save, bbox_inches='tight')


if __name__ == "__main__":
    type_slc = "COH"

    my_file = "d:\\slc\\coherence\\weekly_20170301_20170306\\20170301_SLC_DES_VV_COH.tif"
    # my_file = "O:\\aitlas_slc_SIGMA\\yr17wk16_SLC_SIG_20170401_20170406_weekly\\20170401_20170406_weekly_SLC_SIG_ASC_VH_yr17wk16.tif"
    # my_file = "O:\\aitlas_slc_COHERENCE\\yr17wk16_SLC_COH_20170401_20170406_weekly\\20170401_20170406_weekly_SLC_COH_ASC_VH_yr17wk16.tif"

    tif2jpg(my_file, type_slc)
