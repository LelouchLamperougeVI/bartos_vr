from __future__ import print_function
import GameLogic

import sys
sys.path.append('/usr/lib/python3/dist-packages')
sys.path.append('/home/behavior/.local/lib/python3.8/site-packages')
sys.path.append('/home/loulou/Downloads/blender-2.79b-linux-glibc219-x86_64/2.79/scripts/modules')

import bge
import time
import serial
import struct
import logging
from datetime import datetime
from os import walk
from os.path import join
import aud
import multiprocessing
import threading
import json
import numpy as np
#import bpy
import os, pty # testing without real arduino
import cProfile, pstats

import sys
import warnings

warnings.simplefilter("ignore")

try:
    # player object is not created 
    GameLogic.Object["player"]
    init = 0
except:
    # initialization
    init = 1

#bge.render.setWindowSize(5400, 1920)    
#bge.render.setFullScreen(True)
assets_path = ''
y_pos=0
reward_stat = 0
sound_stat = 0
freeze = False # freeze location, player cannot move
# reward_pump
class reward_event_():
    def __init__(self,pos,type,arduino,delay=0,platform=None) -> None:
        self.startPos = pos
        self.type = type
        self.active_stat = 0
        self.arduino = arduino
        self.platform = platform
        self.delay = delay
        
    def check_condition(self):
        global y_pos
        if y_pos > self.startPos and not self.active_stat:
            self.active_stat = 1
            if self.platform:
                scene = bge.logic.getCurrentScene()
                scene.objects[self.platform].position = [100,100,0]
            if self.type==1:
                sa = threading.Thread(target=self.reward1Thread)
                sa.start()
                
    def reward1Thread(self):
        global reward_stat, y_pos
        reward_stat = 1
        time.sleep(self.delay)
        logger_event = logging.getLogger("event_logger")
        print("Reward started: %.2f"%(y_pos)) 
        logger_event.info("Reward started: %.2f"%(y_pos))  
        # self.transmitCode(0x08)
        ser = serial.Serial('/dev/ttyUSB0')       
        for i in range(2):
            ser.setDTR(False)
            time.sleep(0.1)
            ser.setDTR(True)
            time.sleep(0.1)
        # self.transmitCode(0x09)
        reward_stat = 0
        logger_event.info("Reward ended: %.2f"%(y_pos))
        print("Reward ended: %.2f"%(y_pos))
    
    
# sound
class sound_():
    def __init__(self,pos,arduino) -> None:
        self.sound = aud.Factory.file("/home/behavior/gnoom/sounds/8000Hz.wav")
        self.arduino = arduino
        self.startPos = pos
        self.startCode = 0xB
        self.stopCode = 0xC
        self.active_stat = 0
    
    def check_condition(self):
        global y_pos,sound_stat
        if y_pos > self.startPos and not self.active_stat:
            self.active_stat = 1
            # sa = multiprocessing.Process(target=self.sound_thread)
            sa = threading.Thread(target=self.sound_thread)
            aud.device().play(self.sound)            
            sa.start()

    def sound_thread(self):
        global y_pos,sound_stat
        logger_event = logging.getLogger("event_logger")
        logger_event.info("Sound started: %.2f"%(y_pos))  
        print("Sound started: %.2f"%(y_pos))  
        sound_stat = 1
        # self.transmitCode(self.startCode)
        time.sleep(0.5)
        # self.transmitCode(self.stopCode)
        sound_stat = 0
        logger_event.info("Sound stopped: %.2f"%(y_pos))
         
class context:
    def __init__(self, ops) -> None:
        self.ops = { # default parameters
            "brake": False, # whether or not to apply brake
            "splash": None, # display a splash screen, either mention image file or None to disable
            "splash_dur": 0.0, # duration of splash screen
            "sound": None, # sound file, None to disable reward tone
            "sound_dur": 0.0, # duration of tone
            "reward_dur": 1.0, # duration of reward
            "trial_delay": 0.0, # blank screen at the end of each trial for set duration
            "env": [0, 160.0], # begining and end of track
            "rewards": [], # locations of rewards
            "towers": [None, None, None, None], # locations of towers, negative for left, positive for right
            "walls": [None, None, None, None, None, None, None, None], # list of file names for walls, None for black
            "floor": None, # floor texture, None for black
        }
        self.ops.update(ops)
        self.ls_towers = ['tower_r1', 'tower_r2', 'tower_l1', 'tower_l2']
        self.ls_walls = ['wall_l1', 'wall_r1', 'wall_l2', 'wall_r2', 'wall_l3', 'wall_r3', 'wall_l4', 'wall_r4']
        self.ls_floors = ['Cube']
        self._black = 'black.jpg'
        self.events = []
        self._end = False
        self._splashing = False
        
    def cycle(self): # cycle the routine
        for event_ in self.events:
            event_.check_condition()
        if self._splashing:
            
    def splash(self):
        global freeze
        freeze = True
    
    def end_trial(self):
        
    def paint(self, obj, path=None):
        prop_name = 'customTexture'
        if prop_name not in obj:
            tex = bge.texture.Texture(obj)
            obj[prop_name] = tex
        else:
            tex = obj[prop_name]
        if path is None:
            path = join(assets_path, 'images', self._black)
        else:
            path = join(assets_path, 'images', path)
        raw = bge.texture.ImageFFmpeg(path)
        if raw.status == 0:
            raise ValueError("Unable to load image at {}".format(path))
        tex.source = raw
        tex.refresh(True)
        
    def reset(self): # reset the scene
        return
        
    def activate(self): # make this context active
        self.reset() # start fresh
        
        # position rewards
        reward_pos = self.ops['rewards']
        #self.events.append(reward_event_(reward_pos,1,self.arduino,delay=0)) # attach reward triggers to reward locations
        #self.events.append(sound_(reward_pos,self.arduino)) # attach sound triggers to rewards
        
        # position towers
        scene = bge.logic.getCurrentScene()
        for t, x in zip(self.ls_towers, self.ops['towers']):
            if x is None:
                scene.objects[t].position = [0, -10, 10]
                continue
            if x < 0.0:
                scene.objects[t].position = [-10, x, 10]
            else:
                scene.objects[t].position = [10, x, 10]
        
        # paint the walls
        path = join(assets_path, "images")
        for w, f in zip(self.ls_walls, self.ops['walls']):
            obj = scene.objects[w]
            self.paint(obj,f)


class Player:
    def __init__(self) -> None:
        self.logicRate = 100
        GameLogic.setLogicTicRate(self.logicRate)                                         
        self.gain = 1.6                                                         #default should be replaced by value in setting file ("/home/behavior/gnoom/settings")
        self.gameCycles = 0                                                     # keeps track of game/logic cycles                
        self.initScreenDelay = 1 * self.logicRate                               # initial black screen delay [1 sec]                                                            
        self.Stop = 1                                                           # 1-> paused 0-> free used in evread.py
        self.finalScreenDelay = 10 * self.logicRate                             # blank screen at the end of run [2 secs]
        self.finalScreenDelay = np.random.randint(int(self.finalScreenDelay/2),self.finalScreenDelay)         # also log
        
        self.freezeDelay = 2*self.logicRate                                     # seconds to freeze screen at end of run before blank screen [2 secs]               
        self.blankScreenStat = 1                                                # current status of screen: 1-> dark
        self.interrupted = 0                                                    # esc is pressed
        self.y_pos = 0
        self.x_pos = 0
        self.lick_stat = 0
        self.events=[]
        self.cueDelay = 3*self.logicRate
        self.cameraReset = 0
        self.spatialRewardPos = 40.5
        self.soundRewardPos = 40.5
        self.currentContext = 0
        self.currentRun = 0
        self.runBlocks = 5
        self.runs = []
        self.total_runs = 0
        self.reward_delay = 1
        self.delay_bool = False
        with open('game.json','r') as json_file:
            data = json.load(json_file)
            self.runs_file_path = os.path.expanduser(data["runs_file_path"])
            self.assets_path = os.path.expanduser(data["assets_path"])
            global assets_path
            assets_path = os.path.expanduser(data['settings']["assets_path"])
            self.currentRun = int(data["current_run"])
            self.total_runs = int(data["total_runs"])
            self.delay_bool = data["delay"]
            self.reward_delay = data["reward_delay"]
            
            self.context = context(data['contexts']['A'])
            #if self.currentRun>=self.total_runs:
            #    bpy.ops.wm.quit_blender()
        
        with open(self.runs_file_path,'r') as json_file:
            data = json.load(json_file)
            self.currentContext = data["runs"][str(self.currentRun)]["context"]
            self.soundRewardPos  = data["runs"][str(self.currentRun)]["sound_pos"]


        # attach arduino -> try /dev/ttyACM0 to /dev/ttyACM9 (WILL NOT WORK IF MORE THAN ONE ARE CONNECTED)
        connected = False
        for i in range(10):
            try:
                name = '/dev/ttyACM{}'.format(i)
                print("trying to connect",name)
                self.arduino = serial.Serial(name, 115200, timeout=.1)
                connected = True
                break
            except: 
                pass
        if not connected:
            print("failed to connect to arduino, opening virtual port for testing")
            master, slave = pty.openpty()
            s_name = os.ttyname(slave)
            self.arduino = serial.Serial(s_name, 115200, timeout=0) # timeout non-blocking for testing
        print('Arduino initialized')
        
        self.context.activate()


    def reset_(self):
        with open("config.json",'r') as json_file:
            data = json.load(json_file)   
        # self.currentRun += 1                                  # apparently reset_ is called multiple times before blender gets reset
        data["current_run"] = self.currentRun + 1
        with open("config.json",'w') as json_file:
            json.dump(data,json_file,indent=4)
    
    def lick_value(self):
        OpMenuByte = 213
        handshakeByteString = struct.pack('<BB', OpMenuByte,0x03)
        self.arduino.write(handshakeByteString)
        Response=self.arduino.read(1)
        res=0
        try:
            res = struct.unpack('B',Response)[0]
        except:
            pass
        return res
    
    def send_pos_y(self,y):
        self.y_pos = y
        # initial value 5V until mouse starts moving then range[0.2,5]
        OpMenuByte = 213
        if self.blankScreenStat==1 or self.interrupted:
            value = 55049
        else:
            value = max(1311,(min(53740,1311+(y/165*52429))))
        handshakeByteString = struct.pack('<BBH', OpMenuByte,0x01,int(value))
        self.arduino.write(handshakeByteString)

    def log_xls(self):
        logger = logging.getLogger("excel_logger")
        logger.info("%d,%.2f,%d,%d,%d"%(self.currentContext, self.y_pos,sound_stat,reward_stat,self.lick_stat))
    
    def show_picture(self, obj, path=None):
        prop_name = 'customTexture'
        if prop_name not in obj:
            tex = bge.texture.Texture(obj)
            obj[prop_name] = tex
        else:
            tex = obj[prop_name]
        if path is None:
            path = join(assets_path, 'images', self._black)
        else:
            path = join(assets_path, 'images', path)
        raw = bge.texture.ImageFFmpeg(path)
        if raw.status == 0:
            raise ValueError("Unable to load image at {}".format(path))
        tex.source = raw
        tex.refresh(True)
        
    def paintClue(self): 
        mypath = join(self.assets_path, "images")
        scene = bge.logic.getCurrentScene()
        obj = scene.objects["Cube.011"]      
        if self.currentContext ==0:
            pattern_image = "diagonal_stripes.png"
        if self.currentContext ==1:
            pattern_image = "horizontal_stripes.png"
        image_path = join(mypath,pattern_image)
        self.show_picture(obj,image_path)
        camera = scene.objects['Camera']
        camera.position = [-4.71363,-0.882549,2]
        camera.localOrientation = [3.14,0,0]

    def resetCamera(self):
        scene = bge.logic.getCurrentScene()
        scene.objects['Camera'].position = [-4.71363,-0.882549,1.02404]
        scene.objects['Camera'].localOrientation = [3.14/2,0,0.139626]

    def generateSoundPos(self):
        pos = [x for x in range(50,110,6)]
        np.random.shuffle(pos)
        return pos


    # define main program
    def cycle(self):
        global y_pos  
        controller=bge.logic.getCurrentController()
        own=controller.owner
        scene = bge.logic.getCurrentScene()

        Location=own.worldPosition
        # Write locations for direction dependent collisions
        x=Location[0]
        y=Location[1]
        y_pos = y
        
        self.send_pos_y(y)

        self.lick_stat = self.lick_value()%2

        for event_ in self.events:
            event_.check_condition()
       
        self.log_xls()
        if self.gameCycles>self.initScreenDelay and self.gameCycles<(self.initScreenDelay + self.cueDelay):
            self.paintClue()
        if self.gameCycles > (self.initScreenDelay + self.cueDelay):
            if not self.cameraReset:
                self.cameraReset = 1
                self.resetCamera()
            if y_pos<165.5:
                self.Stop = 0
                scene.objects['Cube.003'].position = [100,100,0] 
                self.blankScreenStat = 0
            else:
                self.Stop = 1
                scene.objects['Player'].position = [0,165.5,2.7]
                if self.freezeDelay>0:
                    self.freezeDelay-=1
                else:
                    self.blankScreenStat = 1
                    scene.objects['Cube.003'].position = [0,y+0.3,0]
                    if self.finalScreenDelay>0:
                        self.finalScreenDelay-=1
                    else:
                        self.reset_()
                        print(self.currentRun)
                        GameAct = controller.actuators["restart"]
                        controller.activate(GameAct)
        
        self.gameCycles += 1
           
if not init:
    GameLogic.Object["player"].cycle()
    #profiler = cProfile.Profile()
    #profiler.enable()
    #GameLogic.Object["player"].cycle()
    #profiler.disable()
    #stats = pstats.Stats(profiler).sort_stats('cumulative')
    #stats.print_stats()
else:
    GameLogic.Object={}
    print("BLENDER: GameLogic object created")
    GameLogic.Object["player"] = Player()
  