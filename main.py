import sys
from time import sleep

from labjack import ljm
from PyQt5.QtWidgets import QMainWindow, QApplication, QPushButton, QLCDNumber, \
    QDoubleSpinBox, QSpinBox
from PyQt5 import uic
from PyQt5.QtCore import QTimer

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

handle = ljm.openS("ANY", "ANY", "ANY")  # Any device, Any connection, Any identifier

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

        # Show application window
        self.show()

    def updateGUI(self):
        global seconds
        global pHCurrent
        global orpCurrent
        global tempCurrent
        global DOCurrent

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

        pHCurrent = ((118.65 / 16) * ljm.eReadName(handle, 'AIN4')) - 3.5
        orpCurrent = ((16102.5 / 8) * ljm.eReadName(handle, 'AIN5')) - 2850
        DOCurrent = (((0.125 * 8.475) * ljm.eReadName(handle, 'AIN6')) - 0.5) * 100
        tempCurrent = ((325 / 71) * ljm.eReadName(handle, 'AIN0')) - (3257 / 284)

        # Update pH,ORP,Temp,DO
        self.pHValue.display(pHCurrent)
        self.ORPValue.display(orpCurrent)
        self.tempValue.display(tempCurrent)
        self.DOValue.display(DOCurrent)

    def startControl(self):
        global seconds
        global pHParameter
        global tempParameter
        global orpParameter
        global agitationTime

        def takeInputs():
            global pHParameter
            global tempParameter
            global orpParameter
            global agitationTime

            pHParameter = self.pHinputBox.value()
            tempParameter = self.tempinputBox.value()
            orpParameter = self.orpinputBox.value()
            agitationTime = 60000 * (self.agitationinputBox.value())

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
      I2C.config(sdaPin, sclPin, throttleVal, 0, acidAddr)
      I2C.write({0x44,0x2C,0x31,0x35})
      sleep(10000)
    elseif pH > acidThreshold then
      I2C.config(sdaPin, sclPin, throttleVal, 0, baseAddr)
      I2C.write({0x44,0x2C,0x31,0x35})
      sleep(10000)
    elseif ORP > targetORP then
      I2C.config(sdaPin, sclPin, throttleVal, 0, reducingAgentAddr)
      I2C.write({0x44,0x2C,0x31,0x35})
      sleep(10000)
    end
  end
end"""
        loadLuaScript(luaScript)
        self.timerUpdateGUI.start(1000)

    def stopControl(self):
        global seconds

        luaScript = ""
        loadLuaScript(luaScript)
        self.timerUpdateGUI.stop()

    def exitApp(self):
        app.exit()
        ljm.close(handle)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    UIWindow = UI()
    app.exec()
