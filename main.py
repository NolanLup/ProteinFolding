import os
import os.path
import random
import sys
from time import sleep
from PyQt5 import uic
import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMainWindow, QApplication, QPushButton, QLCDNumber, \
    QDoubleSpinBox, QSpinBox
from labjack import ljm
from xlwt import Workbook

# Parameters
seconds = 0
pHParameter = 0
orpParameter = 0
tempParameter = 0
agitationTime = 0

# Current value of pH,ORP,Temp,DO
pHCurrent = 0
orpCurrent = 0
tempCurrent = 0
DOCurrent = 0

# Global Arrays to use in continuous graphing
pHArray = []
ORPArray = []
tempArray = []
DOArray = []
minuteArray = []
# Keeps track of the transition to minutes
secToMin = False

# Lines on graph
tempLine = pg.mkPen(color=(200, 0, 0), width=5)
ORPLine = pg.mkPen(color=(0, 0, 255), width=5)
pHLine = pg.mkPen(color=(180, 0, 180), width=5)
DOline = pg.mkPen(color=(0, 0, 0), width=5)

# handle = ljm.openS("ANY", "ANY", "ANY")  # Any device, Any connection, Any identifier
wb = Workbook()
sheet1 = wb.add_sheet('Sheet 1')
file_num = len([name for name in os.listdir('.') if os.path.isfile(name)])


def shift(arr, num):
    result = np.empty_like(arr)
    for x in range(29):
        arr[x] = arr[x + 1]
    arr[30] = num
    return arr


def readLuaInfo(handle):
    """Function that selects the current lua execution block and prints
       out associated info from lua

    """
    try:
        for i in range(20):
            # The script sets the interval length with LJ.IntervalConfig.
            # Note that LJ.IntervalConfig has some jitter and that this program's
            # interval (set by sleep) will have some minor drift from
            # LJ.IntervalConfig.
            sleep(1)
            print("LUA_RUN: %d" % ljm.eReadName(handle, "LUA_RUN"))
            # Add custom logic to control the Lua execution block
            executionLoopNum = i % 3
            # Write which lua control block to run using the user ram register
            ljm.eWriteName(handle, "USER_RAM0_U16", executionLoopNum)
            numBytes = ljm.eReadName(handle, "LUA_DEBUG_NUM_BYTES")
            if (int(numBytes) == 0):
                continue
            print("LUA_DEBUG_NUM_BYTES: %d\n" % numBytes)
            aBytes = ljm.eReadNameByteArray(handle, "LUA_DEBUG_DATA", int(numBytes))
            luaMessage = "".join([("%c" % val) for val in aBytes])
            print("LUA_DEBUG_DATA: %s" % luaMessage)
    except ljm.LJMError:
        print("Error while running the main loop")
        raise


def loadLuaScript(luaScript):
    """Function that loads and begins running a lua script

    """
    try:
        scriptLen = len(luaScript) + 1
        # LUA_RUN must be written to twice to disable any running scripts.
        ljm.eWriteName(handle, "LUA_RUN", 0)
        # Then, wait for the Lua VM to shut down. Some T7 firmware
        # versions need a longer time to shut down than others.
        sleep(0.6)
        ljm.eWriteName(handle, "LUA_RUN", 0)
        ljm.eWriteName(handle, "LUA_SOURCE_SIZE", scriptLen)
        ljm.eWriteNameByteArray(handle, "LUA_SOURCE_WRITE", scriptLen, luaScript)
        ljm.eWriteName(handle, "LUA_DEBUG_ENABLE", 1)
        ljm.eWriteName(handle, "LUA_DEBUG_ENABLE_DEFAULT", 1)
        ljm.eWriteName(handle, "LUA_RUN", 1)
    except ljm.LJMError:
        print("Error while loading the lua script")
        raise


class UI(QMainWindow):
    def __init__(self):
        super(UI, self).__init__()

        # load UI File
        uic.loadUi("ProteinFoldingGUI.ui", self)
        # define LCD
        self.lcd = self.findChild(QLCDNumber, "timeSince")

        # define current variables
        self.pHValue = self.findChild(QLCDNumber, "pHValue")
        self.ORPValue = self.findChild(QLCDNumber, "ORPValue")
        self.tempValue = self.findChild(QLCDNumber, "tempValue")
        self.DOValue = self.findChild(QLCDNumber, "DOValue")

        # define buttons
        self.start = self.findChild(QPushButton, "start")
        self.stop = self.findChild(QPushButton, "stop")
        self.exit = self.findChild(QPushButton, "exit")

        # define input boxes
        self.pHinputBox = self.findChild(QDoubleSpinBox, "pH")
        self.pHinputBox.setRange(1, 14)
        self.orpinputBox = self.findChild(QSpinBox, "orp")
        self.orpinputBox.setRange(-1900, 1900)
        self.tempinputBox = self.findChild(QDoubleSpinBox, "temp")
        self.tempinputBox.setRange(0, 40)
        self.agitationinputBox = self.findChild(QDoubleSpinBox, "agitation")
        self.agitationinputBox.setRange(0, 5)  # In minutes

        # Setup timer and buttons
        self.timerUpdateGUI = QTimer()
        self.timerUpdateGUI.timeout.connect(self.updateGUI)
        self.start.pressed.connect(self.startControl)
        self.stop.pressed.connect(self.stopControl)
        self.exit.pressed.connect(self.exitApp)

        styles = {'color': 'r', 'font-size': '20px'}

        self.graphWidget.setBackground('w')
        self.graphWidget.setLabel('left', 'pH', **styles)
        self.graphWidget.setLabel('bottom', 'Seconds', **styles)
        self.graphWidget_2.setBackground('w')
        self.graphWidget_2.setLabel('left', 'ORP', **styles)
        self.graphWidget_2.setLabel('bottom', 'Seconds', **styles)
        self.graphWidget_3.setBackground('w')
        self.graphWidget_3.setLabel('left', 'Temp', **styles)
        self.graphWidget_3.setLabel('bottom', 'Seconds', **styles)
        self.graphWidget_4.setBackground('w')
        self.graphWidget_4.setLabel('left', 'DO (%)', **styles)
        self.graphWidget_4.setLabel('bottom', 'Seconds', **styles)

        # Show application window
        self.showMaximized()

    def updateGUI(self):
        global seconds
        global pHCurrent
        global orpCurrent
        global tempCurrent
        global DOCurrent
        global pHArray
        global ORPArray
        global tempArray
        global DOArray
        global minuteArray
        global secToMin

        def convert(timeSeconds):
            timeSeconds = timeSeconds % (24 * 3600)
            hour = timeSeconds // 3600
            timeSeconds %= 3600
            minutes = timeSeconds // 60
            timeSeconds %= 60

            return "%02d:%02d:%02d" % (hour, minutes, timeSeconds)

        # Update seconds by 1
        seconds += 1
        # Update time LCD
        self.lcd.setDigitCount(8)
        self.lcd.display(convert(seconds))

        # Read values from sensors

        # pHCurrent = ((118.65 / 16) * ljm.eReadName(handle, 'AIN4')) - 3.5
        # orpCurrent = ((16102.5 / 8) * ljm.eReadName(handle, 'AIN5')) - 2850
        # DOCurrent = (((0.125 * 8.475) * ljm.eReadName(handle, 'AIN6')) - 0.5) * 100
        # tempCurrent = ((325 / 71) * ljm.eReadName(handle, 'AIN0')) - (3257 / 284)

        # Update pH,ORP,Temp,DO
        self.pHValue.display(pHCurrent)
        self.ORPValue.display(orpCurrent)
        self.tempValue.display(tempCurrent)
        self.DOValue.display(DOCurrent)

        # Update + plot data:
        if seconds > 50000:
            minuteArray.append((seconds / 60))
        else:
            minuteArray.append(seconds)
            pHArray.append(random.randrange(4,10,1))
            ORPArray.append(random.randrange(100,150,5))
            tempArray.append(random.randrange(15,25,1))
            DOArray.append(random.randrange(95,105,1))

        if seconds > 50000 and not secToMin:
            styles = {'color': 'r', 'font-size': '20px'}
            self.graphWidget.setLabel('bottom', 'Minutes', **styles)
            self.graphWidget_2.setLabel('bottom', 'Minutes', **styles)
            self.graphWidget_3.setLabel('bottom', 'Minutes', **styles)
            self.graphWidget_4.setLabel('bottom', 'Minutes', **styles)
            secToMin = True
            minuteArray[:] = [x / 60 for x in minuteArray]

        self.graphWidget.plot(minuteArray, pHArray, pen=pHLine)
        self.graphWidget_2.plot(minuteArray, ORPArray, pen=ORPLine)
        self.graphWidget_3.plot(minuteArray, tempArray, pen=tempLine)
        self.graphWidget_4.plot(minuteArray, DOArray, pen=DOline)

        # Save to file
        # add_sheet is used to create sheet.
        sheet1.write(seconds, 1, seconds)
        sheet1.write(seconds, 2, pHCurrent)
        sheet1.write(seconds, 3, orpCurrent)
        sheet1.write(seconds, 4, tempCurrent)
        sheet1.write(seconds, 5, DOCurrent)

    def startControl(self):
        global seconds
        global pHParameter
        global tempParameter
        global orpParameter
        global agitationTime
        global wb
        global sheet1
        global secToMin
        global pHArray
        global ORPArray
        global tempArray
        global DOArray
        global minuteArray

        def takeInputs():
            global pHParameter
            global tempParameter
            global orpParameter
            global agitationTime

            pHParameter = self.pHinputBox.value()
            tempParameter = self.tempinputBox.value()
            orpParameter = self.orpinputBox.value()
            agitationTime = 60000 * (self.agitationinputBox.value())

        pHArray.clear()
        ORPArray.clear()
        tempArray.clear()
        DOArray.clear()
        minuteArray.clear()
        self.graphWidget.clear()
        self.graphWidget_2.clear()
        self.graphWidget_3.clear()
        self.graphWidget_4.clear()

        wb = Workbook()
        sheet1 = wb.add_sheet('Sheet 1')
        seconds = 0
        takeInputs()
        acidthreshold = pHParameter + 1
        basethreshold = pHParameter - 1
        orpThreshold = orpParameter
        tempThreshold = tempParameter
        luaScript = """
local mbRead=MB.R
local mbWrite=MB.W
pH=0
ORP=0
DO=0
Temp=0
baseThreshold=""" + str(basethreshold) + """
acidThreshold=""" + str(acidthreshold) + """
targetORP=""" + str(orpThreshold) + """
targetTemp= """ + str(tempThreshold) + """
LJ.IntervalConfig(0, 1000)
local checkInterval=LJ.CheckInterval
function sleep(time_ms)
    LJ.IntervalConfig(7, time_ms)
    while( LJ.CheckInterval(7) ~= 1 )do
    end
end
sdaPin=15
sclPin=11
throttleVal=65526
baseAddr=0x1
acidAddr=0x2
reducingAgentAddr=0x3
while true do
  if checkInterval(0) then
    pH=((118.65/16)*mbRead(8, 3)) - 3.5--Read address 0 (AIN0), type is 3
    ORP=((16102.5/8)*mbRead(10, 3)) - 2850--Read address 0 (AIN0), type is 3
    DO=(((0.125*8.475)*mbRead(12, 3)) - 0.5) * 100
    Temp=((325/71)*mbRead(0, 3)) - (3257/284)
    if pH < baseThreshold then
      I2C.config(sdaPin, sclPin, throttleVal, 0, baseAddr)
      I2C.write({0x44,0x2C,0x34})
      mbWrite(1002, 3, 5.0)
      sleep(10000)
      sleep(10000)
      sleep(10000)
      mbWrite(1002, 3, 0)
      sleep(10000)
      sleep(10000)
      sleep(10000)
      sleep(10000)
      sleep(10000)
      sleep(10000)
    elseif pH > acidThreshold then
      I2C.config(sdaPin, sclPin, throttleVal, 0, acidAddr)
      I2C.write({0x44,0x2C,0x31,0x35})
      mbWrite(1002, 3, 5.0)
      sleep(10000)
      sleep(10000)
      sleep(10000)
      mbWrite(1002, 3, 0)
      sleep(10000)
      sleep(10000)
      sleep(10000)
      sleep(10000)
      sleep(10000)
      sleep(10000)
    elseif ORP > targetORP then
      I2C.config(sdaPin, sclPin, throttleVal, 0, reducingAgentAddr)
      I2C.write({0x44,0x2C,0x31,0x35})
      sleep(10000)
    elseif Temp > targetTemp then
      mbWrite(1000, 3, 5)
      sleep(10000)
      mbWrite(1000, 3, 0)
      sleep(10000)
    end
  end
end
"""
        # loadLuaScript(luaScript)
        self.timerUpdateGUI.start(1000)
        sheet1.write(0, 1, 'Time (Seconds)')
        sheet1.write(0, 2, 'pH')
        sheet1.write(0, 3, 'ORP')
        sheet1.write(0, 4, 'Temp')
        sheet1.write(0, 5, 'Dissolved Oxygen %')
        secToMin = False

    def stopControl(self):
        global seconds
        global file_num

        file_num = len([name for name in os.listdir('.') if os.path.isfile(name)])

        luaScript = ""
        # loadLuaScript(luaScript)
        self.timerUpdateGUI.stop()
        wb.save('Protein Folding Data' + str(file_num) + '.xls')
        seconds = 0


    def exitApp(self):
        app.exit()
        # ljm.close(handle)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    UIWindow = UI()
    app.exec()
