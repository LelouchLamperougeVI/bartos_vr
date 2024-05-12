from __future__ import print_function
import GameLogic

import sys
import os
import re
import bge
import time
import serial
import struct
import logging
from datetime import datetime
import aud
import multiprocessing
import threading
import json
import numpy as np
import itertools
import pty # testing without real arduino
import cProfile, pstats
import warnings

warnings.simplefilter("ignore")

#bge.render.setWindowSize(5400, 1920)
#bge.render.setFullScreen(True)
reward_stat = 0
sound_stat = 0

chan_map = {}

def position(y=None): # get/set player's current position
    scene = bge.logic.getCurrentScene()
    if y is None:
        return scene.objects['Player'].position[1]
    else:
        scene.objects['Player'].position = [0, y, 2.7]

def transmit(arduino, do=None, value=None): # transmitting signals through pulse pal
    opcode = 213
    if do == 'handshake':
        handshakeByteString = struct.pack('BB', opcode, 72)
        arduino.write(handshakeByteString)
        Response = arduino.read(5)
        fvBytes = Response[1:5]
        firmwareVersion = struct.unpack('<I',fvBytes)[0]
        print('Handshake complete. Firmware version {}'.format(firmwareVersion))
        arduino.write('YPYTHON')
    elif do == 'pos':
        voltage = math.ceil(((voltage+10)/float(20))*255) # Convert volts to bytes
        mesg = struct.pack('BBBB', opcode, 79, chan_map['pos'], voltage)
        arduino.write(mesg)
    elif do == 'trial':

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
        ser = serial.Serial('/dev/ttyUSB0')
        for i in range(2):
            ser.setDTR(False)
            time.sleep(0.1)
            ser.setDTR(True)
            time.sleep(0.1)
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
            "env": 160.0, # begining and end of track
            "rewards": [], # locations of rewards
            "towers_pos": [None, None, None, None], # locations of towers, negative for left, positive for right
            "towers": [None, None, None, None], # textures for towers, None for black
            "walls": [None, None, None, None, None, None, None, None], # list of file names for walls, None for black
            "floors": [None], # floor texture, None for black
        }
        self.ops.update(ops)
        self.ls_towers = ['tower_r1', 'tower_r2', 'tower_l1', 'tower_l2']
        self.ls_walls = ['wall_l1', 'wall_r1', 'wall_l2', 'wall_r2', 'wall_l3', 'wall_r3', 'wall_l4', 'wall_r4']
        self.ls_floors = ['Cube']
        self._black = 'black.jpg'
        self.reset()

    def cycle(self): # cycle the routine
        tic = self._clock / self.ops['logicRate']
        for event_ in self.events:
            event_.check_condition()
        if self._splashing and self._splash_dur <= tic:
            scene = bge.logic.getCurrentScene()
            scene.objects['Camera'].position = [-4.71363,-0.882549,1.02404]
            scene.objects['Camera'].localOrientation = [3.14/2,0,0.139626]
            self._splashing = False
        self._clock += 1
        if position() >= self.ops['env']:
            self.splash(blank=True)
            self._splash_dur = self.ops['trial_delay']
            self._clock = 0
            self._end = True
        self.done = self._end and (not self._splashing)

    def splash(self, blank=False):
        position(0.0)
        scene = bge.logic.getCurrentScene()
        obj = scene.objects["Cube.011"]
        if blank:
            self.paint(obj)
        else:
            self.paint(obj, self.ops['splash'])
        camera = scene.objects['Camera']
        camera.position = [-4.71363,-0.882549,2]
        camera.localOrientation = [3.14,0,0]
        self._splashing = True

    def paint(self, obj, path=None):
        prop_name = 'customTexture'
        if prop_name not in obj:
            tex = bge.texture.Texture(obj)
            obj[prop_name] = tex
        else:
            tex = obj[prop_name]
        if path is None:
            path = os.path.join(self.ops['assets_path'], 'images', self._black)
        else:
            path = os.path.join(self.ops['assets_path'], 'images', path)
        raw = bge.texture.ImageFFmpeg(path)
        if raw.status == 0:
            raise ValueError("Unable to load image at {}".format(path))
        tex.source = raw
        tex.refresh(True)

    def reset(self): # reset the scene
        self._splash_dur = self.ops['splash_dur']
        self._end = False
        self._splashing = False
        self._clock = 0
        self.done = False
        self.events = []
        position(0.0)

    def activate(self): # make this context active
        self.reset() # start fresh

        # position rewards
        reward_pos = self.ops['rewards']
        #self.events.append(reward_event_(reward_pos,1,self.arduino,delay=0)) # attach reward triggers to reward locations
        #self.events.append(sound_(reward_pos,self.arduino)) # attach sound triggers to rewards

        # position towers
        scene = bge.logic.getCurrentScene()
        for t, x in zip(self.ls_towers, self.ops['towers_pos']):
            if x is None:
                scene.objects[t].position = [0.0, -10.0, 10.0]
                continue
            if x < 0.0:
                scene.objects[t].position = [-10.0, -x, 10.0]
            else:
                scene.objects[t].position = [10.0, x, 10.0]
        # paint the towers
        for w, f in zip(self.ls_towers, self.ops['towers']):
            obj = scene.objects[w]
            self.paint(obj, f)
        # paint the walls
        for w, f in zip(self.ls_walls, self.ops['walls']):
            obj = scene.objects[w]
            self.paint(obj, f)
        # paint the floor
        for w, f in zip(self.ls_floors, self.ops['floors']):
            obj = scene.objects[w]
            self.paint(obj, f)
        # show splash screen
        if self.ops['splash'] is not None:
            self.splash()
        # send trial pulse

class sequencer:
    def __init__(self, ops):
        self.ops = {}
        self.ops.update(ops)
        self.blocks = []
        for r, b in zip(self.ops['repetitions'], self.ops['blocks']):
            self.blocks.append([c for reps, context in zip(r, b) for c in itertools.repeat(context, reps)])
        print(self.blocks)
        self.laps = -1
        self.next_block()
    
    def next_block(self):
        self.completions = 0
        self.current_rep = -1
        self.current_block = self.blocks.pop(0)
        self.loop = self.ops['loop'].pop(0)
        self.duration = self.ops['duration'].pop(0)
        self.block_cycle = 0.0
        self.next_rep()

    def next_rep(self):
        self.current_rep += 1
        self.completions += self.current_rep == (len(self.current_block) - 1)
        self.current_rep = self.current_rep % len(self.current_block)
        self.current_context = self.current_block[self.current_rep]
        self.laps += 1

class Player:
    def __init__(self) -> None:
        self.ops = {
                "gain": 1.6, # VR gain
                "logicRate": 120.0, # rate at which logic/script runs in Hz
                "env_len": 160.0, # maximum length of environment
                "voltage_scale": [-9.5, 9.5], # voltage output scaling from beginning to end of track
                "assets_path": "~/Documents/VR/resources", # assets folder containing textures, sounds, etc.
                }

        exp = r".*\.json$"
        config_files = os.listdir("./config/")
        [print("[{}] \t".format(i), file) for i, file in enumerate(config_files) if re.search(exp, file)]
        load_file = input("Which config? [0]\t")
        if len(load_file) == 0:
            load_file = '0'
        load_file = os.path.join(os.getcwd(), "config", config_files[int(load_file)])

        with open(load_file, 'r') as f:
            data = json.load(f)

        # load settings
        self.ops.update(data['settings'])
        GameLogic.setLogicTicRate(self.ops['logicRate']) # set game logic rate
        self.ops['assets_path'] = os.path.expanduser(self.ops['assets_path'])

        # load contexts
        self.context_ops = data['contexts']
        self.contexts = {}
        for key in self.context_ops:
            self.context_ops[key].update(self.ops) # settings field contains global parameters that override context specific values!!!
            self.contexts[key] = context(self.context_ops[key]) # instantiate context

        # load channels mapping
        global chan_map
        chan_map.update(data['channels'])

        # load sequence
        self.sequencer = sequencer(data['sequence'])

        self.Stop = 1                                                           # 1-> paused 0-> free used in evread.py

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

        self.current_context = self.contexts[self.sequencer.current_context]
        self.current_context.activate()

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

    # define main program
    def cycle(self):
        # self.send_pos_y(position())
        self.lick_stat = self.lick_value()%2

        # sequence runner routine
        self.current_context.cycle()
        self.sequencer.block_cycle += 1

        if self.current_context.done: # loop, reps, duration, blocks
            if self.sequencer.loop or not self.sequencer.completions:
                self.sequencer.next_rep()
            else:
                self.sequencer.next_block()
            self.current_context = self.contexts[self.sequencer.current_context]
            self.current_context.activate()

        if self.sequencer.block_cycle / self.ops['logicRate'] >= self.sequencer.duration:
            self.sequencer.next_block()
            self.current_context = self.contexts[self.sequencer.current_context]
            self.current_context.activate()
            
        # post debuging information
        scene = bge.logic.getCurrentScene()
        scene.objects['Player']['Context'] = self.sequencer.current_context
        scene.objects['Player']['Block'] = ', '.join(self.sequencer.current_block)
        scene.objects['Player']['Laps'] = self.sequencer.laps
        scene.objects['Player']['Block time'] = "{0:.3f} s".format(self.sequencer.block_cycle / self.ops['logicRate'])

        # self.log_xls()


#### run that bitch ####
try:
    GameLogic.Object["player"]
    init = 0
except:
    init = 1

if not init:
    #profiler = cProfile.Profile()
    #profiler.enable()
    GameLogic.Object["player"].cycle()
    #profiler.disable()
    #stats = pstats.Stats(profiler).sort_stats('cumulative')
    #stats.print_stats()
else:
    GameLogic.Object={}
    GameLogic.Object["player"] = Player()
    print("DEBUG: player instantiated")

