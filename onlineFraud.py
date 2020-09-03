#!/usr/local/bin/python3

# Written in Python 3.7.2
# Written by: Izz Noland
# Version 0.5.1 - 09/02/2020

"""
RELEASE NOTES
0.5.1 - moved secrets to environment variables, cleaned prod data for push to public repo
0.4.6 - Fixed comparison in alertOnce() to remove CRLF & set TO = Izz & Chris
0.4.5 - Added daily alerting if fraudulent activity is detected
0.4.0 - Setup as an AWS Lambda function with upload to S3 as website
0.3.0 - Added functionality for warnings based on date
0.2.0 - Modularized script for geoloc lookup, json parsing, and html output
0.1.0 - Initial query for rate limiting bot in Elasticsearch
"""

import requests
from datetime import timezone
import datetime
import boto3
import smtplib
from email.message import EmailMessage


# aws-p-smtp-01
# 10.60.5.190
def sendEmail():
    # send to Izz and Chris
    recipients = ["emailAddy1@example.com", "emailAddy2@example.com"]

    # compose body, and headers
    msg = EmailMessage()
    body = "Please review " \
           "https://notreal-onlinegivinginfoscript.s3.amazonaws.com/index.html " \
           "for more information on recent activity. Monitoring has found rate " \
           "limits placed today. You will not be alerted again today on activity."
    msg.set_content(body)
    msg['Subject'] = "Fraudulent Activity Found!"
    msg['From'] = "noreply@example.com"
    msg['To'] = ", ".join(recipients)

    # send the email
    server = smtplib.SMTP('10.60.5.190')
    server.send_message(msg)
    server.quit()


# retrieves data from ElasticSearch API
def getData(url):
    r = requests.get(url=url)

    if r.status_code != 200:
        print("What the hell dude?\n")
        exit(code=255)
    else:
        data = r.json()
        return data


# set the flag as necessary
def setFlag():
    # we are only going to send an alert on first instance of activity each day
    currentTime = datetime.datetime.now() - datetime.timedelta(hours=5)

    # setup our s3 info
    s3 = boto3.resource("s3")
    bucket = s3.Bucket("notreal-onlinegivinginfo")

    # open file for writing
    alertfile = open("/tmp/alert.log", "w+")

    # clear flag for the today
    if currentTime.hour == 17:
        alertfile.write("0")
        alertfile.close()

        # upload the cleared alert flag to s3
        object = bucket.put_object(ACL="public-read", Body=open("/tmp/alert.log", "rb"), ContentType="text/plain",
                                   Key="alert.log")
    else:
        alertfile.write("1")
        alertfile.close()

        # upload the set alert flag to s3
        object = bucket.put_object(ACL="public-read", Body=open("/tmp/alert.log", "rb"), ContentType="text/plain",
                                   Key="alert.log")


# check for today's alerting and fire off email if needed
def alertOnce():
    # check bucket and send alert here
    s3alert = boto3.resource('s3')
    s3alert.meta.client.download_file("notreal-onlinegivinginfo", "alert.log", "/tmp/s3alerts.log")
    alertStatus = open("/tmp/s3alerts.log", "r")
    status = alertStatus.read()
    alertStatus.close()

    currentTime = datetime.datetime.now() - datetime.timedelta(hours=5)

    if (status.rstrip() == "0") and (currentTime.hour != 17):
        # send an alert
        sendEmail()
        setFlag()
    elif status.rstrip() == "1":
        # do nothing, we've already sent an alert for today
        setFlag()
    else:
        setFlag()


# Converts from UTC to localtime
def convertToLocalTime(utcString):
    utc = datetime.datetime.strptime(utcString, "%Y-%m-%dT%H:%M:%S.%fZ")
    localtime = utc.replace(tzinfo=timezone.utc, microsecond=0).astimezone(tz=None) - datetime.timedelta(hours=5)
    today = datetime.datetime.today().date()
    if localtime.date() == today:
        warning = True
        alertOnce()
    else:
        warning = False
    return str(localtime)[:-6], warning


# our geoIP lookup function
def geoIPLookup(sourceIP):
    izzAccessKey = os.environ.get('API_PASSWORD')
    apiconstruct = "http://api.ipstack.com/" + sourceIP + "?access_key=" + izzAccessKey
    geo = requests.get(url=apiconstruct)

    if geo.status_code != 200:
        print("You did something again dummy?!\n")
        exit(code=255)
    else:
        geoData = geo.json()
        return geoData["country_name"], geoData["region_name"], geoData["city"]


# extracts IP and datetime while doing geoIP lookup
def parse_body_data(data, recs):
    record = data["hits"]["hits"]

    outList = []

    for i in range(0, int(recs)):
        localtime, isToday = convertToLocalTime(record[i]["_source"]["@timestamp"])
        fullMessage = record[i]["_source"]["message"]

        try:
            clientIP = record[i]["_source"]["clientip"]
        except:
            sourceIP = fullMessage.split(" ", 1)
            clientIP = sourceIP[0]

        country, region, city = geoIPLookup(clientIP)
        tmpList = [localtime, clientIP, country, region, city, isToday]
        outList.append(tmpList)

    return outList


# create as nice little html page
def createHTML(data):
    outfile = open("/tmp/index.html", "w+")
    strTable = "<html><head><style>table { border-collapse:collapse; width: 100%;} th, td " \
               "{ text-align: left; padding: 8px; }" \
               "tr:nth-child(even) {background-color: #dddddd} " \
               "th { background-color: #999999; color: white; } </style></head><body" \
               ">" \
               "<table><tr><th>Time</th><th>IP</th><th>Country</th><th>Region</th><th>City</th></tr>"

    while data:
        datapoints = data.pop(0)

        # override background color if there are hits today
        if datapoints[5]:
            strROW = '<tr style="background-color:#f60606">'
            # sendEmail()
        else:
            strROW = '<tr>'
        strROW = strROW + "<td>" + str(datapoints[0]) + "</td><td>" + str(datapoints[1]) + "</td><td>" + str(
            datapoints[2]) + \
                 "</td><td>" + str(datapoints[3]) + "</td><td>" + str(datapoints[4]) + "</td></tr>"

        strTable = strTable + strROW

    currentTime = datetime.datetime.now() - datetime.timedelta(hours=5)
    currentTime = currentTime.strftime("%Y-%m-%d %H:%M")

    strROW = '<tr style="background-color:#ffffff">'
    strROW = strROW + "<td></td><td></td><td></td><td></td><td></td><td></td></tr>"
    strROW = strROW + '<tr style="background-color:#ffffff">'
    strROW = strROW + "<td></td><td></td><td></td><td></td><td></td><td></td></tr>"
    strROW = strROW + '<tr style="background-color:#ffffff">'
    strROW = strROW + "<td></td><td></td><td></td><td></td><td></td><td></td></tr>"
    strROW = strROW + '<tr style="background-color:#ffffff">'
    strROW = strROW + "<td></td><td></td><td></td><td></td><td></td><td></td></tr>"
    strROW = strROW + '<tr style="background-color:#ffffff">'
    strROW = strROW + '<td></td><td></td><td></td><td></td><td style="text-align:right">Last Updated:<br>' + currentTime + "</td></tr>"

    strTable = strTable + strROW + "</table></html>"
    strTable = strTable + "</table></html>"

    outfile.write(strTable)
    outfile.close()

    s3 = boto3.resource('s3')
    bucket = s3.Bucket("notreal-onlinegivinginfo")
    object = bucket.put_object(ACL="public-read", Body=open("/tmp/index.html", "rb"), ContentType="text/html",
                               Key="index.html")


# main
def main():
    # numRecords = input("How many records would you like to retrieve?\t")
    numRecords = 15
    baseURL = "https://search-izz-elk-5-somerandomstringofcharacters.us-east-1.es.amazonaws.com/_search"
    query = "f5status:bot%20AND%20message:exceeded&size=" + str(numRecords) + "&sort=@timestamp:desc"
    data = getData(baseURL + "?q=" + query)
    dataPoints = parse_body_data(data, numRecords)
    createHTML(dataPoints)


def lambda_handler(event, context):
    main()


if __name__ == "__main__":
    main()
