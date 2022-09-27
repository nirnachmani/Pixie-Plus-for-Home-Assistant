import json
import httpx
import websockets
import datetime
import logging
import asyncio
import time


_LOGGER = logging.getLogger(__name__)


async def pixie_login(applicationid, installationid, javascriptkey, email, password):

    # pixie plus hub is controlled from the cloud by accessing the foloowing url's
    api_url = {
        "userquery": "https://www.pixie.app/p0/pixieCloud/functions/userQuery",
        "login": "https://www.pixie.app/p0/pixieCloud/login",
        "home": "https://www.pixie.app/p0/pixieCloud/classes/Home",
        "HP": "https://www.pixie.app/p0/pixieCloud/classes/HP",
        "livegroup": "https://www.pixie.app/p0/pixieCloud/classes/LiveGroup",
        "logout": "https://www.pixie.app/p0/pixieCloud/logout",
    }

    # data required for login
    login_data = {
        "applicationid": applicationid,
        "installationid": installationid,
        "javascriptkey": javascriptkey,
        "clientversion": "js1.9.2",
        "email": email,
        "password": password,
    }

    # session data has session speicifc data: sessionToken, userId, homeId
    session_data = login(api_url, login_data)
    session_data.update(login_data)
    del session_data["email"]
    del session_data["password"]

    # json parameters often needed in commands to pixie plus
    ID_param = {
        "_ApplicationId": login_data["applicationid"],
        "_ClientVersion": login_data["clientversion"],
        "_InstallationId": login_data["installationid"],
        "_JavaScriptKey": login_data["javascriptkey"],
        "_SessionToken": session_data["sessiontoken"],
    }

    # the function of this is not clear but done by pixie plus client; return HP_key and HP_objectId are not required for this scope of operation
    register_home(api_url, session_data, ID_param)

    # required for getting livegroup_object id and bridge name which are needed for commands
    live_group_data = livegroup_get_objectID(api_url, session_data, ID_param)
    session_data.update(live_group_data)

    # function not clear, first post, no new data
    post_GwData(api_url, session_data, ID_param)

    devices_list = await getdevices(session_data, ID_param)

    if devices_list != "":
        return devices_list


# check if user exist as part of config flow
def check_user(api_url_web_userquery, data):

    userquery = {
        "_ApplicationId": data["applicationid"],
        "_ClientVersion": "js1.9.2",
        "_InstallationId": data["installationid"],
        "_JavaScriptKey": data["javascriptkey"],
        "email": data["username"],
    }

    request = httpx.post(api_url_web_userquery, json=userquery)
    userexist = json.loads(request.text)

    if userexist["result"] == 1:
        success = "True"
    else:
        success = "False"

    return success


def login(api_url, login_data):

    login_command = {
        "_ApplicationId": login_data["applicationid"],
        "_ClientVersion": login_data["clientversion"],
        "_InstallationId": login_data["installationid"],
        "_JavaScriptKey": login_data["javascriptkey"],
        "_method": "GET",
        "password": login_data["password"],
        "username": login_data["email"],
    }

    request = httpx.post(api_url["login"], json=login_command)
    json_data = json.dumps(request.json())
    data = json.loads(json_data)

    session_data = {
        "userid": data["objectId"],
        "homeid": data["curHome"]["objectId"],
        "sessiontoken": data["sessionToken"],
    }

    return session_data


def register_home(api_url, session_data, ID_param):

    # building the command
    curHome = {
        "__type": "Pointer",
        "className": "Home",
        "objectId": session_data["homeid"],
    }
    registerhome = {"_method": "PUT", "curHome": curHome}
    registerhome.update(ID_param)

    HP_where = {"homeId": session_data["homeid"], "userId": session_data["userid"]}
    HP = {"_method": "GET", "limit": "1", "where": HP_where}
    HP.update(ID_param)

    api_url_web_user = (
        "https://www.pixie.app/p0/pixieCloud/classes/_User/" + session_data["userid"]
    )

    request = httpx.post(api_url_web_user, json=registerhome)
    # json_data = json.dumps(request.json())
    # TODO check for success

    request = httpx.post(api_url["HP"], json=HP)
    # json_data = json.dumps(request.json())
    # HP_data = json.loads(json_data)
    # HP_objectId = HP_data["results"][0]["objectId"]
    # HP_key = HP_data["results"][0]["key"]
    # TODO check for success
    # HP_key and HP_objectId are not required for operation

    return


def livegroup_get_objectID(api_url, session_data, ID_param):

    livegroup_get_where = {"GroupID": session_data["homeid"]}
    livegroup_get = {"_method": "GET", "where": livegroup_get_where}
    livegroup_get.update(ID_param)

    request = httpx.post(api_url["livegroup"], json=livegroup_get)
    json_data = json.dumps(request.json())
    data = json.loads(json_data)

    live_group_data = {
        "livegroup_objectid": data["results"][0]["objectId"],
        "bridge_name": data["results"][0]["Online"][0],
    }

    return live_group_data


def post_GwData(api_url, session_data, ID_param):

    api_url_web_livegroup_instance = (
        api_url["livegroup"] + "/" + session_data["livegroup_objectid"]
    )

    GwData_request_data = {"data": "fffe01010100000400003400d568", "type": "GwData"}
    GwData_request = {
        "data": GwData_request_data,
        "from": session_data["userid"],
        "time": unix_time(),
        "to": session_data["bridge_name"],
    }

    GwData = {"Cmd": 2, "Request": GwData_request, "_method": "PUT"}
    GwData.update(ID_param)

    request = httpx.post(api_url_web_livegroup_instance, json=GwData)
    json_data = json.dumps(request.json())
    Gw_success = json.loads(json_data)
    # TODO check success

    return


def unix_time():

    return int(datetime.datetime.timestamp(datetime.datetime.now()) * 1000)


async def getdevices(session_data, ID_param):

    url = "https://www.pixie.app/p0/pixieCloud/classes/Home"

    gethome = {"_method": "GET", "where": "{}"}
    gethome.update(ID_param)

    request = httpx.post(url, json=gethome)

    try:
        json_data = json.dumps(request.json())
        devices = json.loads(json_data)

        _LOGGER.debug(devices)
        devices_list = parse_devices(devices, session_data)

        return devices_list

    except:
        _LOGGER.warning("Couldn't get devices")


def parse_devices(devices, session_data):

    numberofdevices = 0
    devices_list = list()

    if "results" in devices:
        numberofdevices = len(devices["results"][0]["deviceList"])
    elif "error" in devices:
        if devices["code"] == 209:
            print("please login")
            exit()
        else:
            print("other error")
            exit()

    for i in range(numberofdevices - 1):

        dev_id = devices["results"][0]["deviceList"][i]["id"]

        if devices["results"][0]["onlineList"][str(dev_id)]["br"] == 100:
            state = "true"
        elif devices["results"][0]["onlineList"][str(dev_id)]["br"] == 0:
            state = ""

        devices_list.append(
            {
                "name": devices["results"][0]["deviceList"][i]["name"],
                "id": devices["results"][0]["deviceList"][i]["id"],
                "color1": devices["results"][0]["deviceList"][i]["state"]["color"][0],
                "color2": devices["results"][0]["deviceList"][i]["state"]["color"][1],
                "color3": devices["results"][0]["deviceList"][i]["state"]["color"][2],
                "br": devices["results"][0]["deviceList"][i]["state"]["br"],
                "br2_1": devices["results"][0]["deviceList"][i]["state"]["br2"][0],
                "br2_2": devices["results"][0]["deviceList"][i]["state"]["br2"][1],
                "br2_3": devices["results"][0]["deviceList"][i]["state"]["br2"][2],
                "br2_4": devices["results"][0]["deviceList"][i]["state"]["br2"][3],
                "colour": devices["results"][0]["deviceList"][i]["state"]["colour"],
                "mac": devices["results"][0]["deviceList"][i]["mac"],
                "state": state,
                "applicationid": session_data["applicationid"],
                "installationid": session_data["installationid"],
                "javascriptkey": session_data["javascriptkey"],
                "userid": session_data["userid"],
                "homeid": session_data["homeid"],
                "livegroup_objectid": session_data["livegroup_objectid"],
                "sessiontoken": session_data["sessiontoken"],
            }
        )

    return devices_list


async def change_light(data, state):

    ID_param = {
        "_ApplicationId": data._applicationid,
        "_ClientVersion": "js1.9.2",
        "_InstallationId": data._installationid,
        "_JavaScriptKey": data._javascriptkey,
        "_SessionToken": data._sessiontoken,
    }

    # livegroup_last_request = livegroup_get_last_request(HomeID, ID_param)
    # if livegroup_last_request[1] == "bleData":
    #    last_light_command_number = livegroup_last_request[0][
    #        :2
    #    ]  # [:2] takes first two digits
    #    if last_light_command_number == "9f":
    #        light_command_number = "00"
    #    else:
    #        light_command_number = last_light_command_number
    #        light_command_number = int(
    #            light_command_number, 16
    #        )  # int(x, 16) turns to hex
    #        light_command_number = hex(light_command_number + 1)[2:].zfill(
    #            2
    #        )  # [2:] removes first two digis, zfill add zero if one digit
    # else:
    #    light_command_number = "00"

    light_command_number = "00"

    l = len(data._mac)
    mac_id = data._mac[l - 2 :]

    if state == "on":
        state_command = 1
    elif state == "off":
        state_command = 0

    light_command_data = (
        str(light_command_number)
        + "00000304"
        + str(mac_id)
        + "00ed69690"
        + str(state_command)
        + "000000000000000000"
    )

    bleData_request_data = {"data": light_command_data, "type": "bleData"}
    bleData_request = {
        "data": bleData_request_data,
        "from": data._userid,
        "time": unix_time(),
        "to": "ALL",
    }
    bleData = {"Cmd": 2, "Request": bleData_request, "_method": "PUT"}
    bleData.update(ID_param)

    api_url_web_livegroup_instance = (
        "https://www.pixie.app/p0/pixieCloud/classes/LiveGroup/"
        + data._livegroup_objectid
    )

    request = httpx.post(api_url_web_livegroup_instance, json=bleData)
    # json_data = json.dumps(request.json())
    # ble_success = json.loads(json_data)
    # TODO check success

    return


# used to get a response from pixie plus containing the last request made. In this data, the first two digits
# represent a counter (in hex) that can be used in the next command. however, it works without it so dropped for now
# def livegroup_get_last_request(HomeID, ID_param):

#    api_url_web_livegroup = "https://www.pixie.app/p0/pixieCloud/classes/LiveGroup"

#    livegroup_get_where = {"GroupID": HomeID}
#    livegroup_get = {"_method": "GET", "where": livegroup_get_where}
#    livegroup_get.update(ID_param)

#    request = httpx.post(api_url_web_livegroup, json=livegroup_get)
#    json_data = json.dumps(request.json())
#    livegroup_data = json.loads(json_data)

#    livegroup_last_request = (
#        livegroup_data["results"][0]["Request"]["data"]["data"],
#        livegroup_data["results"][0]["Request"]["data"]["type"],
#    )

#    return livegroup_last_request


# connect to websocket to get updates
async def pixie_websocket_connect(
    applicationid,
    installationid,
    javascriptkey,
    sessiontoken,
    userid,
    homeid,
    livegroup_objectid,
    coordinator,
    hass,
):

    # logger = logging.getLogger('websockets')
    # logger.setLevel(logging.DEBUG)
    # logger.addHandler(logging.StreamHandler())

    api_url_web_websocket = "wss://www.pixie.app/ws/p0/pixieCloud:443"

    ws_ID_param = {
        "applicationId": applicationid,
        "javascriptKey": javascriptkey,
        "sessionToken": sessiontoken,
    }

    ws_connect = {"op": "connect"}
    ws_connect.update(ws_ID_param)

    ws_subscribe_livegroup_where = {"GroupID": homeid}
    ws_subscribe_livegroup_query = {
        "className": "LiveGroup",
        "where": ws_subscribe_livegroup_where,
    }
    ws_subscribe_livegroup = {
        "op": "subscribe",
        "query": ws_subscribe_livegroup_query,
        "requestId": 1,
        "sessionToken": sessiontoken,
    }

    ws_subscribe_home_where = {"objectId": homeid}
    ws_subscribe_home_query = {"className": "Home", "where": ws_subscribe_home_where}
    ws_subscribe_home = {
        "op": "subscribe",
        "query": ws_subscribe_home_query,
        "requestId": 2,
        "sessionToken": sessiontoken,
    }

    ws_subscribe_HP_where = {"homeId": homeid, "userId": userid}
    ws_subscribe_HP_query = {"className": "HP", "where": ws_subscribe_HP_where}
    ws_subscribe_HP = {
        "op": "subscribe",
        "query": ws_subscribe_HP_query,
        "requestId": 3,
        "sessionToken": sessiontoken,
    }

    async for websocket in websockets.connect(api_url_web_websocket):
        try:
            await websocket.send(json.dumps(ws_connect))
            response = await websocket.recv()
            try:
                response = json.loads(response)
            except:
                _LOGGER.debug("Websocket response unable to be processed by json.loads")
            if "op" in response:
                if response["op"] == "connected":
                    _LOGGER.debug("Websocket connected")

            await websocket.send(json.dumps(ws_subscribe_livegroup))
            response = await websocket.recv()
            try:
                response = json.loads(response)
            except:
                _LOGGER.debug("Websocket response unable to be processed by json.loads")
            if "op" in response:
                if response["op"] == "subscribed":
                    _LOGGER.debug("Subscribed to Livegroup")

            await websocket.send(json.dumps(ws_subscribe_home))
            response = await websocket.recv()
            try:
                response = json.loads(response)
            except:
                _LOGGER.debug("Websocket response unable to be processed by json.loads")
            if "op" in response:
                if response["op"] == "subscribed":
                    _LOGGER.debug("Subscribed to home")

            await websocket.send(json.dumps(ws_subscribe_HP))
            response = await websocket.recv()
            try:
                response = json.loads(response)
            except:
                _LOGGER.debug("Websocket response unable to be processed by json.loads")
            if "op" in response:
                if response["op"] == "subscribed":
                    _LOGGER.debug("Subscribed to HP")

            while True:

                ws_update = await websocket.recv()

                try:
                    ws_update = json.loads(ws_update)
                except:
                    _LOGGER.warning(
                        "websocket data couldn't be proceesed through json.loads"
                    )
                    # print(json.dumps(ws_update, indent=4))
                    # _LOGGER.info(ws_update)
                if "op" in ws_update:
                    if ws_update["op"] == "update":
                        if "deviceList" in ws_update["object"]:
                            try:
                                # _LOGGER.debug(ws_update)
                                devices_list = parse_ws_data(
                                    ws_update,
                                    applicationid,
                                    installationid,
                                    javascriptkey,
                                    sessiontoken,
                                    userid,
                                    homeid,
                                    livegroup_objectid,
                                )
                                _LOGGER.debug(devices_list)
                                coordinator.async_set_updated_data(devices_list)
                            except:
                                _LOGGER.debug("unable to parse websocket input")
        except websockets.ConnectionClosed:
            _LOGGER.warning("websocket disconnected, reconnecting")
            continue
        except websockets.TimeoutError:
            _LOGGER.warning(
                "unable to connect to websocket, will try again in 1 minute"
            )
            continue

    return


# parses websocket data as has different structure from data recivied via http to get current devices
def parse_ws_data(
    devices,
    applicationid,
    installationid,
    javascriptkey,
    sessiontoken,
    userid,
    homeid,
    livegroup_objectid,
):

    numberofdevices = 0
    devices_list = list()
    state = ""

    numberofdevices = len(devices["object"]["deviceList"])

    for i in range(numberofdevices - 1):

        dev_id = devices["object"]["deviceList"][i]["id"]

        if devices["object"]["onlineList"][str(dev_id)]["br"] == 100:
            state = "true"

        elif devices["object"]["onlineList"][str(dev_id)]["br"] == 0:
            state = ""

        devices_list.append(
            {
                "name": devices["object"]["deviceList"][i]["name"],
                "id": devices["object"]["deviceList"][i]["id"],
                "color1": devices["object"]["deviceList"][i]["state"]["color"],
                "color2": devices["object"]["deviceList"][i]["state"]["color"][1],
                "color3": devices["object"]["deviceList"][i]["state"]["color"][2],
                "br": devices["object"]["deviceList"][i]["state"]["br"],
                "br2_1": devices["object"]["deviceList"][i]["state"]["br2"],
                "br2_2": devices["object"]["deviceList"][i]["state"]["br2"][1],
                "br2_3": devices["object"]["deviceList"][i]["state"]["br2"][2],
                "br2_4": devices["object"]["deviceList"][i]["state"]["br2"][3],
                "colour": devices["object"]["deviceList"][i]["state"]["colour"],
                "mac": devices["object"]["deviceList"][i]["mac"],
                "state": state,
                "applicationid": applicationid,
                "installationid": installationid,
                "javascriptkey": javascriptkey,
                "userid": userid,
                "homeid": homeid,
                "livegroup_objectid": livegroup_objectid,
                "sessiontoken": sessiontoken,
            }
        )

    # print(devices_list)
    return devices_list


# log out not currently used
# def pixie_logout():

#    request = httpx.post(api_url_web_logout, json=ID_param)
#    json_data = json.dumps(request.json())

#    return
