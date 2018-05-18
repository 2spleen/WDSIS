#!/usr/bin/env python3
import speedtest
import pymongo
import dateutil.parser as dp

### This script runs out of cron once every 5 minutes on a home raspberry pi,
### performs a speedtest using speedtest.net api,
### and inserts to MongoDB running in AWS (connected via OpenVPN)

### Setup
m_connection = pymongo.MongoClient("mongodb://aws-mongod.vpn")
db = m_connection.wdsis
speedtests = db.speedtests
s = speedtest.Speedtest()
s.get_best_server()
s.download()
s.upload()

### Document creation/anipulation
speedTestDoc = s.results.dict()
ts_string = speedTestDoc["timestamp"]
dt_object = dp.parse(ts_string)
speedTestDoc["timestamp"] = dt_object   # replace timestamp string with a datetime object so it is saved in mongo as an ISOdate type
epoch_ts = dt_object.strftime('%s')
speedTestDoc["epoch_timestamp"] = int(epoch_ts)   # insert an additional ts field in epoch format for my convenience/sanity

try:
    ### Ye Olde MongoDB insert ###
    speedtests.insert_one(speedTestDoc)
except Exception:
    raise
