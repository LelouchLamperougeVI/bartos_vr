from __future__ import print_function
import GameLogic

import os
import re
import bge
import time
import datetime
import serial
import struct
import logging
import csv
import aud
import threading
import json
import itertools
import pty # testing without real arduino
import cProfile, pstats
import warnings
import EV

warnings.simplefilter("ignore")

scene = bge.logic.getCurrentScene()
cameras = [scene.objects['Camera'], scene.objects['Camera.001'], scene.objects['Camera.002'], scene.objects['Camera.003'], scene.objects['Camera.004']]

#bge.render.setWindowSize(5400, 1920)
#bge.render.setFullScreen(True)
reward_stat = 0
sound_stat = 0
y_pos = 0.0
_start_ts = time.time()
log_file = '/dev/null'

arduino = serial.Serial()
voltage_scale = [-10.0, 10.0]
env_len = 150.0

def log(*mesg):
    # Write row into csv.
    # *mesg write to each column
    timestamp = '{0:.9f}'.format(time.time() - _start_ts)
    with open(log_file, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile, dialect='unix')
        writer.writerow([timestamp] + [m for m in mesg])

def position(y=None): # get/set player's current position
    scene = bge.logic.getCurrentScene()
    global y_pos
    if y_pos != scene.objects['Camera'].position[1]: # log position every time function gets called
        y_pos = scene.objects['Camera'].position[1]
        transmit('pos', (y_pos % env_len) / env_len * (voltage_scale[1] - voltage_scale[0]) + voltage_scale[0])
        log('pos', y_pos)
    if y is None:
        return scene.objects['Camera'].position[1]
    scene.objects['Camera'].position = [0, y, scene.objects['Camera'].position[2]]
    for c in cameras:
        c.position = [c.position[0], y, scene.objects['Camera'].position[2]]

def transmit(do=None, value=None): # transmitting signals through pulse pal
    opcode = 213
    volt2short = lambda v: round((v + 10) / 20 * 65535)
    if do == 'pos':
        handshakeByteString = struct.pack('<BBH', opcode, 0x01, volt2short(value))
        arduino.write(handshakeByteString)
    elif do == 'frame':
        handshakeByteString = struct.pack('<BB', opcode, 0x02)
        arduino.write(handshakeByteString)
        Response = arduino.read(4)
        try:
            res = struct.unpack('I', Response)[0]
        except:
            res = 0
        return res
    elif do == 'lick':
        handshakeByteString = struct.pack('<BB', opcode, 0x03)
        arduino.write(handshakeByteString)
        Response = arduino.read(1)
        try:
            res = struct.unpack('B', Response)[0]
        except:
            res = 0
        return res
    elif do == 'trial':
        handshakeByteString = struct.pack('<BB', opcode, 0x04)
        arduino.write(handshakeByteString)
    elif do == 'reward':
        handshakeByteString = struct.pack('<BB', opcode, 0x05)
        arduino.write(handshakeByteString)
    elif do == 'brake':
        if value:
            handshakeByteString = struct.pack('<BBB', opcode, 0x06, 0x01)
        else:
            handshakeByteString = struct.pack('<BBB', opcode, 0x06, 0x00)
        arduino.write(handshakeByteString)

# reward_pump
class reward_event_():
    def __init__(self, pos, delay=0, sound=None) -> None:
        self.startPos = pos
        self.active_stat = 0
        self.delay = delay
        self.sound = aud.Factory.file(sound)

    def check_condition(self):
        if position() > self.startPos and not self.active_stat:
            self.active_stat = 1
            sa = threading.Thread(target=self.reward1Thread)
            sa.start()
            if self.sound is not None:
                aud.device().play(self.sound)
            transmit('reward')

    def reward1Thread(self):
        time.sleep(self.delay)
        ser = serial.Serial('/dev/ttyUSB0')
        for i in range(2):
            ser.setDTR(False)
            time.sleep(0.1)
            ser.setDTR(True)
            time.sleep(0.1)

class context:
    def __init__(self, ops) -> None:
        self.ops = { # default parameters
            "brake": False, # whether or not to apply brake
            "splash": None, # display a splash screen, either mention image file or None to disable
            "splash_dur": 0.0, # duration of splash screen
            "sound": None, # sound file, None to disable reward tone
            "reward_dur": 1.0, # duration of reward
            "trial_delay": 0.0, # blank screen at the end of each trial for set duration
            "env": 160.0, # begining and end of track
            "rewards": [], # locations of rewards, negative numbers only display platform but do not actually trigger pump
            "towers_pos": [None, None, None, None], # locations of towers, negative for left, positive for right
            "towers": [None, None, None, None], # textures for towers, None for black
            "walls": [None, None, None, None, None, None, None, None], # list of file names for walls, None for black
            "floors": [None], # floor texture, None for black
            "void": False, # show nothing at all, free-floating position, for resting state acquisition
        }
        self.ops.update(ops)
        if self.ops['sound'] is not None:
            self.ops['sound'] = os.path.join(self.ops['assets_path'], 'sounds', self.ops['sound'])
        self.ls_towers = ['tower_r1', 'tower_r2', 'tower_l1', 'tower_l2']
        self.ls_walls = ['wall_l1', 'wall_r1', 'wall_l2', 'wall_r2', 'wall_l3', 'wall_r3', 'wall_l4', 'wall_r4']
        self.ls_floors = ['Cube']
        self.ls_plats = ['plat1', 'plat2', 'plat3', 'plat4']
        self._black = 'black.jpg'
        self._height = 2
        self._orientation = 3.1416/2
        if self.ops['void']:
            self._height = 1000
            self._orientation = 3.1416
        self.reset()

    def cycle(self): # cycle the routine
        tic = self._clock / self.ops['logicRate']
        for event_ in self.events:
            event_.check_condition()
        if self._splashing and self._splash_dur <= tic:
            scene = bge.logic.getCurrentScene()
            scene.objects['Camera'].position = [0,0,self._height]
            position(0)
            scene.objects['Camera'].localOrientation = [self._orientation,0,0]
            self._splashing = False
        self._clock += 1
        if position() >= self.ops['env'] and not self.ops['void']:
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
        for c in cameras:
            c.position = [c.position[0], 0, 1000]
        scene.objects['Camera'].position = [0,0,9]
        scene.objects['Camera'].localOrientation = [3.1416,0,0]
        self._splashing = True
        log('splashing', 'blank' if blank else self.ops['splash'])

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
        scene = bge.logic.getCurrentScene()
        scene.objects['Camera'].position = [0,0,self._height]
        position(0)
        scene.objects['Camera'].localOrientation = [self._orientation,0,0]
        position(0.0)

    def activate(self): # make this context active
        self.reset() # start fresh
        global env_len
        env_len = self.ops['env']

        # position rewards
        scene = bge.logic.getCurrentScene()
        reward_pos = self.ops['rewards']
        if len(reward_pos) == 0:
            reward_pos = [None for _ in range(len(self.ls_plats))]
        for i, r in enumerate(reward_pos):
            if r is None:
                scene.objects[self.ls_plats[i]].position = [0, -10, 0]
            elif r < 0:
                scene.objects[self.ls_plats[i]].position = [0, -r, 0]
            else:
                scene.objects[self.ls_plats[i]].position = [0, r, 0]
                self.events.append(reward_event_(pos=r, sound=self.ops['sound'])) # attach reward triggers to reward locations

        # position towers
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
        # send trial pulse and apply brake
        transmit('trial')
        if self.ops['brake']:
            transmit('brake', True)
        else:
            transmit('brake', False)

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
        self.done = False

    def next_block(self):
        self.completions = 0
        self.current_rep = -1
        if len(self.blocks):
            self.current_block = self.blocks.pop(0)
        else:
            self.done = True
            log('finish', 'All blocks completed. Experiment is over :)')
            return
        self.loop = self.ops['loop'].pop(0)
        self.duration = self.ops['duration'].pop(0)
        self.block_cycle = 0.0
        self.next_rep()
        log('block', '|'.join(self.current_block))

    def next_rep(self):
        self.current_rep += 1
        self.completions += self.current_rep == (len(self.current_block) - 1)
        self.current_rep = self.current_rep % len(self.current_block)
        self.current_context = self.current_block[self.current_rep]
        self.laps += 1
        log('context', self.current_context)
        print('Laps: {}'.format(self.laps))

class Player:
    def __init__(self, data) -> None:
        self.ops = {
                "gain": 1.6, # VR gain
                "logicRate": 120.0, # rate at which logic/script runs in Hz
                "env_len": 160.0, # maximum length of environment
                "voltage_scale": [-9.5, 9.5], # voltage output scaling from beginning to end of track
                "assets_path": "~/Documents/VR/resources", # assets folder containing textures, sounds, etc.
                }

        # load settings
        self.ops.update(data['settings'])
        GameLogic.setLogicTicRate(self.ops['logicRate']) # set game logic rate
        self.ops['assets_path'] = os.path.expanduser(self.ops['assets_path'])
        global log_file
        log_file = os.path.expanduser(self.ops['save_path'])
        log_file = os.path.join(log_file, datetime.datetime.now().strftime('%Y_%m_%d-%H_%M_%S') + '.csv')
        log('settings', 'global', self.ops)
        global voltage_scale
        voltage_scale = self.ops['voltage_scale']

        # load contexts
        self.context_ops = data['contexts']
        self.contexts = {}
        for key in self.context_ops:
            self.context_ops[key].update(self.ops) # settings field contains global parameters that override context specific values!!!
            self.contexts[key] = context(self.context_ops[key]) # instantiate context
            log('settings', 'context', key, self.context_ops[key])

        # load sequence
        self.sequencer = sequencer(data['sequence'])
        log('settings', 'sequence', data['sequence'])

        # attach arduino -> try /dev/ttyACM0 to /dev/ttyACM9 (WILL NOT WORK IF MORE THAN ONE ARE CONNECTED)
        connected = False
        global arduino
        for i in range(10):
            try:
                name = '/dev/ttyACM{}'.format(i)
                print("trying to connect",name)
                arduino = serial.Serial(name, 115200, timeout=.1)
                connected = True
                break
            except:
                pass
        if not connected:
            print("failed to connect to arduino, opening virtual port for testing")
            master, slave = pty.openpty()
            s_name = os.ttyname(slave)
            arduino = serial.Serial(s_name, 115200, timeout=0) # timeout non-blocking for testing
        print('Arduino initialized')

        self.last_frame = 0 # last frame tracking
        self.current_context = self.contexts[self.sequencer.current_context]
        self.current_context.activate()

        self.evtracker = EV.evtracker() # new wheel rotation tracker to replace evread

    # define main program
    def cycle(self):
        # track position
        delta = self.evtracker.acc() * self.ops['gain']
        if not self.current_context._splashing:
            position(delta + position())

        # track frame pulses
        frame = transmit('frame')
        if frame != self.last_frame:
            log('frame', frame)
            self.last_frame = frame

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

        if self.sequencer.done:
            bge.logic.endGame()

        # post debuging information
        scene = bge.logic.getCurrentScene()
        scene.objects['Player']['Context'] = self.sequencer.current_context
        scene.objects['Player']['Block'] = ', '.join(self.sequencer.current_block)
        scene.objects['Player']['Laps'] = self.sequencer.laps
        scene.objects['Player']['Block time'] = "{:.3f} s".format(self.sequencer.block_cycle / self.ops['logicRate'])
        scene.objects['Player']['y'] = "{:.1f}".format(position())


#### run that bitch ####
scene = bge.logic.getCurrentScene()
cam1 = scene.objects['Camera.003']
cam2 = scene.objects['Camera.001']
cam3 = scene.objects['Camera']
cam4 = scene.objects['Camera.002']
cam5 = scene.objects['Camera.004']

width = bge.render.getWindowWidth()
height = bge.render.getWindowHeight()

cam1.setViewport(0, 0, int(width/5), height)
cam2.setViewport(int(width/5), 0, int(width*2/5), height)
cam3.setViewport(int(width*2/5), 0, int(width*3/5), height)
cam4.setViewport(int(width*3/5), 0, int(width*4/5), height)
cam5.setViewport(int(width*4/5), 0, int(width*5/5), height)

cam1.useViewport = True
cam2.useViewport = True
cam3.useViewport = True
cam4.useViewport = True
cam5.useViewport = True

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
    exp = r".*\.json$"
    config_files = os.listdir("./config/")
    config_files = [file for file in config_files if re.search(exp, file)]
    [print("[{}] \t".format(i), file) for i, file in enumerate(config_files) if re.search(exp, file)]
    load_file = input("Which config? [0]\t")
    if len(load_file) == 0:
        load_file = '0'
    load_file = os.path.join(os.getcwd(), "config", config_files[int(load_file)])

    with open(load_file, 'r') as f:
        data = json.load(f)

    GameLogic.Object={}
    GameLogic.Object["player"] = Player(data)
    print("DEBUG: player instantiated")

