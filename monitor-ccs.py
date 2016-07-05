#!/usr/bin/python
from __future__ import print_function
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt
import pychromecast
import os
import sys
import logging

import time
import BaseHTTPServer
import urllib
import mimetypes
from threading import Thread
import thread
import traceback
import socket
import fcntl
import struct

def get_mimetype(filename):
    """ find the container format of the file """
    # default value
    mimetype = "video/mp4"
    
    
    # guess based on filename extension
    guess = mimetypes.guess_type(filename)[0].lower()
    if guess is not None:
        if guess.startswith("video/") or guess.startswith("audio/"):
            mimetype = guess
      
        
    # use the OS file command...
    try:
        file_cmd = 'file --mime-type -b "%s"' % filename
        file_mimetype = subprocess.check_output(file_cmd, shell=True).strip().lower()
        
        if file_mimetype.startswith("video/") or file_mimetype.startswith("audio/"):
            mimetype = file_mimetype
            logger.debug("OS identifies the mimetype as :" + mimetype)
            return mimetype
    except:
        pass
    
    
    return mimetype
    

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])
	
	
class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    content_type = "video/mp4"
    
    """ Handle HTTP requests for files which do not need transcoding """
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", self.content_type)
        self.end_headers()
        
        filepath = urllib.unquote_plus(self.path)
        
        self.write_response(filepath)

    def write_response(self, filepath):
        with open(filepath, "r") as f: 
            self.wfile.write(f.read())  
	

def cast_media(device, filename):

	if os.path.isfile(filename):
		filename = os.path.abspath(filename)
	else:
		return

	logger.debug("Playing: " + filename)

	mimetype = get_mimetype(filename)
	cast = getDeviceNamed(device)
	webserver_ip = get_ip_address('eth0')

	logger.debug("my ip address: " + webserver_ip)
		
	req_handler = RequestHandler
	req_handler.content_type = mimetype

	# create a webserver to handle a single request on a free port        
	server = BaseHTTPServer.HTTPServer((webserver_ip, 0), req_handler)

	thread = Thread(target=server.handle_request)
	thread.start()    

	url = "http://%s:%s%s" % (webserver_ip, str(server.server_port), urllib.quote_plus(filename, "/"))
	logger.debug("Serving media from: " + url)
	logger.debug("mime type: " + mimetype)
	
	mc = cast.device.media_controller
	mc.play_media(url, mimetype)
	
	# wait for playback to complete before exiting
	logger.debug("waiting for player to finish...")    

	idle = False
	while not idle:
		time.sleep(1)
		idle = (cast.device.media_controller.status.player_state == "IDLE")
	
	server.server_close()

	logger.debug("Player finished")

	
def getDeviceNamed(name):
	for myDevice in myDevices:
		if myDevice.device.name == name:
			return myDevice
	return None;

def on_mqtt_connect(client, userdata, flags, rc):
	for device in devices:
		client.subscribe("chromecast/{0}/command".format(device.name))

		
def on_mqtt_message(client, userdata, msg):
	logger.debug(msg.topic+" "+str(msg.qos)+" "+str(msg.payload))
	device = msg.topic.split("/")[1]
	
	command = msg.payload.split("|")
	try:	
		if command[0] == "play":
			getDeviceNamed(device).device.media_controller.play()
			getDeviceNamed(device).forceUpdate()
			logger.info("%s command play", device)
		if command[0] == "pause":
			getDeviceNamed(device).device.media_controller.pause()
			getDeviceNamed(device).forceUpdate()
			logger.info("%s command pause", device)
		if command[0] == "stop":
			getDeviceNamed(device).device.quit_app()
			getDeviceNamed(device).forceUpdate()
			logger.info("%s command stop", device)
		if command[0] == "volume_up":
			getDeviceNamed(device).device.volume_up()
			getDeviceNamed(device).forceUpdate()
			logger.info("%s command volume up", device)
		if command[0] == "volume_down":
			getDeviceNamed(device).device.volume_down()
			getDeviceNamed(device).forceUpdate()
			logger.info("%s command volume down", device)
			
			
		if command[0] == "set_volume":
			getDeviceNamed(device).device.set_volume(float(str(command[1])) / 100)
			getDeviceNamed(device).forceUpdate()
			logger.info("%s command sert volume", device)
			
		if command[0] == "replay":
			getDeviceNamed(device).device.media_controller.seek(getDeviceNamed(device).media_controller.status.current_time - float(str(command[1])))
			getDeviceNamed(device).forceUpdate()
			logger.info("%s command replay", device)
		if command[0] == "skip":
			getDeviceNamed(device).device.media_controller.seek(getDeviceNamed(device).media_controller.status.current_time + float(str(command[1])))
			getDeviceNamed(device).forceUpdate()
			logger.info("%s command skip", device)

		if command[0] == "reboot":
			getDeviceNamed(device).device.reboot()
			logger.info("%s command reboot", device)
			
		if command[0] == "update":
			getDeviceNamed(device).forceUpdate()
			getDeviceNamed(device).sendDeviceStatus()
			logger.debug("%s command update", device)

		if command[0] == "cast":
			thread.start_new_thread(cast_media, (device, command[1], ))
			logger.info("%s command cast %s", device, command[1])
	
	except:
			logger.error("%s", sys.exc_info()[0])


class DeviceStatusUpdater:
	def __init__(self, device):
		self.device = device
		self.thumbnail = ""
		self.sendDeviceStatus()
		self.device.media_controller.register_status_listener(self)
		
	def new_media_status(self, status):
		self.sendDeviceStatus()
		
	def forceUpdate(self):
		self.device.socket_client._force_recon=True
		
	def addDeviceInfo(self, topic, payload):
		logger.debug("%s info: %s - %s", str(self.device.name), topic, payload)
		return {"topic":"chromecast/{0}/{1}".format(str(self.device.name), topic), "payload":payload}
	
	def sendDeviceStatus(self):
		global publish
		deviceInfo = []
		
		deviceInfo.append(self.addDeviceInfo("name", self.device.name))
		deviceInfo.append(self.addDeviceInfo("host", self.device.host))

		if len(str(self.device.app_display_name)):
			deviceInfo.append(self.addDeviceInfo("app",  self.device.app_display_name))
		else:
			deviceInfo.append(self.addDeviceInfo("app", "None"))


		if self.device.media_controller is not None:
			if self.device.media_controller.status is not None:
				deviceInfo.append(self.addDeviceInfo("state", self.device.media_controller.status.player_state))
				
				if self.device.media_controller.status.player_state == pychromecast.controllers.media.MEDIA_PLAYER_STATE_PLAYING:
					deviceInfo.append(self.addDeviceInfo("is_playing", "ON"))
				else:
					deviceInfo.append(self.addDeviceInfo("is_playing", "OFF"))
					
				deviceInfo.append(self.addDeviceInfo("title", 			self.device.media_controller.status.title))
				deviceInfo.append(self.addDeviceInfo("series_title", 		self.device.media_controller.status.series_title))
				deviceInfo.append(self.addDeviceInfo("artist", 			self.device.media_controller.status.artist))
				deviceInfo.append(self.addDeviceInfo("album", 			self.device.media_controller.status.album_name))
				deviceInfo.append(self.addDeviceInfo("mediatype", 		self.device.media_controller.status.metadata_type))
				deviceInfo.append(self.addDeviceInfo("thumbnail", 		self.device.media_controller.thumbnail))
				deviceInfo.append(self.addDeviceInfo("volume", 			str(float(self.device.status.volume_level) * 100)))
				deviceInfo.append(self.addDeviceInfo("current",                 self.device.media_controller.status.current_time))

				duration = self.device.media_controller.status.duration
				if duration is None:
					duration = -1
				deviceInfo.append(self.addDeviceInfo("duration", 		duration))
				
				if self.thumbnail is not self.device.media_controller.thumbnail and self.device.media_controller.thumbnail is not None:
					os.system("wget {1} -O /usr/share/openhab/webapps/images/{0}.png".format(self.device.name, self.device.media_controller.thumbnail))
					#os.system("/usr/bin/convert /usr/share/openhab/webapps/images/{0}.png -resize 128x128 /usr/share/openhab/webapps/images/{0}.png".format(self.device.name))
					self.thumbnail = self.device.media_controller.thumbnail
				
		publish.multiple(deviceInfo)

				
#logging.basicConfig(filename='/var/log/monitor-ccs.log', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.DEBUG)		
logging.basicConfig(filename='/var/log/monitor-ccs.log', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
logger = logging.getLogger('monitor-ccs')
		
logger.info("Begin device discovery...")
devices = pychromecast.get_chromecasts()
myDevices = []
for device in devices:
	# Wait for cast device to be ready
	device.wait()
	logger.info("Discovered device: %s (%s) - %s", device.device.friendly_name, device.host, device.model_name)
	logger.debug("Discovered device: %s", str(device))
	myDevices.append(DeviceStatusUpdater(device))

client = mqtt.Client()
client.on_connect = on_mqtt_connect
client.on_message = on_mqtt_message
client.connect("localhost")
logger.info("MQTT connect...")
client.loop_forever()	
client.disconnect()	
