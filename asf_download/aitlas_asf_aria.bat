:: Runs python script for automatized download of Sentinel SLC data
::
@echo off

:: Make sure R:\ (lidar) is mapped
net use l: /delete
net use l: \\172.16.10.10\lidar /persistent:yes
        o: \\iaps-24tera\opticni

:: PATH TO ARIA2 EXECUTABLE
set aria2_path=D:\nejc\aria2;
set PATH=%aria2_path%%PATH%

:: Change directory for download
cd /d l:
cd S1-aitlas

:: Start dawnload
aria2c --check-certificate=false --http-auth-challenge=true --http-user=cozn --http-passwd="slo61hrtNNN" "https://api.daac.asf.alaska.edu/services/search/param?platform=Sentinel-1&polygon=6.525,53.5239,5.1388,53.3312,4.6883,52.9431,3.6671,51.4616,3.701,51.3604,3.8892,51.2786,4.0315,51.2907,4.6536,51.5139,5.728,51.2399,5.7943,50.993,6.0069,50.9678,5.9937,51.0297,6.1438,51.2544,6.0052,51.8934,6.7445,51.9148,7.0795,52.4108,6.6637,52.5374,6.7445,52.6497,7.068,52.6497,7.2066,53.3174,6.525,53.5239&start=2017-01-01T00:00:00Z&end=2017-12-31T23:59:00Z&processingLevel=SLC&output=METALINK"

pause
