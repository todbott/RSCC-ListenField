# -*- coding: utf-8 -*-
"""
Created on Wed Aug 11 22:54:34 2021

@author: Gillies
"""
# ------------------ Imports -------------------------------------------------------------
# Flask is a Python web framework 
# We will be putting this whole system into the cloud (via Google App Engine)
# and interacting with it via http/https, so we need to use Flask
from flask import Flask, Response

# This imports Earth Engine, a Python library for accessing Google Earth Engine
import ee
from ee import Export

# We need to access the environment varible (secret key for the app)
# from an external text file (*.yaml), so we need to import os
import os

# We have to get last week's date (each time we get a satellite image)
# so we have to import datetime and date
import datetime
from datetime import date

# We will need to use the Google Sheets API, so we need to make a service account
# and use the Python gspread library
from google.oauth2 import service_account
import gspread
# ------------------------------------------------------------------------------------



# ------------------ Google Sheets API setup-----------------------------------------------
# We will be using the Google Sheets API to write NDVI values to a Google Sheet
# Here we get the Google Sheets API key and make credentials 
skey_location = "online-library-app-43816975ead2.json"
scredentials = service_account.Credentials.from_service_account_file(skey_location)

# set the scopes for the spreadsheet interactions, and create a spreadsheet client
sheetscopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
spreadsheet_credentials = service_account.Credentials.from_service_account_file(
    skey_location,
    scopes = sheetscopes)
spreadsheet_client = gspread.authorize(spreadsheet_credentials)
# ------------------------------------------------------------------------------------



# ----------------------- Flask setup --------------------------------------------
app = Flask(__name__)  
# There is an 'app.yaml' file that will be uploaded to the cloud with this script
# Our'app.secret_key' is in that file.  It shouldn't be put into the code here,
# as someone could get access to the source code and find the key.  So, we put it in 
# as an environment variable instead
app.secret_key = os.environ['APP_KEY']
# ------------------------------------------------------------------------------------




# --------------------- API endpoint ------------------------------------------------
# This is the one and only 'endpoint' in our API here.
# A post request will be sent to this endpoint by Google Cloud Scheduler
# every 24 hours, resulting in 
#   1) a new image from GEE being sent to our Google Drive folder, and
#   2) the average NDVI score for the image being written to a special Google Sheet
@app.route('/trigger', methods=['POST'])
def trigger():

    # This is the point we want to see
    # (I hard-coded it in to the endpoint here, but it could very
    # easily be passed in as a JSON value, as well)    
    point = ee.Geometry.Point([-23.99, 67.53]);
    
    # This is the image collection we want to take from
    # (again, this could be passed in as a JSON value, instead of hard-coded)
    imageSet = ee.ImageCollection('LANDSAT/LC08/C01/T1_TOA');
    
    # I'm asssuming that it takes a while for images to be available on GEE,
    # so this system will always get the image from 7 days ago.
    # Here, we get today's date - 7 days, in 'yyyy-mm-dd' format
    # (for filtering purposes)
    dateToGet = (date.today() - datetime.timedelta(days=7)).strftime("20%y-%m-%d")
    
    # Here, we get the image, filtering by the point and the date (7 days ago)
    image = ee.Image(imageSet.filterBounds(point)
        .filterDate(dateToGet))
    
    # Here we get the NDVI from the image, and add it as a band
    ndvi = image.normalizedDifference(['B5', 'B4']).rename('NDVI');
    image_with_ndvi = image.addBands(ndvi)
    
    # Now let's save the image to our Google Drive Folder
    Export.image.toDrive(image_with_ndvi, 
                         "NDVI band image",  # file description
                         "Landsat NDVI images", # folder name
                         dateToGet), # text to put in the filename 
    
    # Because I don't have a GEE account, I couldn't test this next part,
    # but somehow it will be possible to get the NDVI score for the entire image as a figure (like 0.37)
    ndvi_score = sum(ndvi) / len(ndvi)  

    # Once we have the NDVI score, we can write it to a special Google Sheet
    # Let's assume the Google sheet is named "Landsat NDVI scores"
    book = spreadsheet_client.open("Landsat NDVI scores")
    # And the worksheet is named "data"
    sheet = book.worksheet("data")
    # Get all the data from the sheet
    dataToUpdate = sheet.get_all_values()        

    # Find the first empty row in the sheet
    # then put the date in column 1:
    sheet.update_cell(len(dataToUpdate)+1, 1, dateToGet) 
    # and put the ndvi score in column 2:
    sheet.update_cell(len(dataToUpdate)+1, 2, ndvi_score) 
    
    
    # That is the end of the process.
    # The image from 7 days before (with an NDVI band added) has been saved to our Google Drive folder
    # and the actual NDVI score for that date has been written to our Google Sheet
    # Let's return a 200 HTTP code, meaning "success!"
    status_code = Response(status=200)
    return status_code

      

# This is just for debugging purposes (if running on localhost) --------------------
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True, threaded=True)
# ----------------------------------------------------------------------------------