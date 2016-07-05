# monitor-ccs.py
Python based monitoring of Google Chromecasts and communication via MQTT to command and control

Requires pychromecast: https://github.com/balloob/pychromecast

Requires paho-mqtt: https://pypi.python.org/pypi/paho-mqtt/1.1


I do not remember where I got the code used to cast a file to a chromecast.  Once I figure that out I will give credit



Assumptions:

The services file assumes the python file is located in /usr/local/bin 

The services file assumed you have a user and group named 'openhab' to run the service as.  

The python script assumes it has a permission to write to /var/log/monitor-ccs.log

The MQTT server is running on the local host with no user name nor password required


MQTT Usage:

The service monitors MQTT for topics in the following format: chromecast/<device name>/command and the message is the command payload.  Most commands do not take addition arguments and are as follows: play, pause, stop, volume_up, volume_down, replay, skip, reboot, update.

Example: mosquitto_pub -t "chromecast/Bedroom-CC/command" -m "play"

The update command will cause the monitoring system to return data in the following format: chromecast/<device name>/<data type> and the message will contain the value for the data.  Data returned is: state, is_playing, title, series_title, artist, album, mediatype, thumbnail, volume, current, and duration.  This information can then be displayed within your command and control system (OpenHAB, Home Assistant, HomeSeer, etc, etc.)

Example: mosquitto_sub -t "chromecast/Bedroom-CC/series_title"

Commands that take additional parameters are set_volume and cast.  Parameters are seperated by a '|' character.

Example: mosquitto_pub -t "chromecast/Bedroom-CC/command" -m "set_volume|75"


Some additional OpenHAB specific configuration information can be found here: https://www.reddit.com/r/homeautomation/comments/4fc01z/quick_question_for_openhab_users/
