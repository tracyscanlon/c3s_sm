# -*- coding: utf-8 -*-
"""
Module for a command line interface to convert the GLDAS data into a
time series format using the repurpose package
"""

import os
import sys
import argparse
from datetime import datetime

from pygeogrids import BasicGrid

from repurpose.img2ts import Img2Ts
from interface import C3S_Nc_Img_Stack
from smecv_grid.grid import SMECV_Grid_v042 as c3s_grid
import warnings

def get_metadata():
    '''
    Reads metadata from the image file, to pass to the time series
    Returns
    -------

    '''
    pass


def mkdate(datestring):
    """
    Create date string.

    Parameters
    ----------
    datestring : str
        Date string.
    Returns
    -------
    datestr : datetime
        Date string as datetime.
    """
    if len(datestring) == 10:
        return datetime.strptime(datestring, '%Y-%m-%d')
    if len(datestring) == 16:
        return datetime.strptime(datestring, '%Y-%m-%dT%H:%M')

def str2bool(val):
    if val in ['True', 'true', 't', 'T', '1']:
        return True
    else:
        return False

def reshuffle(input_root, outputpath,
              startdate, enddate,
              parameters, land_points=True, sub_path=['%Y'],
              imgbuffer=50):
    """
    Reshuffle method applied to C3S data.
    Parameters
    ----------
    input_root: string
        input path where gldas data was downloaded
    outputpath : string
        Output path.
    startdate : datetime
        Start date.
    enddate : datetime
        End date.
    parameters: list
        parameters to read and convert
    imgbuffer: int, optional
        How many images to read at once before writing time series.
    """

    if land_points:
        grid = c3s_grid(subset_flag='land')
    else:
        grid = c3s_grid(subset_flag=None)

    input_dataset = C3S_Nc_Img_Stack(input_root, parameters, sub_path, grid,
                                     array_1D=True)

    if not os.path.exists(outputpath):
        os.makedirs(outputpath)

    # todo: copy metadata from all files to time series files.
    global_attr = {'product': 'C3S'}

    # get time series attributes from first day of data.
    data = input_dataset.read(startdate)
    #ts_attributes = data.metadata
    ts_attributes = global_attr

    reshuffler = Img2Ts(input_dataset=input_dataset, outputpath=outputpath,
                        startdate=startdate, enddate=enddate, input_grid=grid,
                        imgbuffer=imgbuffer, cellsize_lat=5.0,
                        cellsize_lon=5.0, global_attr=global_attr, zlib=True,
                        unlim_chunksize=1000, ts_attributes=ts_attributes)
    reshuffler.calc()


def parse_args(args):
    """
    Parse command line parameters for C3S reshuffling.

    Parameters
    ----------
    args : list of str
        Command line parameters as list of strings.
    Returns
    -------
    args : argparse.Namespace
        Command line arguments.
    """

    parser = argparse.ArgumentParser(
        description="Convert C3s image data to time series format.")
    parser.add_argument("dataset_root",
                        help='Root of local filesystem where the '
                             'data is stored.')

    parser.add_argument("timeseries_root",
                        help='Root of local filesystem where the timeseries '
                             'should be stored.')

    parser.add_argument("start", type=mkdate,
                        help=("Startdate. In format YYYY-MM-DD"))

    parser.add_argument("end", type=mkdate,
                        help=("Enddate. In format YYYY-MM-DD"))

    parser.add_argument("parameters", metavar="parameters",
                        nargs="+",
                        help=("Parameters to reshuffle into time series format. "
                              "e.g. sm for creating soil moisture time series"))
    parser.add_argument("--land_points", type=str2bool, default='False',
                        help=("Set True to convert only land points as defined"
                              " in the C3s land mask (faster and less/smaller files)"))

    parser.add_argument("--imgbuffer", type=int, default=50,
                        help=("How many images to read at once. Bigger "
                              "numbers make the conversion faster but "
                              "consume more memory."))

    args = parser.parse_args(args)
    # set defaults that can not be handled by argparse

    print("Converting data from {} to"
          " {} into folder {}.".format(args.start.isoformat(),
                                      args.end.isoformat(),
                                      args.timeseries_root))

    return args


def main(args):
    """
    Main routine used for command line interface.
    Parameters
    ----------
    args : list of str
        Command line arguments.
    """
    args = parse_args(args)

    reshuffle(args.dataset_root,
              args.timeseries_root,
              args.start,
              args.end,
              args.parameters,
              land_points=args.land_points,
              imgbuffer=args.imgbuffer)



def run():
    main(sys.argv[1:])

if __name__ == '__main__':


    cmd = [r'C:\Temp\tcdr\active_daily', r'C:\Temp\tcdr\ts',
           '1991-08-05', '1991-08-10', 'sm']
    main(cmd)


    run()