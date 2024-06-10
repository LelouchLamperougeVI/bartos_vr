#! /bin/bash

WID=$(xdotool search --name bastard)
while [[ -z "$WID" ]]; do
        sleep .5
        WID="$(xdotool search --name bastard)"
done
xprop -id $WID -format _MOTIF_WM_HINTS 32c -set _MOTIF_WM_HINTS 2 
wmctrl -r bastard -b remove,maximized_vert,maximized_horz
xdotool windowmove $WID 1920 0
xdotool windowsize $WID 5400 1920
