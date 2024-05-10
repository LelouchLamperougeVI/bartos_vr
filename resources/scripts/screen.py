from bge import logic,render
import logging
from datetime import datetime
import os
from os import walk
from os.path import join
import sys
# import bpy
import json


logging.getLogger('bge').propagate = False
logging.getLogger('bpy').propagate = False

with open('config.json','r') as json_file:
            data = json.load(json_file)
            log_folder = data["log_folder"]
            runs_file_path = os.path.expanduser(data["runs_file_path"])
            currentRun = int(data["current_run"])
            total_runs = int(data["total_runs"])
            
        
with open(runs_file_path,'r') as json_file:
    data = json.load(json_file)
    currentContext = data["runs"][str(currentRun)]["context"]
            
            
log_path = join(log_folder,datetime.now().strftime("%Y_%m_%d"))

isExist = os.path.exists(log_path)
if not isExist:

   # Create a new directory because it does not exist
   os.makedirs(log_path)
   print("The new directory is created!")
   
formatter = logging.Formatter('%(asctime)s.%(msecs)03d, %(message)s',datefmt='%I:%M:%S')


def setup_logger(name, log_file, level=logging.INFO):
    """To setup as many loggers as you want"""

    handler = logging.FileHandler(log_file)        
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger

if currentContext==0:
      filename_pre = "position"
else:
      filename_pre = "sound"

# first file logger
# filename = os.path.basename(bpy.data.filepath.split('.')[0])+datetime.now().strftime("_%H_%M_%S")+'_events.log'
filename = filename_pre+datetime.now().strftime("_%H_%M_%S")+'_events.log'
file_path = join(log_path,filename)
logger_event = setup_logger('event_logger', file_path)

# second file logger
# filename = os.path.basename(bpy.data.filepath.split('.')[0])+datetime.now().strftime("_%H_%M_%S")+'_excel.xls'
filename = filename_pre +datetime.now().strftime("_%H_%M_%S")+'_excel.xls'
file_path = join(log_path,filename)
logger_xls = setup_logger('excel_logger', file_path)
logger_xls.info("%s,%s, %s, %s,%s"%("context","y_pos","sound_stat" ,"reward_stat","lick_stat"))



# logger_event.info("File : "+str(bpy.data.filepath))
logger_event.info("Contex: %s"%(str(currentContext)))
 

print("Script started at",datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

camList = logic.getCurrentScene().cameras
cam1 = camList['Camera']
cam2 = camList['Camera.001']

width = render.getWindowWidth()
height = render.getWindowHeight()

x = int(width/25)

cam1.setViewport(0,0,width,height)
cam2.setViewport(0,int(height/2),x,height)

cam1.useViewport = True
cam2.useViewport = True
cam2.setOnTop()