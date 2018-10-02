# The MIT License (MIT)
#
# Copyright (c) 2018, TU Wien
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

'''
Readers for the C3S soil moisture proudct daily, dekadal (10-daily) and monthly images as well
as for timeseries generated using this module
'''

import inspect
import pandas as pd
import os
import netCDF4 as nc
import numpy as np
from datetime import timedelta
from dateutil.relativedelta import relativedelta

from pygeobase.object_base import Image
from pygeobase.io_base import ImageBase
from pygeobase.io_base import MultiTemporalImageBase
from pygeogrids.netcdf import load_grid

from smecv_grid.grid import SMECV_Grid_v042
from netCDF4 import Dataset, num2date
from pynetcf.time_series import GriddedNcOrthoMultiTs
from pynetcf.time_series import IndexedRaggedTs, GriddedNcTs
from pygeogrids.grids import CellGrid
from datetime import datetime
from datetime import time as dt_time
from collections import Iterable
from grid import C3SCellGrid
from parse import parse

def c3s_filename_template(name='default'):
    # this function can be used in case the filename changes at some point.
    if name == 'default':
        return '{product}-SOILMOISTURE-L3S-{data_type}-{sensor_type}-{temp_res}-{datetime}000000-{subprod}-{version}.0.0.nc'


class C3STs(GriddedNcOrthoMultiTs):
    """
    Module for reading C3S time series in netcdf format.
    """

    def __init__(self, ts_path, grid_path=None, remove_nans=False):
        '''
        Parameters
        ----------
        ts_path : str
            Path to the netcdf time series files
        grid_path : str, optional (default: None)
            Path to the netcdf grid file.
            If None is passed, grid.nc is searched in ts_path.
        remove_nans : bool, optional (default: False)
            Replace -9999 with np.nan in time series
        '''
        self.remove_nans = remove_nans

        if grid_path is None:
            grid_path = os.path.join(ts_path, "grid.nc")

        grid = load_grid(grid_path)

        super(C3STs, self).__init__(ts_path, grid=grid)
        '''
        super(C3STs, self).__init__(ts_path, grid=grid,
                                    ioclass=GriddedNcOrthoMultiTs,
                                    ioclass_kws={'read_bulk': True},
                                    mode='r',
                                    fn_format='{:04d}')
        '''

    def _read_gp(self, gpi, **kwargs):
        """Read a single point from passed gpi or from passed lon, lat """
        # override the _read_gp function from parent class, to add dropna functionality

        ts = super(C3STs, self)._read_gp(gpi, **kwargs)
        if ts is None:
            return None

        if self.remove_nans:
            ts = ts.replace(-9999.0000, np.nan)

        ts.index = ts.index.tz_localize('UTC')

        return ts


    def read_cell(self, cell, var=None):
        """
        Read all time series for the selected cell.

        Parameters
        -------
        cell: int
            Cell number as in the c3s grid
        var : str
            Name of the variable to read.
        """

        file_path = os.path.join(self.path, '{}.nc'.format("%04d" % (cell,)))
        with nc.Dataset(file_path) as ncfile:
            loc_id = ncfile.variables['location_id'][:]
            time = ncfile.variables['time'][:]
            unit_time = ncfile.variables['time'].units
            delta = lambda t: timedelta(t)
            vfunc = np.vectorize(delta)
            since = pd.Timestamp(unit_time.split('since ')[1])
            time = since + vfunc(time)

            variable = ncfile.variables[var][:]
            variable = np.transpose(variable)
            data = pd.DataFrame(variable, columns=loc_id, index=time)
            if self.remove_nans:
                data = data.replace(-9999.0000, np.nan)
            return data


class C3SImg(ImageBase):
    """
    Module for a single C3S image (for one time stamp)
    """

    def __init__(self, filename, parameters='sm', mode='r', subgrid=None,
                 array_1D=False):
        '''
        Parameters
        ----------
        filename : str
            Path to the file to read
        parameters : str or Iterable, optional (default: 'sm')
            Names of parameters in the file to read.
            If None are passed, all are read.
        array_1D : bool, optional (default: False)
            Read image as one dimensional array, instead of a 2D array
            Use this when using a subgrid.
        '''

        super(C3SImg, self).__init__(filename, mode=mode)

        if not isinstance(parameters, list):
            parameters = [parameters]

        self.parameters = parameters
        self.grid = C3SCellGrid(subset=None) if not subgrid else subgrid
        self.array_1D = array_1D

    def read(self, timestamp=None):
        """
        Reads a single C3S image.

        Parameters
        -------
        timestamp: datetime
            Timestamp file file to read.

        Returns
        -------
        image : Image
            Image object from netcdf content
        """

        ds = Dataset(self.filename, mode='r')

        param_img = {}
        img_meta = {'global': {}}

        if self.parameters[0] is None:
            parameters = ds.variables.keys()
        else:
            parameters = self.parameters

        for param in parameters:
            if param in ['lat', 'lon', 'time']: continue
            param_metadata = {}

            variable = ds.variables[param]

            for attr in variable.ncattrs():
                param_metadata.update({str(attr): getattr(variable, attr)})

            #there is always only day per file?
            param_img[param] = variable[0][:].flatten().filled()
            img_meta[param] = param_metadata

        # add global attributes
        for attr in ds.ncattrs():
            img_meta['global'][attr] = ds.getncattr(attr)

        ds.close()

        if self.array_1D:
            return Image(self.grid.activearrlon, self.grid.activearrlat,
                         param_img, img_meta, timestamp)
        else:
            for key in param_img:
                param_img[key] = param_img[key].reshape(720, 1440)

            return Image(self.grid.activearrlon.reshape(720, 1440),
                         self.grid.activearrlat.reshape(720, 1440),
                         param_img,
                         img_meta,
                         timestamp)


    def write(self, *args, **kwargs):
        pass

    def close(self, *args, **kwargs):
        pass

    def flush(self, *args, **kwargs):
        pass



class C3S_Nc_Img_Stack(MultiTemporalImageBase):

    def __init__(self, data_path, parameters='sm', sub_path=['%Y'],
                 subgrid=None, array_1D=False):
        '''
        Parameters
        ----------
        data_path : str
            Path to directory where C3S images are stored
        parameters : list or str,  optional (default: 'sm')
            Variables to read from the image files.
        sub_path : list or None, optional (default: ['%Y'])
            List of subdirectories in the data path
        subgrid : grid, optional (default: None)
            Subset of the image to read
        array_1D : bool, optional (default: False)
            Flatten the read image to a 1D array instead of a 2D array
        '''

        self.data_path = data_path
        ioclass_kwargs = {'parameters': parameters,
                          'subgrid' : subgrid,
                          'array_1D': array_1D}

        template = c3s_filename_template()
        self.fname_args = self._parse_filename(template)
        filename_templ = template.format(**self.fname_args)

        super(C3S_Nc_Img_Stack, self).__init__(path=data_path, ioclass=C3SImg,
                                               fname_templ=filename_templ ,
                                               datetime_format="%Y%m%d",
                                               subpath_templ=sub_path,
                                               exact_templ=True,
                                               ioclass_kws=ioclass_kwargs)

    def _parse_filename(self, template):
        '''
        Search a file in the passed directory and use the filename template to
        to read settings.

        Parameters
        -------
        template : str
            Template for all files in the passed directory.

        Returns
        -------
        parse_result : parse.Result
            Parsed content of filename string from filename template.
        '''

        for curr, subdirs, files in os.walk(self.data_path):
            for f in files:
                file_args = parse(template, f)
                if file_args is None:
                    continue
                else:
                    file_args = file_args.named
                    file_args['datetime'] = '{datetime}'
                    return file_args

        raise IOError('No file name in passed directory fits to template')



    def tstamps_for_daterange(self, start_date, end_date):
        '''
        Return dates in the passed period, with respect to the temp resolution
        of the images in the path.

        Parameters
        ----------
        start_date: datetime
            start of date range
        end_date: datetime
            end of date range

        Returns
        -------
        timestamps : list
            list of datetime objects of each available image between
            start_date and end_date
        '''
        if self.fname_args['temp_res'] == 'MONTHLY':
            next = lambda date : date + relativedelta(months=+1)
        elif self.fname_args['temp_res'] == 'DAILY':
            next = lambda date : date + relativedelta(days=+1)
        elif self.fname_args['temp_res'] == 'DEKADAL':
            next = lambda date : date + relativedelta(days=+10)
        else:
            raise NotImplementedError

        timestamps = [start_date]
        while next(timestamps[-1])  <= end_date:
            timestamps.append(next(timestamps[-1]))

        return timestamps






if __name__ == '__main__':

    path = r'C:\Users\wpreimes\AppData\Local\Temp\tmphbaubd'
    ds = C3STs(path)
    ts = ds.read(-159.625, 65.875)

    afile = r"C:\Temp\tcdr\active_daily"
    ds = C3S_Nc_Img_Stack(afile, parameters=['sm'], sub_path=['%Y'],
                 subgrid=None, array_1D=False)

    img = ds.read(timestamp=datetime(1991,8,6))

    images = ds.iter_images(start_date=datetime(1991,8,5), end_date=datetime(1991,8,10))




    afile = r"C:\Temp\tcdr\active_daily\1991\C3S-SOILMOISTURE-L3S-SSMS-ACTIVE-DAILY-19910805000000-TCDR-v201801.0.0.nc"
    img = C3SImg(afile, ['sm', 'sm_uncertainty'], None, True)
    image = img.read()
