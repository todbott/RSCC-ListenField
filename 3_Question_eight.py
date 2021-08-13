# -*- coding: utf-8 -*-
"""
Created on Sun Aug  8 16:11:14 2021

@author: Gillies
"""
from osgeo import osr, gdal
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import * 

# This is the main function, called after the file is chosen
def choose_clicked():
    # A file dialog pops up, and asks the user to choose the *.tiff file to process.
    # The path to that file (plus the filename) is stored in a variable called "tiff_path"
    tiff_path = os.path.abspath(filedialog.askopenfilename(initialdir = os.path.join(os.environ['HOMEPATH'], "Desktop"), title = "Choose the GeoTIFF file you want to resample and convert"))
    # ALso, we'll get the file extension from the last part of the filename by splitting it
    # This is done because we are going to save a new *.tif file at the end of this process,
    # and we want to re-use the same file extension (TIFF files might have a *.tif or *.tiff extension,
    # which is wny getting the file extension here is necessary)
    file_extension = "." + os.path.split(tiff_path)[len(os.path.split(tiff_path))-1].split(".")[1]
    
    # Open the raster and get the band
    # For this exercise, I assumed that it was a single-band raster image
    # If it was an RGB raster, for example, the code would have to be changed a bit
    in_ds = gdal.Open(tiff_path)
    in_band = in_ds.GetRasterBand(1)
    
    # Multiply the output size by 5
    out_rows = in_band.YSize * 5
    out_columns = in_band.XSize * 5
    
    # Create a new GeoTIFF file, with the sufffix "_resampled_and_converted.tif" (or .tiff, depending
    # on the original file extension)
    gtiff_driver = gdal.GetDriverByName('GTiff')
    out_ds = gtiff_driver.Create(tiff_path.replace(file_extension, "_resampled_and_converted" + file_extension), out_columns, out_rows)
    
    # create an EPSG:32617 Spatial Reference
    sr = osr.SpatialReference()
    sr.ImportFromEPSG(32617)
    
    # put that spatial reference into the new tiff
    out_ds.SetProjection(sr.ExportToWkt())
    geotransform = list(in_ds.GetGeoTransform())
    
    # Edit the geotransform so the pixels are one-fifth previous size
    geotransform[1] /= 5
    geotransform[5] /= 5
    out_ds.SetGeoTransform(geotransform)
    
    # read the original raster band from the original GeoTIFF into an array called "data"
    data = in_band.ReadAsArray(buf_xsize=out_columns, buf_ysize=out_rows) 
    out_band = out_ds.GetRasterBand(1)
    # then write it to the new GeoTIFF file we created above
    out_band.WriteArray(data)
    
    # flush the cache
    out_band.FlushCache()
    out_band.ComputeStatistics(False)
    # Build some overviews
    out_ds.BuildOverviews('average', [2, 4, 8, 16, 32, 64])
    
    # release the out_ds resource, effectively closing it and saving our changes
    del out_ds
    
    # Show a success message box, and close the main window, the program is complete here.
    messagebox.showinfo("Complete", "Processing is complete.  The image is saved in the original directory with the suffix '_resampled_and_converted'.")
    root.destroy()

# The code below is just for creating the GUI ---------------------------------------
root = Tk()
root.geometry('387x117')
root.configure(background='#CAE1FF')
root.title('Resample and convert')
Button(root, text='Choose a GeoTIFF to resample and convert', 
       bg='#A4D3EE', 
       font=('arial', 12, 'normal'), 
       command=choose_clicked).place(x=29, y=14)
root.mainloop()
#-----------------------------------------------------------------------------------