import panel as pn
import xarray as xr
import holoviews
from holoviews import opts

from pathlib import Path
import re
import matplotlib
import argparse

from echopype import visualize
import echoshader
import echoregions as er


holoviews.extension("bokeh")
pn.extension()


parser = argparse.ArgumentParser()
parser.add_argument('-z', '--zarr-file', type=str, help="regridded zarr file to plot", default=None)
args, _ = parser.parse_known_args()


zarr_file_input = args.zarr_file  # regridded zarr file to plot

REGRID_FOLDER = "/home/ubuntu/efs/hake_nasc_202309/regridd_Sv_latlon/"
EVR_PRED_FOLDER = "/home/ubuntu/efs/hake_nasc_202309/prediction_evr"
EVR_LABEL_FOLDER = "/home/ubuntu/efs/label_allocations/"
EVR_LABEL_FOLDER_pattern = "_run_2023_10_18/regions"



# Determine which file to plot 
if zarr_file_input is None:
    # Grab the last in regridded folder
    zarr_file = sorted(list(Path(REGRID_FOLDER).glob("*.zarr")))[-1]
else:
    # Use input zarr file
    zarr_file = Path(zarr_file_input)





# file_selector = pn.widgets.FileSelector(REGRID_FOLDER, value=["/home/ubuntu/efs/hake_nasc_202309/regridd_Sv_latlon/2019/x0083_2_WT_20190815_204056_f0019_platform_Sv_latlon.zarr"])
file_selector = pn.widgets.FileSelector(REGRID_FOLDER, value=[str(zarr_file)])

print(f"Plotting: {zarr_file.name}")

@pn.depends(file_selector.param.value, watch=False)
def update_echogram(zarr_file):

    filename = str(zarr_file[0]).split(REGRID_FOLDER)[-1].strip(".zarr")

    evr_file = Path(EVR_PRED_FOLDER) / f"{filename}_pred.evr"

    transect  = filename.split("/")[1].split("_")[0]

    year = filename.split("/")[0]

    evr_manual_file = Path(EVR_LABEL_FOLDER) / (year + EVR_LABEL_FOLDER_pattern) / f"{transect}_regions.evr"

    print(evr_manual_file)

    ds_MVBS = xr.open_mfdataset(zarr_file[0], engine="zarr")

    print(ds_MVBS)

    # drop echo_range if it is there (it will be reassigned to depth)
    if "echo_range" in list(ds_MVBS.coords):
       ds_MVBS = (
          ds_MVBS
          .drop(["echo_range"])
           )
   
    gram_opts = opts.RGB(width=1200, height=500, xlabel="Time", ylabel="depth", title=filename)


    # 2019 
    #tricolor = ds_MVBS.eshader.echogram(
    #    channel=[
    #        'GPT 120 kHz 00907205a6d0 4-1 ES120-7C',
    #        'GPT  38 kHz 009072060fbe 2-1 ES38B',
    #        'GPT  18 kHz 009072058c8d 1-1 ES18-11',
    #    ],
    #    vmin = -100, 
    #    vmax = -0,
    #    rgb_composite = True,
    #    opts = gram_opts,
    #)
    
    # the channels strings seem to be different for different years: hence manual selection based on order 
    channels = list(ds_MVBS.channel.values)
    tricolor = ds_MVBS.eshader.echogram(
        channel=[
            channels[2],
            channels[1],
            channels[0],
        ],
        vmin = -70, 
        vmax = -40,
        rgb_composite = True,
        vert_dim = "depth",
        opts = gram_opts,
    )




    # Read EVR prediction regions
    try:
        r2d = er.read_evr(str(evr_file))
    except:
        r2d = None
        print("No hake regions detected!")

    if r2d:
        # close regions
        ping_times = [list(item)+[item[0]] for item in r2d.data["time"]]
        depths = [list(item)+[item[0]] for item in r2d.data["depth"]]

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
        region_id_manual_hake = df_r2d_manual_hake["region_id"].values.astype("int").tolist()


        # Close regions manually due to bug addressed in #133 (not merged yet)
        r2d_manual.data = r2d_manual.close_region(region=region_id_manual_hake)

        # close regions
        ping_times_manual = [list(item) for item in r2d_manual.data["time"]]
        depths_manual = [list(item) for item in r2d_manual.data["depth"]]


        # Plot region
        regions_manual = holoviews.Path(zip(ping_times_manual, depths_manual)).opts(color='c', line_width=2, xlim=(ds_MVBS.ping_time.min().values, ds_MVBS.ping_time.max().values))


    if regions_manual is not None and regions_pred is not None:

        tricolor_regions = tricolor() * regions_pred * regions_manual
        

    else:
        tricolor_regions = tricolor()

    return(tricolor_regions)

panel_tricolor_region = pn.Column(
               pn.Column(file_selector, update_echogram),
        )




pn.serve(
    {
        "tricolor": panel_tricolor_region,
    },
    port=1456,
    websocket_origin="*",
    admin=True,
    show=False, # don't show on brower tab by default
)
