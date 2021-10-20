# -*- coding: utf-8 -*-
"""
Created on Tue Oct 19 16:28:41 2021

@author: Gillies
"""

import ee
import time
import datetime
from datetime import date
import json

from google.cloud import storage
import random

import rasterio

from tempfile import NamedTemporaryFile

from google.oauth2 import service_account

service_acct = 'agxactly-app-serviceaccount@agxactly-app-backend.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_acct, 'agxactly-app-backend-42b1257ae398.json')
ee.Initialize(credentials)

storage_credentials = service_account.Credentials.from_service_account_file('agxactly-app-backend-42b1257ae398.json')
storage_client = storage.Client("online-library-app", storage_credentials)

# Create a function that adds an NDVI band to a Sentinel-2 image
def addNDVI(image):
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI');
    return image.addBands(ndvi);


def cors_enabled_function(request):

    request_json = request.get_json(silent=True)
    request_args = request.args

    # For more information about CORS and CORS preflight requests, see:
    # https://developer.mozilla.org/en-US/docs/Glossary/Preflight_request

    # Set CORS headers for the preflight request
    if request.method == 'OPTIONS':
        # Allows GET requests from any origin with the Content-Type
        # header and caches preflight response for an 3600s
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }

        return ('', 204, headers)

    else:

        if request_json and 'coords' in request_json:
            coords = request_json['coords']
        elif request_args and 'coords' in request_args:
            coords = request_args('coords')

        print(coords)
        realCoords = json.loads(coords)
        print(realCoords)

        geometry = ee.Geometry.Polygon(realCoords);
        
        today = date.today()
        start = str(today.year) + "-" + str(today.month) + "-" + str(today.day)
        
        a_month_ago = date.today() - datetime.timedelta(days = 30)
        end = str(a_month_ago.year) + "-" + str(a_month_ago.month-1) + "-" + str(a_month_ago.day)
        
        S2_SR = ee.ImageCollection('COPERNICUS/S2_SR').filterBounds(geometry).filterDate(end, start);
        
        # Apply this function across your image collection
        S2_NDVI = S2_SR.map(addNDVI);
        
        # Sort the image collection by date and select the most recent image
        recent_S2 = ee.Image(S2_NDVI
                            #.sort('CLOUD COVER').first());
                            .sort('system:time_start', False).first());
        
        #Print the image’s metadata to the console to view its metadata
        dateTaken = recent_S2.date().format().getInfo().split("T")[0]
        print(dateTaken)
        
        recent_S2_for_export = recent_S2.select('NDVI').visualize(**{
            'min': 0,
            'max': 1,
            'palette': ['FF0000', 'FFA500', '00FF00']
        })
        
        
        nameForFile = str(random.random()).replace(".", "") + '_' + dateTaken
        
        task = ee.batch.Export.image.toCloudStorage(
            image=recent_S2_for_export,
            region=geometry,
            description='an image from the iPhone frontend',
            bucket='braga-agx-native',
            fileNamePrefix=nameForFile,
            scale=1,
            crs='EPSG:4326')
        
        task.start()
        
        done = False
        while done == False:
            state = task.status()['state']
            print(state)
            time.sleep(5)
            if (state == 'COMPLETED'):
                done = True
            
        print("task has completed")
        
        # Now, download it to temp file, change the format with rasterio,
        # and re-upload it to cloud storage
        
        destination_bucket = storage_client.get_bucket('braga-agx-native')
        with NamedTemporaryFile() as tempTiff:
            # Extract name to the temp file
            tempTiff_file = "".join([str(tempTiff.name), "from_the_cloud.tif"])
            blob = destination_bucket.blob(nameForFile + ".tif")
            # Download the file to a destination
            blob.download_to_filename(tempTiff_file)
            
            # convert it with rasterio
            with rasterio.open(tempTiff_file) as infile:
                profile=infile.profile
                #
                # change the driver name from GTiff to PNG
                #
                profile['driver']='PNG'
                
                with NamedTemporaryFile() as tempPng:
                    tempPng_file = "".join([str(tempPng.name), "to_the_cloud.png"])
                    
                    raster=infile.read()
                    with rasterio.open(tempPng_file, 'w', **profile) as dst:
                        dst.write(raster)
                        
                    dest_blob = destination_bucket.blob(nameForFile + ".png")
                    dest_blob.upload_from_filename(tempPng_file)
                    

        url = "https://storage.googleapis.com/braga-agx-native/" + nameForFile + ".png"

        

    # Set CORS headers for the main request
    headers = {
        'Access-Control-Allow-Origin': '*'
    }
    
    value = {
        "imageURL": url,
        "dateTaken": dateTaken
    }
    
    returnPackage = json.dumps(value)
    
            
    
    return (returnPackage, 200, headers)
