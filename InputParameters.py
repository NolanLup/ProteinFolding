
if __name__ == '__main__':
    my_file = open("luaScript.lua")
    string_list = my_file.readlines()
    # Asking for parameters from user:
    acidParameter = "2.00"
    baseParameter = "1.00"
    tempParameter = "3.00"

    my_file.close()
    for string in string_list:
        if "local" in string and "Thresh" in string:
            # Updating pH parameters:
            if "acid" in string:
                index = string.find('=')
                newParameter = string[:index] + "= " + acidParameter + string[(index + 6):]
                print(string)
                print(newParameter)
            if "base" in string:
                index = string.find('=')
                newParameter = string[:index] + "= " + baseParameter + string[(index + 6):]
                print(string)
                print(newParameter)
            if "Temp" in string:
                index = string.find('=')
                newParameter = string[:index] + "= " + tempParameter + string[(index + 6):]
                print(string)
                print(newParameter)
