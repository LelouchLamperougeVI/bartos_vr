# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

# Read out mice from Blender
# (c) C. Schmidt-Hieber, 2013

from __future__ import print_function
import bge
import GameLogic
import struct

# define main program
def main():
        print('Arduino off')
        GameLogic.Object['player'].interrupted= 1
        arduino = GameLogic.Object['player'].arduino
        OpMenuByte = 213
        value = 3440
        handshakeByteString = struct.pack('<BBH', OpMenuByte,0x03,int(value))
        arduino.write(handshakeByteString)
        bge.logic.endGame()
        return
main()
    