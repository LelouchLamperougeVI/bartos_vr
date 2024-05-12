from __future__ import print_function

import sys
import GameLogic
import json
import numpy as np
import xinput
from resources.scripts import gnoomutils as gu
import datetime
import bge

try:
    GameLogic.Object['m1conn']
    init = 0
except:
    init = 1

if init:
    print("BLENDER: GameLogic object created")
    GameLogic.Object['closed'] = False

    mice = xinput.find_mice(model="G703")   #G703
    for mouse in mice:
        # xinput.set_owner(mouse) # Don't need this if using correct udev rule
        xinput.switch_mode(mouse)

    blenderpath = GameLogic.expandPath('//')

    GameLogic.Object['m1conn'] = None
    GameLogic.Object['m2conn'] = None
    GameLogic.Object['m3conn'] = None
    GameLogic.Object['m4conn'] = None

    for i in range(len(mice)):
        s1, conn1, addr1, p1 = \
            gu.spawn_process("\0mouse0socket", 
                          ['%s/evread/readout' % blenderpath, '%d' % mice[i].evno, '0'])
                           
        conn1.send(b'start')

        gu.recv_ready(conn1)

        conn1.setblocking(0)

        GameLogic.Object["m{}conn".format(i+1)] = conn1

conn1 = GameLogic.Object['m1conn']
conn2 = GameLogic.Object['m2conn']
conn3 = GameLogic.Object['m3conn']
conn4 = GameLogic.Object['m4conn']

# define main program
def main():
    if GameLogic.Object['closed']:
        return
    # get controller
    controller = GameLogic.getCurrentController()
    connection_list = [conn1, conn2, conn3, conn4]
    gu.keep_conn(connection_list)

    t1, dt1, x1, y1 = np.array([0.,]), np.array([0.,]), np.array([0.,]), np.array([0.,]) 
    for conn in connection_list:
        #print(connection_list)
        if conn is not None:
            _t1, _dt1, _x1, _y1 = gu.read32(conn)
            if np.abs(_y1.sum()) > 0.8:
                t1, dt1, x1, y1 = _t1, _dt1, _x1, _y1
    # move according to ball readout:
    # some delay introduced (100 Fs) so that mouse cant move before everthing is loaded
    if not GameLogic.Object['player'].current_context._splashing:
        movement(controller, (x1, y1, t1, dt1))
    else:
        pass

# define useMouseLook
def movement(controller, move):
    # Note that x is mirrored if the dome projection is used.
    ytranslate = 0
    # gain 2.6e-1 for 2-P station, 5e-2 for training setup!
    gain = GameLogic.Object['player'].ops['gain']
    
    # y axis front mouse
    if len(move[1]):
        ytranslate = float(move[1].sum()) * -2.0*gain
    
    # Get the actuators
    act_ytranslate = controller.actuators["ytranslate"]
    act_ytranslate.linV = [0.0, ytranslate, 0.0]

    # Use the actuators
    controller.activate(act_ytranslate)

main()

