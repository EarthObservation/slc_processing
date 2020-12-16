import pickle
import time
from os.path import dirname, basename, join, isfile
import glob

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
    ax.set_title(f"Overview - {typ_long} {array.shape}")

    # Add colorbar that fits nicely
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    plt.colorbar(my_raster, cax=cax)

    # Save as JPG
    plt.savefig(save_path, bbox_inches='tight')


def tif2jpg(path_in):
    dt = time.time()
    # File path
    # file_save = ".\\test_coh3.jpg" # file_orig[:-4] + ".png"

    file_orig = path_in
    file_save = join(dirname(path_in), "preview_" + basename(path_in)[:-3] + "jpg")

    # file_save = ".\\test_jpg\\" + basename(path_in)[:-3] + "jpg"

    img_title = basename(path_in)[:-4]

    # Open file and read array
    with rasterio.open(file_orig, "r") as src:
        array = src.read()
        array = array.squeeze()

    # Set some parameters for plotting
    if "SIG" in img_title:
        v_min, v_max = (0, 0.2)
    elif "COH" in img_title:
        v_min, v_max = (0, 1)
    else:
        v_min, v_max = (None, None)

    # Create figure and plot raster
    f = plt.figure(figsize=(9.6, 7.2))
    ax = f.add_subplot(111)
    my_raster = ax.imshow(array, vmax=v_max, vmin=v_min)
    ax.set_title(f"Overview - {img_title} {array.shape}")

    # Add colorbar that fits nicely
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    plt.colorbar(my_raster, cax=cax)

    # Save as JPG
    plt.savefig(file_save, bbox_inches='tight')

    dt = time.time() - dt
    print(f"Time to convert to jpeg: {dt:02} sec.")


def batch_convert(folder):
    # folder = "o:\\aitlas_slc_SI_coherence"

    print(f"Searching for TIFs in {folder}")
    q = join(folder, "*", "*.tif")
    paths = glob.glob(q)

    for i, tif in enumerate(paths):
        jpg = tif[:-3] + "jpg"
        if not isfile(jpg):
            name = basename(tif)
            print(f"Converting {name} ({i+1}/{len(paths)})")
            tif2jpg(tif)
        else:
            print(f"SKIP ({i+1}/{len(paths)})")


if __name__ == "__main__":
    my_folder = "o:\\aitlas_slc_SI_sigma"
    batch_convert(my_folder)
    print("DONE!")