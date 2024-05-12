import bge
import GameLogic

co = bge.logic.getCurrentController()
sensor = co.sensors["Keyboard1"]
act = co.actuators["move"]

act.linV = [0.0, 0.0, 0.0]

for key,status in sensor.events:
     if status == bge.logic.KX_INPUT_JUST_ACTIVATED and not GameLogic.Object['player'].current_context._splashing:
             if key == bge.events.UPARROWKEY:
                     act.linV = [0.0, 40.0, 0.0]
             if key == bge.events.DOWNARROWKEY:
                     act.linV = [0.0, -20.0, 0.0]
                     
co.activate(act)
