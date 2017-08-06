#! /usr/bin/env python
# -*- coding: utf-8 -*-

import indigo
import logging
from math import radians, cos, sin, asin, sqrt
from pyicloud import PyiCloudService

import os
import sys
import time

class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.debug = False
        self.timeWarpOn = False
        self.timeWarpCount = 0
        self.api = None

        try:
            indigo.variables.folder.create("iDevice Data")
        except ValueError, e:
            print(e)
            pass

        if "iDevice Data" not in indigo.variables.folders:
            self.logger.error("Could not load or create iDevice Data folder. Stopping plugin...")
            self.shutdown()

    def border_msg(self, msg):
        count = len(msg) + 2  # dash will need +2 too
        dash = "-" * count
        return ["+{dash}+".format(dash=dash), "| {msg} |".format(msg=msg), "+{dash}+".format(dash=dash)]
        #return "+{dash}+\n| {msg} |\n+{dash}+".format(dash=dash, msg=msg)

    def login(self, email, password):
        indigo.server.log("Logging into the iCloud API...")
        try:
            self.api = PyiCloudService(email, password)
            if self.api.requires_2fa:
                indigo.server.log("Two-factor authentication required.")
            else:
                indigo.server.log("Logged into iCloud API!")
        except Exception as e:
            self.logger.error(e)

    def testLogin(self, valuesDict):
        #for item in valuesDict:
            #self.debugLog("%s: %s" % (item, valuesDict[item]))

        email = valuesDict["iCloudEmail"]
        password = valuesDict["iCloudPassword"]
        self.debugLog(u"Testing iCloud API connection...\nlogging in with\n    email: %s\n    password: %s" % (email, password))
        self.login(email, password)

    def get2FADevices(self, filter="", valuesDict=None, typeId="", targetId=0):
        if self.api is not None:
            if self.api.requires_2fa:
                devices = []
                for i, device in enumerate(self.api.trusted_devices):
                    devices.append((i, "%s" % device.get('deviceName', "SMS to %s" % device.get('phoneNumber'))))
                return devices
            else:
                return [(-1, None)]
        else:
            return [(-1, None)]

    def select2FADevice(self, valuesDict):
        #for item in valuesDict:
            #self.debugLog("%s: %s" % (item, valuesDict[item]))

        device = self.api.trusted_devices[int(valuesDict["iCloud2FADevices"])]
        if not self.api.send_verification_code(device):
            indigo.server.log("Failed to send verification code!")
        indigo.server.log("Sending verification code...")

    def submit2FAKey(self, valuesDict):
        #for item in valuesDict:
            #self.debugLog("%s: %s" % (item, valuesDict[item]))

        device = self.api.trusted_devices[int(valuesDict["iCloud2FADevices"])]
        code = valuesDict["iCloud2FAKey"]
        if not self.api.validate_verification_code(device, code):
            indigo.server.log("Failed to verify verification code")
        indigo.server.log("Logged into iCloud API!")

    def getDeviceList(self, filter="", valuesDict=None, typeId="", targetId=0):
        if self.api is not None:
            devices = []
            for i, device in enumerate(self.api.devices):
                devices.append((i, "%s (%s)" % (device.get('name'), device.get('deviceDisplayName'))))
            return devices
        else:
            return [(-1, None)]

    def haversine(self, lon1, lat1, lon2, lat2):
        """
        Calculate the great circle distance between two points
        on the earth (specified in decimal degrees)
        """
        # convert decimal degrees to radians
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        # haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        km = 6367 * c
        if self.pluginPrefs['units'] == "mi":
            return km * 0.621371
        else:
            return km

    def closedDeviceConfigUi(self, valuesDict, userCancelled, typeId, devId):
        self.debugLog(u"device id: %s" % devId)
        if typeId == "iDevice" and userCancelled is False:
            token = self.api.devices[int(valuesDict["iCloudDeviceID"])]['id']
            self.debugLog(u"iCloud token: %s" % token)
            device = indigo.devices[devId]
            device.updateStateOnServer('iCloudDeviceID', value=token)
            device.updateStateOnServer('accuracyThreshold', value=valuesDict["accuracyThreshold"])
        elif typeId == "iLocation" and userCancelled is False:
            for value in valuesDict:
                self.debugLog(u"%s: %s" % (value, valuesDict[value]))
            device = indigo.devices[devId]
            device.updateStateOnServer('latitude', value=valuesDict['latitude'])
            device.updateStateOnServer('longitude', value=valuesDict['longitude'])
            device.updateStateOnServer('radius', value=valuesDict['radius'])

    def startup(self):
        self.debugLog(u"startup called")


    def shutdown(self):
        self.debugLog(u"shutdown called")

    def pollDevices(self):
        email = self.pluginPrefs.get("iCloudEmail", None)
        password = self.pluginPrefs.get("iCloudPassword", None)
        if email is not None and password is not None:
            self.login(email, password)
        else:
            self.logger.error(u"Email/Password is required for iTracker device tracking")
            self.api = None

        if self.api is not None:
            # indigo.server.log(u"Found %s devices in iCloud" % ( self.api.devices ))
            for device in indigo.devices.iter("self.iDevice"):
                indigo.server.log(u"Updating %s..." % device.name)

                token = device.states.get("iCloudDeviceID")
                self.debugLog(u"Loading data for iCloud device: %s" % token)
                iDevice = self.api.devices[token]

                try:
                    latitude = iDevice.location()['latitude']
                    longitude = iDevice.location()['longitude']
                    accuracy = iDevice.location()['horizontalAccuracy']
                    battery = round(iDevice.status()['batteryLevel'] * 100, 1)

                    self.debugLog(u"Setting latitude to: %s" % latitude)
                    device.updateStateOnServer('latitude', value=latitude)
                    self.debugLog(u"Setting longitude to: %s" % longitude)
                    device.updateStateOnServer('longitude', value=longitude)
                    self.debugLog(u"Setting accuracy to: %s" % accuracy)
                    device.updateStateOnServer('accuracy', value=accuracy)
                    self.debugLog(u"Setting battery to: %s%%" % battery)
                    device.updateStateOnServer('battery', value=battery)
                    for state in device.states:
                        self.debugLog(u"%s: %s" % (state, device.states[state]))

                    closestLocation = None
                    closestDistance = sys.maxint
                    smallestRadius = sys.maxint
                    self.debugLog(accuracy)
                    self.debugLog(device.states.get("accuracyThreshold"))
                    if accuracy <= device.states.get("accuracyThreshold"):
                        for location in indigo.devices.iter("self.iLocation"):
                            if location.states['latitude'] is not None and location.states['longitude'] is not None and \
                                            location.states['radius'] is not None:
                                distance = self.haversine(float(device.states['longitude']),
                                                          float(device.states['latitude']),
                                                          float(location.states['longitude']),
                                                          float(location.states['latitude']))
                                self.debugLog(
                                    u"Distance from %s: %s%s" % (location.name, distance, self.pluginPrefs['units']))

                                # distance_from_device.name_to_location.name
                                variable_name = "distance_from_%s_to_%s" % (
                                    device.name.replace(' ', '-'), location.name.replace(' ', '-'))
                                if variable_name not in indigo.variables:
                                    indigo.variable.create(name=variable_name, value=str(round(distance, 5)),
                                                           folder=indigo.variables.folders['iDevice Data'])
                                else:
                                    indigo.variable.updateValue(indigo.variables[variable_name],
                                                                value=str(round(distance, 5)))

                                if distance < location.states['radius'] and distance < closestDistance and location.states[
                                    'radius'] < smallestRadius:
                                    closestLocation = location
                                    closestDistance = distance
                                    smallestRadius = location.states['radius']
                            else:
                                self.logger.error(
                                    u"Unable to check \"%s\". A Latitude, Longitude, and radius are required for distance calculations." % location.name)

                        if closestLocation is not None:
                            self.debugLog(u"%s is closest to %s (%s %s)" % (
                                device.name, closestLocation.name, round(closestDistance, 5),
                                self.pluginPrefs.get("units")))
                            device.updateStateOnServer('previous_location', value=device.states['location'])
                            device.updateStateOnServer('location', value=closestLocation.name)
                        else:
                            self.debugLog(
                                u"%s is not close enough to any specified location. %s will be marked as \"Away\"" % (
                                    device.name, device.name))
                            device.updateStateOnServer('previous_location', value=device.states['location'])
                            device.updateStateOnServer('location', value="Away")
                    else:
                        self.logger.warning(u"Location accuracy not within threshold, skipping state update.")
                except Exception as e:
                    self.logger.error(e)
                    self.logger.error(
                        u"Could not read data from %s. Are they sharing their location with you?" % device.name)
                    pass

            for location in indigo.devices.iter("self.iLocation"):
                indigo.server.log(u"Updating device count for: %s" % location.name)
                devices = []
                for device in indigo.devices.iter("self.iDevice"):
                    # if device.states['location'] == location.name:
                    #    devices.append(device.name)
                    distance = self.haversine(float(device.states['longitude']), float(device.states['latitude']),
                                              float(location.states['longitude']), float(location.states['latitude']))
                    if distance < location.states['radius']:
                        devices.append(device.name)
                location.updateStateOnServer('deviceCount', value=len(devices))
                if len(devices) == 1:
                    self.debugLog(u"    found 1 device (%s)" % devices[0])
                elif len(devices) != 0:
                    self.debugLog(u"    found %s devices (%s)" % (len(devices), ", ".join(devices)))
                else:
                    self.debugLog(u"    no devices found")

    def runConcurrentThread(self):
        try:
            while True:
                start = time.time()
                self.pollDevices()
                end = time.time()

                indigo.server.log(u"Checking iCloud API again in %s seconds..." % self.pluginPrefs.get("refresh_period", 60))
                self.sleep(int(self.pluginPrefs.get("refresh_period", 60)) - float(end-start))
                duration = None
        except self.StopThread:
            pass  # Optionally catch the StopThread exception and do any needed cleanup.

    def deviceStartComm(self, dev):
        dev.stateListOrDisplayStateIdChanged()
        return























    ########################################
    # Actions defined in MenuItems.xml:
    ####################
    def timeWarp(self):
        if not self.timeWarpOn:
            indigo.server.log(u"starting mega time warp")
            self.timeWarpOn = True
        else:
            indigo.server.log(u"stopping mega time warp")
            self.timeWarpOn = False

    def addDevice(self, valuesDict, typeId, devId):
        self.debugLog(u"addDevice called")
        # just making sure that they have selected a device in the source
        # list - it shouldn't be possible not to but it's safer
        if "sourceDeviceMenu" in valuesDict:
            # Get the device ID of the selected device
            deviceId = valuesDict["sourceDeviceMenu"]
            if deviceId == "":
                return
            # Get the list of devices that have already been added to the "scene"
            # If the key doesn't exist then return an empty string indicating
            # no devices have yet been added. "memberDevices" is a hidden text
            # field in the dialog that holds a comma-delimited list of device
            # ids, one for each of the devices in the scene.
            selectedDevicesString = valuesDict.get("memberDevices", "")
            self.debugLog("adding device: %s to %s" % (deviceId, selectedDevicesString))
            # If no devices have been added then just set the selected device string to
            # the device id of the device they selected in the popup
            if selectedDevicesString == "":
                selectedDevicesString = deviceId
            # Otherwise append it to the end separated by a comma
            else:
                selectedDevicesString += "," + str(deviceId)
            # Set the device string back to the hidden text field that contains the
            # list of device ids that are in the scene
            valuesDict["memberDevices"] = selectedDevicesString
            self.debugLog("valuesDict = " + str(valuesDict))
            # Delete the selections on both dynamic lists since we don't
            # want to preserve those across dialog runs
            if "memberDeviceList" in valuesDict:
                del valuesDict["memberDeviceList"]
            if "sourceDeviceMenu" in valuesDict:
                del valuesDict["sourceDeviceMenu"]
            # return the new dict
            return valuesDict

    ####################
    # This is the method that's called by the Delete Device button in the scene
    # device config UI.
    ####################
    def deleteDevices(self, valuesDict, typeId, devId):
        self.debugLog(u"deleteDevices called")
        if "memberDevices" in valuesDict:
            # Get the list of devices that are already in the scene
            devicesInScene = valuesDict.get("memberDevices", "").split(",")
            # Get the devices they've selected in the list that they want
            # to remove
            selectedDevices = valuesDict.get("memberDeviceList", [])
            # Loop through the devices to be deleted list and remove them
            for deviceId in selectedDevices:
                self.debugLog("remove deviceId: " + deviceId)
                if deviceId in devicesInScene:
                    devicesInScene.remove(deviceId)
            # Set the "memberDevices" field back to the new list which
            # has the devices deleted from it.
            valuesDict["memberDevices"] = ",".join(devicesInScene)
            # Delete the selections on both dynamic lists since we don't
            # want to preserve those across dialog runs
            if "memberDeviceList" in valuesDict:
                del valuesDict["memberDeviceList"]
            if "sourceDeviceMenu" in valuesDict:
                del valuesDict["sourceDeviceMenu"]
            return valuesDict

    ####################
    # This is the method that's called to build the source device list. Note
    # that valuesDict is read-only so any changes you make to it will be discarded.
    ####################
    def sourceDevices(self, filter="", valuesDict=None, typeId="", targetId=0):
        self.debugLog(
            "sourceDevices called with filter: %s  typeId: %s  targetId: %s" % (filter, typeId, str(targetId)))
        returnList = list()
        # if valuesDict doesn't exist yet - if this is a brand new device
        # then we just create an empty dict so the rest of the logic will
        # work correctly. Many other ways to skin that particular cat.
        if not valuesDict:
            valuesDict = {}
        # Get the member device id list, loop over all devices, and if the device
        # id isn't in the member list then include it in the source list.
        deviceList = valuesDict.get("memberDevices", "").split(",")
        for devId in indigo.devices.iterkeys():
            if str(devId) not in deviceList:
                returnList.append((str(devId), indigo.devices.get(devId).name))
        return returnList

    ####################
    # This is the method that's called to build the member device list. Note
    # that valuesDict is read-only so any changes you make to it will be discarded.
    ####################
    def memberDevices(self, filter="", valuesDict=None, typeId="", targetId=0):
        self.debugLog(
            "memberDevices called with filter: %s  typeId: %s  targetId: %s" % (filter, typeId, str(targetId)))
        returnList = list()
        # valuesDict may be empty or None if it's a brand new device
        if valuesDict and "memberDevices" in valuesDict:
            # Get the list of devices
            deviceListString = valuesDict["memberDevices"]
            self.debugLog("memberDeviceString: " + deviceListString)
            deviceList = deviceListString.split(",")
            # Iterate over the list and if the device exists (it could have been
            # deleted) then add it to the list.
            for devId in deviceList:
                if int(devId) in indigo.devices:
                    returnList.append((devId, indigo.devices[int(devId)].name))
        return returnList

    ########################################
    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        # If the typeId is "scene", we want to clear the selections on both
        # dynamic lists so that they're not stored since we really don't
        # care about those.
        self.debugLog(u"validateDeviceConfigUi: typeId: %s  devId: %s" % (typeId, str(devId)))
        if typeId == "scene":
            if "memberDeviceList" in valuesDict:
                valuesDict["memberDeviceList"] = ""
            if "sourceDeviceMenu" in valuesDict:
                valuesDict["sourceDeviceMenu"] = ""
        return (True, valuesDict)

    ########################################
    # Plugin Actions object callbacks (pluginAction is an Indigo plugin action instance)
    ######################
    def resetHardware(self, pluginAction):
        self.debugLog("resetHardware action called:\n" + str(pluginAction))

    def updateHardwareFirmware(self, pluginAction):
        self.debugLog("updateHardwareFirmware action called:\n" + str(pluginAction))