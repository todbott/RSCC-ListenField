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

# We'll keep track of the NDVI figures in Google Sheets (just for easy access)
# We'll also put them in a database (Google Cloud Datastore) for future reference
# Note: using another DB service such as CloudSQL would also work
from google.cloud import ndb

# In addition to uploading the NDVI images to Google Drive (for easy access)
# we will also upload them to Google Cloud Storage, so we need to import the gcs library
# as well as tempfile (which allows us to store the image as a temporary file before upload)
# and 'imageio' (an image reading/writing library)
from google.cloud import storage
from tempfile import NamedTemporaryFile
import imageio
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




# ---------------- Google Cloud Storage setup --------------------------------------------
# We can use the same credentials and key from above, just have to make a client here
storage_client = storage.Client("online-library-app", scredentials)
# ------------------------------------------------------------------------------------




# ---------------- Google Cloud Datastore setup -------------------------------------------
ndbclient = ndb.Client(project="online-library-app", credentials = scredentials)

# Here we define a model
class date_and_ndvi(ndb.Model):
    date = ndb.DateProperty()
    ndvi = ndb.FloatProperty()
    
# This function creates a new entity in the database, containing a date and NDVI score
def create_date_and_ndvi(date, ndvi):
    # The 'date' we have here is in this format: '2021-12-20' as a string.
    # To put it into Google Cloud Datastore as a DateProperty, we have to change it
    # into a datetime object, which we'll do here by splitting it
    ymd = date.split("-")
    date_for_database = datetime.date(int(ymd[0]), int(ymd[1]), int(ymd[2]))
    
    one = date_and_ndvi(
        date = date_for_database,
        ndvi = ndvi)
    one.put()
# ----------------------------------------------------------------------------------




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
    
    # --------------------------- save to Google Drive ---------------------------------------
    # Now let's save the image to our Google Drive Folder
    # (This is just in case someone without Google Cloud Platform
    # access just wants to see the images 'with one click' by 
    # logging into Gmail and going to Google Drive)
    Export.image.toDrive(image_with_ndvi, 
                         "NDVI band image",  # file description
                         "Landsat NDVI images", # folder name
                         dateToGet), # text to put in the filename 
    
    # --------------------------- save to GCS ------------------------------------------------
    # We will also save the image to Google Cloud Storage.
    # First, we get the destination bucket (folder).
    # (This is hard-coded in, but it could easily be passed in as a JSON value, as well)
    destination_bucket = storage_client.get_bucket('NDVI-images')
    
    # We'll have to save the image temporarily before uploading it...
    with NamedTemporaryFile() as temp:
        
        # Make an arbitrary name for the temporary file
        temp_file = "".join([str(temp.name), "going-to-GCS.jpg"])
        
        # Write the image to the temporary file
        imageio.imwrite(temp_file, image_with_ndvi)

        # Give the file a name (such as 'NDVI image from 2021-11-30.jpg')
        # Then, upload it to GCS
        dest_filename = "NDVI image from " + dateToGet + ".jpg"
        dest_blob = destination_bucket.blob(dest_filename)
        dest_blob.upload_from_filename(temp_file)
    
    # Because I don't have a GEE account, I couldn't test this next part,
    # but somehow it will be possible to get the NDVI score for the entire image as a figure (like 0.37)
    ndvi_score = sum(ndvi) / len(ndvi)  

    # --------------------------- write to Google Sheets ---------------------------------------
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
    
    # --------------------------- write to Google Cloud Datastore ------------------------------
    # Also, for more official storage that we can query and search in the future,
    # let's store the NDVI score in Google Cloud Datastore, as well (a database built-in to Google Cloud Platform)
    # We could also use CloudSQL (an SQL database), but for this example, I just chose 
    # Google Cloud Datastore
    with ndbclient.context():
        create_date_and_ndvi(dateToGet, ndvi_score)
    
    
    # That is the end of the process.
    # The image from 7 days before (with an NDVI band added) has been saved to our Google Drive folder
    # and the actual NDVI score for that date has been written to our Google Sheet
    
    # For more official use, the image has also been added to our Google Cloud Storage bucket
    # and the NDVI score has been saved in Google Cloud Datastore, along with the date
    
    # Let's return a 200 HTTP code, meaning "success!"
    status_code = Response(status=200)
    return status_code


    # Note: Depending on the company size and people involved in the project,
    # there may be times where someone with no Google Cloud Platform access wants to casually browse the NDVI
    # data or browse the NDVI satellite images. For that reason, I chose to put the images into Google Drive,
    # as anyone with a Gmail account (and proper rights) can access Google Drive.
    # I put the NDVI scores into Google Sheets for the same reason--so they could be accessed easily
    # by anyone in the company.
    
    # In the future on the data platform, NDVI images will need to be accessed and delivered to users
    # via API, and NDVI scores will have to be filtered, read and delivered via API.
    # To make such delivery easier, the images are also uploaded to Google Cloud Storage,
    # and the NDVI value/date pairs are written to Google Cloud Datastore (a database).
    
    # In summary, Google Drive/Sheets data is for anyone in-house who is curious and wants to 
    # access the data easily and quickly.
    # GCP/database data is for use in the data platform/API.
    

# This is just for debugging purposes (if running on localhost) --------------------
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True, threaded=True)
# ----------------------------------------------------------------------------------