import glob
import time
from os.path import dirname, basename, join, isfile

import geopandas as gpd
import matplotlib.pyplot as plt
import rasterio
import rasterio.plot
from descartes import PolygonPatch
from matplotlib.collections import PatchCollection
from mpl_toolkits.axes_grid1 import make_axes_locatable
from numpy.random import rand


def tif2jpg(path_in, country_border=None):
    """Function creates JPEG preview file from SLC weekly composites (GeoTIFF).
    Optionally add country borders to the preview. The image is saved in the
    same folder as source raster, with matching filename.

    Notes
    -----
    Make sure both polygon and raster have the same CRS.

    Parameters
    ----------
    path_in : string
        Path to source raster file (all formats compatible with rasterio)
    country_border : string (optional)
        Path to shapefile (make sure CRS match with raster)

    Returns
    -------
    None
    """
    dt = time.time()

    # Create output path
    file_save = join(dirname(path_in), basename(path_in)[:-3] + "jpg")

    # Create title for plot
    img_title = basename(path_in)[:-4]

    # Set range for displayed data
    if "SIG" in img_title:
        # Majority of pixels are below 0.5 (values can go up to 10000)
        v_min, v_max = (0, 0.2)
    elif "COH" in img_title:
        # Coherence is always between 0 and 1
        v_min, v_max = (0, 1)
    else:
        v_min, v_max = (None, None)

    # Plot raster
    with rasterio.open(path_in, "r") as src:
        array = src.shape
        fig, ax = plt.subplots(figsize=(9.6, 7.2))
        # f = plt.figure(figsize=(9.6, 7.2))
        img_hidden = ax.imshow(rand(2, 2), vmax=v_max, vmin=v_min)
        # ax = f.add_subplot(111)
        img = rasterio.plot.show((src, 1), ax=ax, vmax=v_max, vmin=v_min)
        # fig.colorbar(img_hidden, ax=ax)

    # Add title
    ax.set_title(f"Overview - {img_title} {array}")

    # Add colorbar that fits nicely
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    fig.colorbar(img_hidden, cax=cax)
    # plt.colorbar(my_raster, cax=cax)  <-- used with ax.imshow
    # f.colorbar(my_raster)

    # Add country borders (from SHP)
    if country_border:
        shape = gpd.read_file(country_border)
        fts = [feature["geometry"] for _, feature in shape.iterrows()]
        ptchs = [PolygonPatch(ft, edgecolor="red", facecolor="none") for ft in fts]
        ax.add_collection(PatchCollection(ptchs, match_original=True))

    # Save as JPG and close the figure
    plt.savefig(file_save, bbox_inches='tight')
    plt.close("all")

    dt = time.time() - dt
    print(f"Time to convert to jpeg: {dt:02} sec.")


def batch_convert(folder, shp):
    """Creates a list of paths to all rasters that don't have a preview file and
    executes tif2jpg() function on them. The function searches folder structure
    of the SLC weekly products (SIG, COH).

    Parameters
    ----------
    folder : string
        Folder containing SLC weekly products.
    shp : string
        Path to shape file for country borders outline.

    Returns
    -------
    None

    """
    print(f"Searching for TIFs in {folder}")
    q = join(folder, "*", "*.tif")
    paths = glob.glob(q)

    for i, tif in enumerate(paths):
        jpg = tif[:-3] + "jpg"
        if not isfile(jpg):
            name = basename(tif)
            print(f"Converting {name} ({i+1}/{len(paths)})")
            tif2jpg(tif, shp)
        else:
            print(f"SKIP ({i+1}/{len(paths)})")


if __name__ == "__main__":
    # my_folder = "o:\\aitlas_slc_SI_sigma"
    my_folder = "d:\\aitlas_slc_test_NL"
    # my_folder = "d:\\slc\\test_tif2jpg"
    my_shape = ".\\shapes\\nl_border_Amersfoort.shp"
    # my_shape = ".\\shapes\\si_border_UTM.shp"
    batch_convert(my_folder, my_shape)
    print("DONE!")