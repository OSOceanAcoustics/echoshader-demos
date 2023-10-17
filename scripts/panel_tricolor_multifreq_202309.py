import holoviews
import panel
import xarray as xr
holoviews.extension("bokeh")

from pathlib import Path
import re
import matplotlib
from echopype import visualize
from echoshader.new_version.echogram import Echogram
import echoregions as er

import argparse

import panel as pn

pn.extension()


parser = argparse.ArgumentParser()
parser.add_argument('-z', '--zarr-file', type=str, help="regridded zarr file to plot", default=None)
args, _ = parser.parse_known_args()


zarr_file_input = args.zarr_file  # regridded zarr file to plot

REGRID_FOLDER = "/home/ubuntu/efs/hake_nasc_202309/regridd_Sv_latlon"
EVR_PRED_FOLDER = "/home/ubuntu/efs/hake_nasc_202309/prediction_evr"
EVR_LABEL_FOLDER = "/home/ubuntu/efs/label_allocations/2013_test/staging/"

file_selector = pn.widgets.FileSelector(REGRID_FOLDER)

# Determine which file to plot 
if zarr_file_input is None:
    # Grab the last in regridded folder
    zarr_file = sorted(list(Path(REGRID_FOLDER).glob("*.zarr")))[-1]
else:
    # Use input zarr file
    zarr_file = Path(zarr_file_input)

print(f"Plotting: {zarr_file.name}")

filename = str(zarr_file).split("regridd_Sv_latlon/")[-1].strip(".zarr")

evr_file = Path(EVR_PRED_FOLDER) / f"{filename}_pred.evr"

transect  = filename.split("/")[1].split("_")[0]

evr_manual_file = Path(EVR_LABEL_FOLDER) / f"{transect}_regions.evr"

ds_MVBS = xr.open_dataset(zarr_file, engine="zarr")

# Swap out depth or echo_range to the inverted echo_range dimension
# This is to circumvent the `y_increase` problem in holoviews
ds_MVBS = (
    ds_MVBS
    .assign_coords({"depth_inverted": ("depth", ds_MVBS["depth"].values[::-1])})
    .swap_dims({"depth": "depth_inverted"})
    .drop(["depth", "echo_range"])
    .rename({"depth_inverted": "echo_range"})
)

# Plot tricolor echogram
tricolor = ds_MVBS.eshader.echogram_multiple_frequency(
    layout="composite",
    rgb_map={
        ds_MVBS.channel.values[2]: "R",  # 120 kHz
        ds_MVBS.channel.values[1]: "G",  # 38 kHz
        ds_MVBS.channel.values[0]: "B",  # 16 kHz
    },
    vmin=-70, vmax=-50
 )


# Read EVR prediction regions
try:
    r2d = er.read_evr(str(evr_file))
except:
    r2d = None
    print("No hake regions detected!")

if r2d:
    r2d.data["depth_inverted"] = ds_MVBS["echo_range"].values[0] - r2d.data["depth"] + 9.15

    # close regions
    ping_times = [list(item)+[item[0]] for item in r2d.data["time"]]
    depths = [list(item)+[item[0]] for item in r2d.data["depth_inverted"]]

    # Plot regions
    regions_pred = holoviews.Path(zip(ping_times, depths)).opts(color='m', line_width=2)
    


# Read EVR label regions

try:
    r2d_manual = er.read_evr(str(evr_manual_file))
except:
    r2d_manual = None
    print("No hake regions labeled!")

HAKE_LABELS = [
    "Age-0 Hake",
    "Age-1 Hake",
    "Hake",
    "Hake Mix",
]


if r2d_manual:

    df_r2d_manual = r2d_manual.data
    df_r2d_manual_hake = df_r2d_manual[df_r2d_manual["region_class"].isin(HAKE_LABELS)]
    region_id_manual_hake = df_r2d_manual_hake["region_id"].values.tolist()


    # Close regions manually due to bug addressed in #133 (not merged yet)
    r2d_manual.data = r2d_manual.close_region(region=region_id_manual_hake)

    r2d_manual.data["depth_inverted"] = ds_MVBS["echo_range"].values[0] - r2d_manual.data["depth"] + 9.15

    # close regions
    ping_times_manual = [list(item) for item in r2d_manual.data["time"]]
    depths_manual = [list(item) for item in r2d_manual.data["depth_inverted"]]


    # Plot region
    regions_manual = holoviews.Path(zip(ping_times_manual, depths_manual)).opts(color='k', line_width=2)




if regions_manual is not None and regions_pred is not None:


    panel_tricolor_region = panel.Column(
           panel.pane.Markdown(filename),
           panel.Row(tricolor * regions_pred * regions_manual, file_selector),
    )
else:
    panel_tricolor_region = panel.Row(tricolor)



# Multi-freq echogram
ek500_cmap = matplotlib.colormaps["ep.ek500"]
echogram_mf = ds_MVBS.eshader.echogram_multiple_frequency(
    layout="multiple_frequency",
    vmin=-70, vmax=-50, cmap="ep.ek500",
    clipping_colors={
        'min': tuple(ek500_cmap.get_under()),
        'max': tuple(ek500_cmap.get_over()),
        'NaN': tuple(ek500_cmap.get_bad()),
    }
 )

panel.serve(
    {
        "tricolor": panel_tricolor_region,
        "multi_freq": panel.Row(echogram_mf),
    },
    port=1456,
    websocket_origin="*",
    admin=True,
    show=False, # don't show on brower tab by default
)
