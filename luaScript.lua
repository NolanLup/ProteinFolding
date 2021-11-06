print("Set a DIO based on voltage. Digital I/O is FIO3 (FIO5 on T4), voltage measured on AIN1. Update at 10Hz")
local TempA0Volt = 0
local pHA1Volt = 0
local TempThresh = .25
local acidThresh = 3.40 -- KCL solution reads around 3.54 Volts
local baseThresh = 2.65 -- Alkaline water reads around 2.60 Volts

local mbRead=MB.R			--local functions for faster processing
local mbWrite=MB.W

local tempOutPin = 2005 --FIO5
local baseOutPin = 2004 --FIO4 
local acidOutPin = 2006 --FIO6

LJ.IntervalConfig(0, 100)                   --set interval to 100 for 100ms
local checkInterval=LJ.CheckInterval

while true do
  if checkInterval(0) then               --interval completed
    TempA0Volt = mbRead(0, 3)               --read AIN1. Address is 2, type is 3
    pHA1Volt = mbRead(2,3)
    -- Check Temp Volt
    if TempA0Volt > TempThresh then --if the input voltage exceeds .28 V
      mbWrite(tempOutPin, 0, 1)                    --write 1 to FIO5 on T4. Address is 2003, type is 0, value is 1(output high)
    else
      mbWrite(tempOutPin, 0, 0)                    --write 0 to FIO5 on T4. Address is 2003, type is 0, value is 0(output low)
    end
    -- Check pH Volt
    if pHA1Volt > acidThresh then --if pH volt is greater than acid threshold 
      mbWrite(acidOutPin, 0, 1)       --write 1 to FIO5 on T4. Address is 2003, type is 0, value is 1(output high)
      mbWrite(baseOutPin, 0, 0)
    elseif pHA1Volt < baseThresh and pHA1Volt > 1.5 then
      mbWrite(baseOutPin, 0, 1)
      mbWrite(acidOutPin, 0, 0)
    else
      mbWrite(baseOutPin, 0, 0)
      mbWrite(acidOutPin, 0, 0) 
    end
    -- 
  end
end