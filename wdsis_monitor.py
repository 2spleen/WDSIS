#!/usr/bin/env python3
import pymongo
import threading
import time, datetime
from twilio.rest import Client as tw_client

### This script runs as a poor mans service (nohupped in the background),
### polls the routerloads collection and alerts if not being created,
### watches for inserts to the speedtests collection via a change stream,
### calculates average internet connection metrics over the last 30 minutes,
### and alerts if performance is below minimum levels defined here.

### Setup
m_connection = pymongo.MongoClient("mongodb://localhost")
db = m_connection.wdsis
speedtests = db.speedtests
routerloads = db.routerloads
last_alert_sent = int(datetime.datetime.now().strftime('%s')) - 3601   # initialize to an hour in the past

### Tweakable defaults
avg_dl_alert_limit = 10   # send an alert if average download speed is less than this limit (in mbit) for a 30 minute sampling of speedtests
avg_ul_alert_limit = 1   # send an alert if average upload speed is less than this limit (in mbit) for a 30 minute sampling of speedtests
avg_png_alert_limit = 100   # send an alert if average ping is greater than this limit (in ms) for a 30 minute sampling of speedtests

### Function definitions
def txt_alert(msg):
    """function to send me text messages via twilio, rate-limited to one per hour """
    global last_alert_sent
    tw_account_sid = "REDACTED"
    tw_auth_token = "REDACTED"

    epoch_now = int(datetime.datetime.now().strftime('%s'))
    last_alert_elapsed = (epoch_now - last_alert_sent)
    if last_alert_elapsed > 3600:   # need to send an alert since there hasn't already been one in the last hour...
        twc = tw_client(tw_account_sid, tw_auth_token)
        twc.messages.create(body=msg, from_="+18172412027", to="+12543962759")
        last_alert_sent = epoch_now
    else:
        pass   # have already sent an alert in the last hour, don't spam me bro...

def rl_poller():
    """background thread function to alert if no routerloads are being created..."""
    while True:
        ### Ye Olde MongoDB find query ###
        last_st_epoch_timestamp = int(routerloads.find({}, {"epoch_timestamp": 1, "_id": 0}).sort("epoch_timestamp", pymongo.DESCENDING).limit(1)[0]["epoch_timestamp"])
        epoch_now = int(datetime.datetime.now().strftime('%s'))
        elapsed = (epoch_now - last_st_epoch_timestamp)
        if elapsed > 300:   # if we've gone 5 minutes without a routerload being inserted it should be safe to assume the connection is down
            txt_alert("Spectrum Connection Down!")
        time.sleep(60)   # poll every 60 seconds

def st_insert_handler(st_insert_event):
    """function called by the main event loop to annalyze recent connection metrics when new speedtests are inserted"""
    download =  st_insert_event["fullDocument"]["download"]
    upload =  st_insert_event["fullDocument"]["upload"]
    ping = st_insert_event["fullDocument"]["ping"]
    epoch_now = int(datetime.datetime.now().strftime('%s'))
    pipeline = [
                {"$match": {"epoch_timestamp": {"$gt": (epoch_now - 1800)}}},   # evaluate speedtests from the last 30 minute period (should be just ~6 documents)
                {"$group": {"_id": None, "average_download": {"$avg": "$download"}, "average_upload": {"$avg": "$upload"}, "average_ping": {"$avg": "$ping"}}},
                {"$project": {"_id": 0}}
    ]
    ### Ye Olde MongoDB aggregation query ###
    result = speedtests.aggregate(pipeline).next()
    avg_dl = result["average_download"] / 1000000   # convert to Mbit
    avg_ul = result["average_upload"] / 1000000   # convert to Mbit
    avg_png = int(result["average_ping"])
    print(datetime.datetime.now().isoformat() + "   Yay - new speedtest doc inserted, new averages for last 30 minutes: " +
          "%.1f" % avg_dl + " Mbit download, " + "%.1f" % avg_ul + " Mbit upload, " + str(avg_png) + " ms ping.")

    if avg_dl < avg_dl_alert_limit or avg_ul < avg_ul_alert_limit or avg_png > avg_png_alert_limit:   # simple/generic recent aggregate performance alert
        txt_alert("Spectrum Connection metrics suck for the last 30 minutes!")

        
### Main
print("Polling in a background thread to monitor time elapsed since the last routerload document was inserted...")
t = threading.Thread(target=rl_poller)
t.start()   # start rl_poller thread

print("Entering main event loop to examine inserted speedtest documents as they are received from the changestream...")
try:
    ### Ye Olde MongoDB ChangeStream ###
    with speedtests.watch([{'$match': {'operationType': 'insert'}}]) as st_stream:
        for st_insert_event in st_stream:
            st_insert_handler(st_insert_event)
except pymongo.errors.PyMongoError as err:
    print("pymongo error: " + str(err))
