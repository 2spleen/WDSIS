#!/usr/bin/env python3
import subprocess
import pymongo
import datetime

### This script just runs out of cron once per minute on a home raspberry pi,
### gets load averages from home router running dd-wrt,
### and inserts to MongoDB running in AWS (connected via OpenVPN)

### Setup
m_connection = pymongo.MongoClient("mongodb://aws-mongod.vpn")
db = m_connection.wdsis
routerloads = db.routerloads

### Document creation/manipulation
output = subprocess.check_output(['ssh', '-q', 'root@dd-wrt', '"uptime"']) 
outStr = output.decode("utf-8")   # decode bytes array to string
load = outStr.split("load average:")[1].lstrip().rstrip().split(" ")  
loadOne = float(load[0].rstrip(","))   # one minute load average
loadFive = float(load[1].rstrip(","))   # five minute load average
loadFifteen = float(load[2])   # fifteen minute load average
dt_now = datetime.datetime.now()   # datetime object gets saved in mongo as an ISOdate type
epoch_now = int(dt_now.strftime('%s'))   # for my convenience/sanity
routerLoadDoc = {'timestamp': dt_now, 'epoch_timestamp': epoch_now, 'oneMinLoadAvg': loadOne, 'fiveMinLoadAvg': loadFive, 'fifteenMinLoadAvg': loadFifteen}

try:
    ### Ye Olde MongoDB insert ###
    routerloads.insert_one(routerLoadDoc)
except Exception:
    raise
