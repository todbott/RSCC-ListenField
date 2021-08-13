# -*- coding: utf-8 -*-
"""
Created on Mon Aug  9 16:01:33 2021

@author: Gillies
"""

import numpy
from numpy import float32, zeros
import math
import imageio
import os

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import *

# These are the gain, offset, effective bandwidth, and band-averaged solar spectral irradiance 
# figures for each band, in dictionary form.  The gain and offset figures came from 
# "ABSOLUTE RADIOMETRIC CALIBRATION",
# published by Maxar in 2021.
 # The solar spectral irradiance and effective bandwith figures came from the PDF 
# "Radiometric Use of WorldView-3 Imagery",
# published by DigitalGlobe in 2016.
calibration_figures = [{"band": "Pan", "gain": 0.955, "offset": -5.505, "effective bandwidth": 0.2896, "band averaged solar_spectral irradiance (Thuillier 2003)": 1574.41},
                       {"band": "Coastal", "gain": 0.938, "offset": -13.099, "effective bandwidth": 0.0405, "band averaged solar_spectral irradiance (Thuillier 2003)": 1757.89},
                       {"band": "Blue", "gain": 0.946, "offset": -9.409, "effective bandwidth": 0.0540, "band averaged solar_spectral irradiance (Thuillier 2003)": 2004.61},
                       {"band": "Green", "gain": 0.958, "offset": -7.771, "effective bandwidth": 0.0618, "band averaged solar_spectral irradiance (Thuillier 2003)": 1830.18},
                       {"band": "Yellow", "gain": 0.979, "offset": -5.489, "effective bandwidth": 0.0381, "band averaged solar_spectral irradiance (Thuillier 2003)": 1712.07},
                       {"band": "Red", "gain": 0.969, "offset": -4.579, "effective bandwidth": 0.0585, "band averaged solar_spectral irradiance (Thuillier 2003)": 1535.33},
                       {"band": "RedEdge", "gain": 1.027, "offset": -5.552, "effective bandwidth": 0.0387, "band averaged solar_spectral irradiance (Thuillier 2003)": 1348.08},
                       {"band": "NIR1", "gain": 0.977, "offset": -6.508, "effective bandwidth": 0.1004, "band averaged solar_spectral irradiance (Thuillier 2003)": 1055.94},
                       {"band": "NIR2", "gain": 1.007, "offset": -3.699, "effective bandwidth": 0.0889, "band averaged solar_spectral irradiance (Thuillier 2003)": 858.77}]

# These figures would ideally be read automatically from the *.imd file included with the Worldview-3 images.
# Since we don't actually have an *.imd file, we'll have to input them manually.
# These would be automatically read in the real version of the script.
abscal_factor = 0
earth_sun_distance = 0
solar_zenith_angle = 0

# This function sets the GUI progress bar maximum value to a figure equal to the height of the input image
def setProgressBarMaximum(xDim):
    progessBarOne['maximum']=xDim
    root.update_idletasks()

# As the script loops through the image and calculates the TOA reflectance values for each pixel,
# this function increases the progress bar value by 1 each time the script starts processing
# a new row of pixels on the y-axis
def makeProgress():
	progessBarOne['value']=progessBarOne['value'] + 1
	root.update_idletasks()

# This function gets the band chosen in the dropdown by the user
def getBand():
	return bands.get()

# This function gets the abscal factor input by the user in the input box
def getAbscalFactor():
    userInput = abscalfactor_input.get()
    return userInput

# This function gets the earth sun distance input by the user in the input box
def getEarthSunDistance():
	userInput = earthsundistance_input.get()
	return userInput

# This function gets the solar zenith angle input by the user in the input box
def getSolarZenithAngle():
	userInput = solarzenithangle_input.get()
	return userInput

def getValueFromBand(band, value):
    for b in calibration_figures:
        if (b['band'] == band):
            return b[value]

# This is the main function which does the calculation, called when
# the user chooses an input image
def choose_and_calculate():
    # A file dialog pops up, and asks the user to choose the file to process.
    # The path to that file (plus the filename) is stored in a variable called "path"
    path = os.path.abspath(filedialog.askopenfilename(initialdir = os.path.join(os.environ['HOMEPATH'], "Desktop"), title = "Choose the Worldview-3 image you want to calculate from"))
    # ALso, we'll get the file extension from the last part of the filename by splitting it
    # This is done because we are going to save a text file at the end of the script
    # and we're going to replace the file extension (for example, .jpg) with 
    # the text _resampled_and_converted.txt"
    file_extension = os.path.split(path)[len(os.path.split(path))-1].split(".")[1]
    
    # Read the chosen image and get the width and height
    image = imageio.imread(path)
    width = image.shape[1]
    height = image.shape[0]
    
    # Now that we know the height of the image, we'll set the progress bar maximum
    setProgressBarMaximum(height)
    
    # We'll get all the values of the input boxes of the GUI
    abscal_factor = float(getAbscalFactor())
    earth_sun_distance = float(getEarthSunDistance())
    solar_zenith_angle = float(getSolarZenithAngle())
    this_band = getBand()
    
    # Depending on the band the user chose to analyze, the gain, offset
    # effective bandwidth, and solar spectral irradiance figures will be different,
    # so we use a function (getValueFromBand) to retrieve the gain, offset,
    # effective bandwidth and solar spectral irradiance from the "calibration_figures" dictionary,
    # depending on the band that was chosen
    thisBandsGain = getValueFromBand(this_band, 'gain')
    thisBandsOffset = getValueFromBand(this_band, 'offset')
    thisBandsEffectiveBandwidth = getValueFromBand(this_band, 'effective bandwidth')
    thisBandsSolarSpectralIrradiance = getValueFromBand(this_band, 'band averaged solar_spectral irradiance (Thuillier 2003)')
    
    # This is an array which will hold the TOA reflectance values.
    # it is a 3D array simply because the input images I have access to are all 3-band images
    # (RGB).  This part of the code may have to be changed if the actual Worldview-3 images
    # turn out to be single-band
    toa_reflectance_values = zeros((height, width, 3), dtype=float32)
    
    # The text file containing the TOA reflectance values needs to be created at the end
    # of this script.  However, it is impossible with numpy to write a 3D array to a text file,
    # so here, we create a 2D array which will eventually hold the TOA reflectance values
    toa_reflectance_values_one_dimension = zeros((height, width), dtype=float32)
    
    # Here we go, a double for loop to get the values of each pixel and calculate the TOA reflectance
    for y in range(toa_reflectance_values.shape[0]):
        # We've started on a new y-axis row of pixels, so increase the progress bar by one
        makeProgress()
        for x in range(toa_reflectance_values.shape[1]):
            # Get the value of the pixel from the original image
            dn_of_this_pixel = image[y][x]
            
            # Calculate the TOA radiance of the pixel, using the value above and the values gotten from
            # the "calibration_figures" dictionary, as well as values the user input in the GUI
            toa_radiance_of_this_pixel = thisBandsGain * (dn_of_this_pixel * (abscal_factor/thisBandsEffectiveBandwidth)) + thisBandsOffset
            
            # Finally, get the TOA reflectance 
            toa_reflectance_of_this_pixel = (toa_radiance_of_this_pixel * pow(earth_sun_distance, 2) * math.pi) / (thisBandsSolarSpectralIrradiance * math.cos(solar_zenith_angle))
            
            # Put the value gotten above into the "toa_reflectance_values" array.  That is a 3D array, because
            # the input images used for testing are all 3-band (RGB) images
            toa_reflectance_values[y][x] = toa_reflectance_of_this_pixel
            
            # The array we will use to write the text file has to be a 2D array,
            # so here average the R, G and B values of the 3D array into one value, and place
            # it in the "toa_reflectance_values_one_dimension" array
            toa_reflectance_values_one_dimension[y][x] = (toa_reflectance_values[y][x][0] + toa_reflectance_values[y][x][1] + toa_reflectance_values[y][x][2]) / 3 

            
    # Finally, the double for loop is over, so we write the TOA reflectance values array to a text file
    numpy.savetxt(path.replace(file_extension, "_resampled_and_converted.txt"), toa_reflectance_values_one_dimension, newline="\n")
    
    # Show a success messagebox, and close the main window.  The program is complete.
    messagebox.showinfo("Complete", "Processing is complete.  A text file containing all the values is saved in the original directory with the name 'toa_reflectance.txt'.")
    root.destroy()
    
    # NOTE: The TOA reflectance value of each pixel could of course be used to brighten or darken 
    # each corresponding pixel of the original image, then an adjusted version of the original image
    # could be saved.  However, as I don't have access to actual Worldview-3 data, it was difficult
    # to know how to do this specifically.  I chose to output the TOA reflectance values to a text
    # file so they could be used by the user as necessary.
    
    # By parsing the text file (the values are separated by spaces, and the rows are separated by linebreaks)
    # the TOA reflectance values could easily be retrieved for use by another "image adjustment" script.
    # However, because of the way imageio (the Python image processing library) works, the image was
    # rotated 90 degrees during processing, so the values in the text file are also rotated.
    # For example, if it was a 10-pixel high and 5-pixel wide image, it is now
    # a 5-row 'high' and 10-column 'wide' text file.  We can take this into acccount if and when
    # we have to work with the text file.

# The code below is just for creating the GUI ---------------------------------------
root = Tk()
root.geometry('350x290')
root.configure(background='#E0EEEE')
root.title('Calculate TOA Reflectance')

bands= ttk.Combobox(root, values=['Pan', 'Coastal', 'Blue', 'Green', 'Yellow', 'Red', 'RedEdge', 'NIR1', 'NIR2'], font=('arial', 12, 'normal'), width=30)
bands.place(x=32, y=45)
bands.current(0)

Label(root, text='Choose a band', 
      bg='#E0EEEE', 
      font=('arial', 12, 'normal')).place(x=32, y=15)
Label(root, text='Earth-Sun distance', 
      bg='#E0EEEE', 
      font=('arial', 12, 'normal')).place(x=32, y=125)
Label(root, text='Abscal factor ', 
      bg='#E0EEEE', 
      font=('arial', 12, 'normal')).place(x=72, y=95)
Label(root, text='Solar zenith angle', 
      bg='#E0EEEE', 
      font=('arial', 12, 'normal')).place(x=42, y=155)

abscalfactor_input=Entry(root)
abscalfactor_input.insert(0, "float, for example 3.14")
abscalfactor_input.place(x=182, y=95)

earthsundistance_input=Entry(root)
earthsundistance_input.insert(0, "float, for example 3.14")
earthsundistance_input.place(x=182, y=125)

solarzenithangle_input=Entry(root)
solarzenithangle_input.insert(0, "float, for example 3.14")
solarzenithangle_input.place(x=182, y=155)

Button(root, text='Choose an image and calculate', 
       bg='#C1CDCD', 
       font=('arial', 12, 'normal'), 
       command=choose_and_calculate).place(x=52, y=195)

progessBarOne_style = ttk.Style()
progessBarOne_style.theme_use('clam')
progessBarOne_style.configure('progessBarOne.Horizontal.TProgressbar', 
                              foreground='#76EE00', 
                              background='#76EE00')

progessBarOne=ttk.Progressbar(root, 
                              style='progessBarOne.Horizontal.TProgressbar', 
                              orient='horizontal', 
                              length=290, 
                              mode='determinate', 
                              maximum=100, 
                              value=0)
progessBarOne.place(x=32, y=250)
root.mainloop()
#  ------------------------------------------------------------------------------