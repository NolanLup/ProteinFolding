import sys
from time import sleep

from labjack import ljm

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QMainWindow, QApplication, QPushButton, QTextBrowser, QLCDNumber, QInputDialog, \
    QDoubleSpinBox, QSpinBox
from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import QTimer

# Global Variables
seconds = 0
pHParameter = 0
orpParameter = 0
tempParameter = 0


# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.

def loadLuaScript(handle, luaScript):
    """Function that loads and begins running a lua script

    """
    try:
        scriptLen = len(luaScript)
        # LUA_RUN must be written to twice to disable any running scripts.
        print("Script length: %u\n" % scriptLen)
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


def updateLabjack(luaScript):
    # Open first found LabJack
    handle = ljm.openS("ANY", "ANY", "ANY")  # Any device, Any connection, Any identifier
    loadLuaScript(handle, luaScript)
    ljm.close(handle)

class UI(QMainWindow):
    def __init__(self):
        super(UI, self).__init__()

        # load UI File
        uic.loadUi("ProteinFoldingGUI.ui", self)

        # define LCD
        self.lcd = self.findChild(QLCDNumber, "timeSince")

        # define buttons
        self.pumpCalibrate = self.findChild(QPushButton, "calibrate")
        self.start = self.findChild(QPushButton, "start")
        self.stop = self.findChild(QPushButton, "stop")
        self.exit = self.findChild(QPushButton, "exit")
        self.pumpSterilize = self.findChild(QPushButton, "sterilize")

        # define input boxes
        self.pHinputBox = self.findChild(QDoubleSpinBox, "pH")
        self.pHinputBox.setRange(0, 14)
        self.orpinputBox = self.findChild(QSpinBox, "orp")
        self.orpinputBox.setRange(-1900, 1900)
        self.tempinputBox = self.findChild(QDoubleSpinBox, "temp")
        self.tempinputBox.setRange(0, 40)

        # Setup timer and buttons
        self.timer = QTimer()
        self.timer.timeout.connect(self.lcdUpdate)
        self.start.pressed.connect(self.startControl)
        self.stop.pressed.connect(self.stopControl)
        self.exit.pressed.connect(self.exitApp)


        # Show application window
        self.show()

    def lcdUpdate(self):
        global seconds

        def convert(timeSeconds):
            timeSeconds = timeSeconds % (24 * 3600)
            hour = timeSeconds // 3600
            timeSeconds %= 3600
            minutes = timeSeconds // 60
            timeSeconds %= 60

            return "%d:%02d:%02d" % (hour, minutes, timeSeconds)

        # Update seconds by 1
        seconds += 1
        # Get time
        self.lcd.setDigitCount(8)
        self.lcd.display(convert(seconds))

    def startControl(self):
        global seconds

        def takeInputs():
            global pHParameter
            global tempParameter
            global orpParameter

            pHParameter = self.pHinputBox.value()
            tempParameter = self.tempinputBox.value()
            orpParameter = self.orpinputBox.value()

        seconds = 0
        takeInputs()
        luaScript = """ local pHA0Volt = 0
                            local orpA1Volt = 0
                            local acidThresh = """ + str(pHParameter + 1) + """ -- KCL solution reads around 3.54 Volts
                            local baseThresh = """ + str(pHParameter - 1) + """ -- Alkaline water reads around 2.60 Volts
                            local agitationOn = 0 -- 0 if agitation system is off, 1 if agitation system is on

                            local mbRead=MB.R			--local functions for faster processing
                            local mbWrite=MB.W

                            local baseOutPin = 2005 --FIO5
                            local acidOutPin = 2006 --FIO6
                            local agitationOutPin = 2007 --FI07

                            LJ.IntervalConfig(0, 100)                   --set interval to 100 for 100ms
                            local checkInterval=LJ.CheckInterval

                            while true do
                              if checkInterval(0) then              --interval completed
                                pHA0Volt = ((59.325*mbRead(0,3))-28)/8   -- Read AN1
                                orpA1Volt = ((16102.5*mbRead(2,3))-22800)/8
                                -- Check pH Volt
                                if pHA0Volt > acidThresh then --if pH is greater than acid threshold
                                  mbWrite(baseOutPin, 0, 0)
                                  LJ.IntervalConfig(2, 1000) -- Set acidInterval for 1 seconds
                                  while not checkInterval(2) do 
                                    mbWrite(acidOutPin, 0, 1)   -- Turn on acid pump for 3 seconds
                                  end
                                  mbWrite(acidOutPin, 0, 0) -- Turn off acid pump
                                  agitationOn = 1 
                                elseif pHA0Volt < baseThresh and pHA0Volt > 0 then -- if pH is less than base threshold
                                  mbWrite(acidOutPin, 0, 0)
                                  LJ.IntervalConfig(2, 1000) -- Set baseInterval for 1 seconds
                                  while not checkInterval(2) do 
                                    mbWrite(baseOutPin, 0, 1)   -- Turn on base pump for 3 seconds
                                  end
                                  mbWrite(baseOutPin, 0, 0) -- Turn off base pump
                                  agitationOn = 1 
                                else
                                  mbWrite(baseOutPin, 0, 0) -- Turn of base pump
                                  mbWrite(acidOutPin, 0, 0) -- Turn of acid pump
                                  mbWrite(agitationOutPin, 0, 0) -- Turn of agitation
                                end
                                if (agitationOn == 1) then
                                    LJ.IntervalConfig(1, 5000)                 --Set agitationInterval for 5 seconds
                                    while not checkInterval(1) do
                                      mbWrite(agitationOutPin, 0, 1)
                                    end
                                      mbWrite(agitationOutPin, 0, 0)
                                      agitationOn = 0
                                  end
                              end
                            end"""
        updateLabjack(luaScript)
        self.timer.start(1000)

    def stopControl(self):
        global seconds
        luaScript = """local mbRead=MB.R --local functions for faster processing
                    local mbWrite=MB.W

                    local baseOutPin = 2005 --FIO5
                    local acidOutPin = 2006 --FIO6
                    local agitationOutPin = 2007 --FI07
                    mbWrite(baseOutPin, 0, 0) -- Turn of base pump
                    mbWrite(acidOutPin, 0, 0) -- Turn of acid pump
                    mbWrite(agitationOutPin, 0, 0) -- Turn of agitation"""
        updateLabjack(luaScript)
        seconds = 0
        self.timer.stop()

    def exitApp(self):
        app.exit()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    UIWindow = UI()
    app.exec()
