#! /usr/bin/python
# Modified code: Art Miller - proto-type for Steam boat logging program.
#   Also includes shutdown procedure, also has (to the best of my ability) comments for 
#   all vars that are reported (at least that are in here)
# LICENSE: Until I've read the GPLv3 license, I'm just going to say that you are free to modify and/or
#   use in part or in whole any of the code below as long as Dan and I are credited as 'starting points'
# Original code: Written by Dan Mandle http://dan.mandle.me September 2012 License: GPL 2.0

# TODO: clean code, proof, debug, test


import os
from gps import *
from time import *
import time
import threading
import RPi.GPIO as GPIO

# global vars
gpsd = None #setting the global variable
isrunning = True #only set to false if button is pressed
shutdownbutton = False
f = None

# some constants, clean up later:
WAIT_TIME_NO_FIX = 5
WAIT_TIME_FIX = 1
class HaltPress( Exception ): pass

# gps polling thread:
class GpsPoller(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        global gpsd #bring it in scope
        gpsd = gps(mode=WATCH_ENABLE) #starting the stream of info
        self.current_value = None
        self.running = True #setting the thread running to true
 
    def run(self):
        global gpsd
        while gpsp.running:
            gpsd.next() #this will continue to loop and grab EACH set of gpsd info to clear the buffer

# 'debug' gps data output
def gpsDebugoutput():
    global gpsd
    os.system('clear')
    print
    print ' GPS reading'
    print '----------------------------------------'
    print 'latitude      ' , gpsd.fix.latitude
    print 'longitude     ' , gpsd.fix.longitude
    #print 'time utc      ' , gpsd.utc,' + ', gpsd.fix.time # not really needed, on-board RTC, only use when no RTC is present
    print 'altitude (ft) ' , gpsd.fix.altitude * METERS_TO_FEET
    #print 'eps         ' , gpsd.fix.eps * MPS_TO_MPH #speed error
    #print 'epd         ' , gpsd.fix.epd #Heading error
    #print 'epx         ' , gpsd.fix.epx * METERS_TO_FEET #horizontal x error NOTE: Same as y error
    #print 'epy         ' , gpsd.fix.epy * METERS_TO_FEET #horizontal y error NOTE: same as x error
    #print 'epv         ' , gpsd.fix.epv * METERS_TO_FEET #vertical error
    #print 'ept         ' , gpsd.fix.ept # time error
    #print 'epd         ' , gpsd.fix.epd # ?
    print 'speed (MPH)   ' , gpsd.fix.speed * MPS_TO_MPH # speed MIGHT be in knots. need testing
    #print 'climb         ' , gpsd.fix.climb * MPS_TO_MPH
    print 'heading       ' , gpsd.fix.track # heading
    print 'mode          ' , gpsd.fix.mode # 1 = no fix, 2 = 2d fix, 3 = 3d fix
    print '----------------------------------------'
    print 'sats:'
    for value in gpsd.satellites:
        print value
    return
    
def blink(pin):
    GPIO.output(pin, GPIO.LOW)
    time.sleep(1)
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(1)

# maybe add this in later?: GPIO.add_event_callback(channel, my_callback, bouncetime=200)
def buttonPress(channel):
    print "shutdown button pressed"
    global isrunning, shutdownbutton, f
    isrunning = False
    shutdownbutton = True
    f.write("Halt button pressed, shutting down\n")

if __name__ == '__main__':
    # setup the GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP) # switch for turning the pi off, use software edge detection
    GPIO.setup(18, GPIO.OUT) # led to notify when the pi is recording
    GPIO.add_event_detect(17, GPIO.FALLING, callback=buttonPress, bouncetime=300) # setup event detect
    GPIO.output(18,GPIO.HIGH) # indicate that we are 'recording'
    
    gpsp = GpsPoller() # create the thread
    try:
        curtime = time.strftime("%m-%d-%y %H:%M")
        f = open('/home/pi/logger/logs/' + curtime + '.log','w')
        f.write("time,lat,lon,alt,head,spd\n")
        gpsp.start() # start it up
        while isrunning:
            # Modified, no sense on getting data from the gps if we are just going to throw it away.
            if gpsd.fix.mode == 1:
                # sleep for a tiny bit and see if the gps gets a fix
                time.sleep(WAIT_TIME_NO_FIX) # 5 sec seems good enough, every 5 sec + main loop wait gives us some time to get a fix
            elif gpsd.fix.mode == 3 or gpsd.fix.mode == 2:
                #gpsDebugoutput()
                # grab all data for recording
                lat = gpsd.fix.latitude
                lon = gpsd.fix.longitude
                alt = gpsd.fix.altitude * METERS_TO_FEET
                spd = gpsd.fix.speed #* MPS_TO_MPH #not sure if base is in mps or knots... maybe record both base units and km/h?
                head = gpsd.fix.track
                strlog = "{0},{1},{2},{3:.2},{4:.1},{5:.1}\n".format(time.time(), lat, lon,  alt, head, spd)
                f.write(strlog)
                f.flush()
                time.sleep(WAIT_TIME_FIX) # in seconds, eventually plan on a 1+ min wait, for now get as much data as possible in a short time for testing
    
    except (KeyboardInterrupt, SystemExit): #when you press ctrl+c
        print "\nKilling Thread..."
        f.write("System or keyboard exit\n")
    except: # some other error happened, flash the green light a few times then exit
        f.write("Error occurred\n")
        # Blink the led, maybe throw in an error led later, maybe move the blinking to a thread?
        for x in range(10):
            blink(18)
    finally: # close the file and clean up
        gpsp.running = False
        gpsp.join()
        GPIO.output(18, GPIO.LOW) #just in-case it was left on for what ever reason
        f.flush()
        f.close()
        GPIO.cleanup()
    print "Done.\nExiting."
    if shutdownbutton == True:
        os.system("sudo shutdown -h now") # don't need a message because the system already does that for us
