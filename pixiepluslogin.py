import json
import httpx
import websockets
import datetime
import logging
import asyncio
import time

from .const import (
    has_dimming,
    has_color,
    is_switch,
    has_two_entities,
    dev_has_usb,
    is_cover,
)


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
    if session_data == "LoginError":
        raise Exception("Unable to loigin, check credentials")
    elif session_data == "ConnectionError":
        raise ConnectionError("Unable to connect - check your internet")
    else:
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

    livegroup_get_last_request(session_data, ID_param)

    devices_list = await getdevices(session_data, ID_param)

    if devices_list != "":
        return devices_list


# check if user exist as part of config flow
def check_user(api_url, data):

    userquery = {
        "_ApplicationId": data["applicationid"],
        "_ClientVersion": "js1.9.2",
        "_InstallationId": data["installationid"],
        "_JavaScriptKey": data["javascriptkey"],
        "email": data["email"],
    }

    request = httpx.post(api_url["userquery"], json=userquery)
    userexist = json.loads(request.text)

    try:
        if userexist["result"] == 1:
            return True
        else:
            return False
    except:
        return False


def login(api_url, login_data):

    login_command = {
        "_ApplicationId": login_data["applicationid"],
        "_ClientVersion": "js1.9.2",
        "_InstallationId": login_data["installationid"],
        "_JavaScriptKey": login_data["javascriptkey"],
        "_method": "GET",
        "password": login_data["password"],
        "username": login_data["email"],
    }

    try:
        request = httpx.post(api_url["login"], json=login_command)
    except:
        return "ConnectionError"

    try:
        json_data = json.dumps(request.json())
        data = json.loads(json_data)
        session_data = {
            "userid": data["objectId"],
            "homeid": data["curHome"]["objectId"],
            "sessiontoken": data["sessionToken"],
        }
        return session_data
    except:
        return "LoginError"


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


# used to get a response from pixie plus containing the last request made. In this data, the first two digits
# represent a counter (in hex) that can be used in the next command. however, it works without it so dropped for now
def livegroup_get_last_request(session_data, ID_param):

    api_url_web_livegroup = "https://www.pixie.app/p0/pixieCloud/classes/LiveGroup"

    livegroup_get_where = {"GroupID": session_data["homeid"]}
    livegroup_get = {"_method": "GET", "where": livegroup_get_where}
    livegroup_get.update(ID_param)

    livegroup_get_2 = {"limit": 1, "_method": "GET", "where": livegroup_get_where}
    livegroup_get_2.update(ID_param)

    request = httpx.post(api_url_web_livegroup, json=livegroup_get)
    json_data = json.dumps(request.json())
    livegroup_data = json.loads(json_data)

    livegroup_last_request = (
        livegroup_data["results"][0]["Request"]["data"]["data"],
        livegroup_data["results"][0]["Request"]["data"]["type"],
    )

    httpx.post(api_url_web_livegroup, json=livegroup_get_2)

    return livegroup_last_request


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
        # print(devices)
        # _LOGGER.debug(devices)
        devices_list = parse_devices(devices, session_data)
        # _LOGGER.info(devices_list)
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
            return _LOGGER.error("Login error, please reload the integration")
        else:
            return _LOGGER.error(f"Error getting devices: {devices}")
    if not devices["results"][0]["onlineList"]:
        return _LOGGER.info(f"No onlineList in update, skipping")

    for i in range(numberofdevices):

        dev_id = devices["results"][0]["deviceList"][i]["id"]
        model_no = str(devices["results"][0]["deviceList"][i]["type"]).zfill(2) + str(
            devices["results"][0]["deviceList"][i]["stype"]
        ).zfill(2)

        if model_no == "0102":
            continue  # skips the gateway for now, doesn't add it to devices_list

        if model_no not in has_two_entities and model_no not in is_cover:
            try:
                if devices["results"][0]["onlineList"][str(dev_id)]["br"] > 0:
                    state = True
                elif devices["results"][0]["onlineList"][str(dev_id)]["br"] == 0:
                    state = ""
            except:
                _LOGGER.info(
                    "unable to get status for %s because it is not online",
                    devices["results"][0]["deviceList"][i]["name"],
                )
                continue

        if model_no in has_dimming:
            br_cur = (
                int(devices["results"][0]["onlineList"][str(dev_id)]["br"]) / 100
            ) * 255
        else:
            br_cur = ""

        if model_no in has_two_entities:
            # left first
            device_name = devices["results"][0]["deviceList"][i]["left_name"]
            master_device_name = devices["results"][0]["deviceList"][i]["name"]
            side = "left"
            try:
                if (devices["results"][0]["onlineList"][str(dev_id)]["r"] == 1) or (
                    devices["results"][0]["onlineList"][str(dev_id)]["r"] == 3
                ):
                    state = True
                else:
                    state = ""
            except:
                _LOGGER.info(
                    "unable to get status for %s because it is not online",
                    devices["results"][0]["deviceList"][i]["name"],
                )
                continue
        else:
            device_name = devices["results"][0]["deviceList"][i]["name"]
            master_device_name = ""
            side = ""

        if model_no in is_cover:
            state = None

        has_usb = ""

        devices_list.append(
            {
                "name": device_name,
                "id": devices["results"][0]["deviceList"][i]["id"],
                "br": devices["results"][0]["deviceList"][i]["state"]["br"],
                "br_cur": br_cur,
                "mac": devices["results"][0]["deviceList"][i]["mac"],
                "state": state,
                "type": devices["results"][0]["deviceList"][i]["type"],
                "stype": devices["results"][0]["deviceList"][i]["stype"],
                "applicationid": session_data["applicationid"],
                "installationid": session_data["installationid"],
                "javascriptkey": session_data["javascriptkey"],
                "userid": session_data["userid"],
                "homeid": session_data["homeid"],
                "livegroup_objectid": session_data["livegroup_objectid"],
                "sessiontoken": session_data["sessiontoken"],
                "master_device_name": master_device_name,
                "side": side,
                "has_usb": has_usb,
                "has_usb_update": "",
            }
        )

        if model_no in dev_has_usb:

            has_usb = True
            state = ""

            devices_list.append(
                {
                    "name": device_name,
                    "id": devices["results"][0]["deviceList"][i]["id"],
                    "br": devices["results"][0]["deviceList"][i]["state"]["br"],
                    "br_cur": br_cur,
                    "mac": devices["results"][0]["deviceList"][i]["mac"],
                    "state": state,
                    "type": devices["results"][0]["deviceList"][i]["type"],
                    "stype": devices["results"][0]["deviceList"][i]["stype"],
                    "applicationid": session_data["applicationid"],
                    "installationid": session_data["installationid"],
                    "javascriptkey": session_data["javascriptkey"],
                    "userid": session_data["userid"],
                    "homeid": session_data["homeid"],
                    "livegroup_objectid": session_data["livegroup_objectid"],
                    "sessiontoken": session_data["sessiontoken"],
                    "master_device_name": master_device_name,
                    "side": side,
                    "has_usb": has_usb,
                    "has_usb_update": "",
                }
            )
        elif model_no in has_two_entities:
            device_name = devices["results"][0]["deviceList"][i]["right_name"]
            side = "right"
            if (devices["results"][0]["onlineList"][str(dev_id)]["r"] == 2) or (
                devices["results"][0]["onlineList"][str(dev_id)]["r"] == 3
            ):
                state = True
            else:
                state = ""

            devices_list.append(
                {
                    "name": device_name,
                    "id": devices["results"][0]["deviceList"][i]["id"],
                    "br": devices["results"][0]["deviceList"][i]["state"]["br"],
                    "br_cur": br_cur,
                    "mac": devices["results"][0]["deviceList"][i]["mac"],
                    "state": state,
                    "type": devices["results"][0]["deviceList"][i]["type"],
                    "stype": devices["results"][0]["deviceList"][i]["stype"],
                    "applicationid": session_data["applicationid"],
                    "installationid": session_data["installationid"],
                    "javascriptkey": session_data["javascriptkey"],
                    "userid": session_data["userid"],
                    "homeid": session_data["homeid"],
                    "livegroup_objectid": session_data["livegroup_objectid"],
                    "sessiontoken": session_data["sessiontoken"],
                    "master_device_name": master_device_name,
                    "side": side,
                    "has_usb": has_usb,
                    "has_usb_update": "",
                }
            )
    # _LOGGER.info(devices_list)
    return devices_list


async def change_light(data, state, other):

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
    mac_id = f"{data._id:02x}"
    model_no = str(data._type).zfill(2) + str(data._stype).zfill(2)

    if (state == "on") or (state == "00"):  # for on/off command

        if model_no in is_switch:  # for switch

            if data._has_usb:  # for USB

                if state == "on":
                    state_command = "0c"
                elif state == "00":
                    state_command = "08"

                light_command_data = (
                    str(light_command_number)
                    + "00000304"
                    + str(mac_id)
                    + "00c16969"
                    + str(state_command)
                    + "000000"
                )

            else:  # for main switch

                if (
                    model_no in has_two_entities
                ):  # for models with left and right sockets
                    if data._side == "left":
                        if state == "on":
                            state_command = "11"
                        elif state == "00":
                            state_command = "10"
                    elif data._side == "right":
                        if state == "on":
                            state_command = "22"
                        elif state == "00":
                            state_command = "20"

                    light_command_data = (
                        str(light_command_number)
                        + "00000304"
                        + str(mac_id)
                        + "00c16969"
                        + str(state_command)
                        + "000000000000000000"
                    )

                else:  # for single switch
                    if state == "on":
                        state_command = "03"
                    elif state == "00":
                        state_command = "02"

                    light_command_data = (
                        str(light_command_number)
                        + "00000304"
                        + str(mac_id)
                        + "00c16969"
                        + str(state_command)
                        + "000000"
                    )

        else:  # for light

            if state == "on":
                state_command = 1
            elif state == "00":
                state_command = 0

            light_command_data = (
                str(light_command_number)
                + "00000304"
                + str(mac_id)
                + "00ed69690"
                + str(state_command)
                + "000000000000000000"
            )
    elif state == "open" or state == "close" or state == "stop":  # for cover
        if state == "open":
            state = int(data._cover_open) - 1
        elif state == "close":
            state = int(data._cover_close) - 1
        elif state == "stop":
            state = int(data._cover_stop) - 1

        light_command_data = (
            str(light_command_number)
            + "00000304"
            + str(mac_id)
            + "00c169690000000"
            + str(state)
            + "000000000000"
        )
    else:  # for chaning brightness (hex value in state to change brightness), color and other parameters
        light_command_data = (
            str(light_command_number)
            + "00000304"
            + str(mac_id)
            + "00c46969ffffff"
            + str(state)
        )

        if other:
            if other["rgb_color"]:
                colors = other["rgb_color"]
                color_command = (
                    hex(colors[0])[2:].zfill(2)
                    + hex(colors[1])[2:].zfill(2)
                    + hex(colors[2])[2:].zfill(2)
                )
            else:
                color_command = "ffffff"

            if other["effect"]:
                effect = other["effect"]
                if effect == "flash":
                    effect_command = "01"
                elif effect == "strobe":
                    effect_command = "02"
                elif effect == "smooth":
                    effect_command = "03"
                elif effect == "fade":
                    effect_command = "04"
                light_command_data = (
                    str(light_command_number)
                    + "00000304"
                    + str(mac_id)
                    + "00f86969"
                    + str(effect_command)
                    + "21"
                    + "0000ff"
                )
            else:
                light_command_data = (
                    str(light_command_number)
                    + "00000304"
                    + str(mac_id)
                    + "00c46969"
                    + color_command
                    + str(state)
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

    ws_subscribe_livegroup_where = {"GroupID2": homeid}
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
                    _LOGGER.info("Websocket connected")
                    print("Websocket connected")

            await websocket.send(json.dumps(ws_subscribe_livegroup))
            response = await websocket.recv()
            try:
                response = json.loads(response)
            except:
                _LOGGER.debug("Websocket response unable to be processed by json.loads")
            if "op" in response:
                if response["op"] == "subscribed":
                    _LOGGER.info("Subscribed to Livegroup")
                    print("Subscribed to Livegroup")

            await websocket.send(json.dumps(ws_subscribe_home))
            response = await websocket.recv()
            try:
                response = json.loads(response)
            except:
                _LOGGER.debug("Websocket response unable to be processed by json.loads")
            if "op" in response:
                if response["op"] == "subscribed":
                    _LOGGER.info("Subscribed to home")
                    print("Subscribed to home")

            await websocket.send(json.dumps(ws_subscribe_HP))
            response = await websocket.recv()
            try:
                response = json.loads(response)
            except:
                _LOGGER.debug("Websocket response unable to be processed by json.loads")
            if "op" in response:
                if response["op"] == "subscribed":
                    _LOGGER.info("Subscribed to HP")
                    print("Subscribed to HP")

            while True:

                ws_update = await websocket.recv()
                # print("\nnew update\n")
                # print(ws_update)
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
                                # _LOGGER.info(ws_update)
                                devices_list = parse_ws_data(
                                    ws_update,
                                    coordinator,
                                    applicationid,
                                    installationid,
                                    javascriptkey,
                                    sessiontoken,
                                    userid,
                                    homeid,
                                    livegroup_objectid,
                                )
                                # _LOGGER.info(
                                #    "devices_list after parsing by main ws update: %s",
                                #    devices_list,
                                # )
                                # print("processed device list")
                                # print(devices_list)
                                if devices_list:
                                    coordinator.async_set_updated_data(devices_list)
                            except:
                                _LOGGER.error("unable to parse large websocket input")
                                _LOGGER.info(ws_update)
                        if ws_update["requestId"] == 1:
                            try:
                                # _LOGGER.info(ws_update)
                                devices_list = parse_single_ws_update(
                                    coordinator, ws_update
                                )
                                # _LOGGER.info(
                                #    "devices_list after parsing by small ws update: %s",
                                #    devices_list,
                                # )
                                if devices_list:
                                    coordinator.async_set_updated_data(devices_list)
                            except ValueError as toolong:
                                _LOGGER.debug(toolong)
                            except RuntimeError as no_data:
                                _LOGGER.debug(no_data)
                            except:
                                _LOGGER.info("unable to parse small websocket input")
                                _LOGGER.info(ws_update)
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
    coordinator,
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

    if not devices["object"]["onlineList"]:
        _LOGGER.info(f"No onlineList in websocket update, skipping")
        return

    numberofdevices = len(devices["object"]["deviceList"])
    # _LOGGER.info("number of devices is: %s", numberofdevices)

    for i in range(numberofdevices):

        dev_id = devices["object"]["deviceList"][i]["id"]
        # _LOGGER.info("dev_id is: %s", dev_id)
        model_no = str(devices["object"]["deviceList"][i]["type"]).zfill(2) + str(
            devices["object"]["deviceList"][i]["stype"]
        ).zfill(2)
        # _LOGGER.info("model_no is: %s", model_no)

        if model_no == "0102":
            continue  # skips the gateway for now, doesn't add it to devices_list

        if model_no not in has_two_entities and model_no not in is_cover:
            try:
                if devices["object"]["onlineList"][str(dev_id)]["br"] > 0:
                    state = True
                elif devices["object"]["onlineList"][str(dev_id)]["br"] == 0:
                    state = ""
            except:
                _LOGGER.info(
                    "unable to get status for %s because it is not online",
                    devices["object"]["deviceList"][i]["name"],
                )
                continue

        # _LOGGER.info("new state is: %s", state)

        if model_no in has_dimming:
            br_cur = (
                int(devices["object"]["onlineList"][str(dev_id)]["br"]) / 100
            ) * 255
        else:
            br_cur = ""

        if model_no in has_two_entities:
            # left first
            device_name = devices["object"]["deviceList"][i]["left_name"]
            master_device_name = devices["object"]["deviceList"][i]["name"]
            side = "left"
            try:
                if (devices["object"]["onlineList"][str(dev_id)]["r"] == 1) or (
                    devices["object"]["onlineList"][str(dev_id)]["r"] == 3
                ):
                    state = True
                else:
                    state = ""
            except:
                _LOGGER.info(
                    "unable to get status for %s because it is not online",
                    devices["object"]["deviceList"][i]["name"],
                )
                continue
        else:
            device_name = devices["object"]["deviceList"][i]["name"]
            master_device_name = ""
            side = ""

        if model_no in is_cover:
            state = None

        has_usb = ""

        devices_list.append(
            {
                "name": device_name,
                "id": devices["object"]["deviceList"][i]["id"],
                "br": devices["object"]["deviceList"][i]["state"]["br"],
                "br_cur": br_cur,
                "mac": devices["object"]["deviceList"][i]["mac"],
                "state": state,
                "type": devices["object"]["deviceList"][i]["type"],
                "stype": devices["object"]["deviceList"][i]["stype"],
                "applicationid": applicationid,
                "installationid": installationid,
                "javascriptkey": javascriptkey,
                "userid": userid,
                "homeid": homeid,
                "livegroup_objectid": livegroup_objectid,
                "sessiontoken": sessiontoken,
                "master_device_name": master_device_name,
                "side": side,
                "has_usb": has_usb,
                "has_usb_update": "",
            }
        )
        # _LOGGER.info("the interim devices list is: %s", devices_list)
        if model_no in dev_has_usb:

            has_usb = True

            for (
                device
            ) in (
                coordinator.data
            ):  # usb state is not provided in the update so looking for existing state

                if (dev_id == device["id"]) and (device["has_usb"]):
                    state = device["state"]
                    # _LOGGER.info("state from coordinator data is: %s", state)

            devices_list.append(
                {
                    "name": device_name,
                    "id": devices["object"]["deviceList"][i]["id"],
                    "br": devices["object"]["deviceList"][i]["state"]["br"],
                    "br_cur": br_cur,
                    "mac": devices["object"]["deviceList"][i]["mac"],
                    "state": state,
                    "type": devices["object"]["deviceList"][i]["type"],
                    "stype": devices["object"]["deviceList"][i]["stype"],
                    "applicationid": applicationid,
                    "installationid": installationid,
                    "javascriptkey": javascriptkey,
                    "userid": userid,
                    "homeid": homeid,
                    "livegroup_objectid": livegroup_objectid,
                    "sessiontoken": sessiontoken,
                    "side": side,
                    "has_usb": has_usb,
                    "has_usb_update": True,
                }
            )

        elif model_no in has_two_entities:
            device_name = devices["object"]["deviceList"][i]["right_name"]
            side = "right"
            if (devices["object"]["onlineList"][str(dev_id)]["r"] == 2) or (
                devices["object"]["onlineList"][str(dev_id)]["r"] == 3
            ):
                state = True
            else:
                state = ""

            devices_list.append(
                {
                    "name": device_name,
                    "id": devices["object"]["deviceList"][i]["id"],
                    "br": devices["object"]["deviceList"][i]["state"]["br"],
                    "br_cur": br_cur,
                    "mac": devices["object"]["deviceList"][i]["mac"],
                    "state": state,
                    "type": devices["object"]["deviceList"][i]["type"],
                    "stype": devices["object"]["deviceList"][i]["stype"],
                    "applicationid": applicationid,
                    "installationid": installationid,
                    "javascriptkey": javascriptkey,
                    "userid": userid,
                    "homeid": homeid,
                    "livegroup_objectid": livegroup_objectid,
                    "sessiontoken": sessiontoken,
                    "side": side,
                    "has_usb": has_usb,
                    "has_usb_update": "",
                }
            )

    # _LOGGER.info("the updated devices list is: %s", devices_list)
    # print(devices_list)
    return devices_list


def parse_single_ws_update(coordinator, ws_update):

    devices_list = coordinator.data
    # _LOGGER.info("devices list from coordinator: %s", devices_list)

    update_data = ws_update["object"]["Result"]["data"]["data"]
    if type(update_data) is dict:
        update_data = update_data["data"]

    if len(update_data) > 30:
        _LOGGER.debug(update_data)
        raise ValueError("update with long string - skipping")

    mac_id = update_data[20:22]
    new_state_data = update_data[24:26]
    # _LOGGER.info("mac_id: %s, new_state_data: %s", mac_id, new_state_data)

    for device in devices_list:

        # _LOGGER.info(device["mac"][15:])
        if (mac_id == hex(device["id"])[2:].zfill(2)) and (device["has_usb"]):
            # _LOGGER.info(device["has_usb"])

            if (new_state_data == "0f") or (new_state_data == "0e"):
                device["state"] = True
                # _LOGGER.info("new device state is: %s", device["state"])
            elif (new_state_data == "0d") or (new_state_data == "0c"):
                device["state"] = ""
                # _LOGGER.info("new device state is: %s", device["state"])
            device["has_usb_update"] = True
            # _LOGGER.info("has usb update is: %s", device["has_usb_update"])
    # _LOGGER.info("devices list after small update is: %s", devices_list)
    return devices_list


def initiate_cover(data):

    ID_param = {
        "_ApplicationId": data._applicationid,
        "_ClientVersion": "js1.9.2",
        "_InstallationId": data._installationid,
        "_JavaScriptKey": data._javascriptkey,
        "_SessionToken": data._sessiontoken,
    }

    light_command_number = "00"
    mac_id = hex(data._id)[2:].zfill(2)
    cover_command_list = []
    cover_response = []

    if data._cover_open:
        cover_command_list.append(data._cover_open)
    if data._cover_close:
        cover_command_list.append(data._cover_close)
    if data._cover_stop:
        cover_command_list.append(data._cover_stop)

    cover_command_list.append(0)
    cover_command_list.append(10)

    cover_command_list.sort()

    api_url_web_livegroup_instance = (
        "https://www.pixie.app/p0/pixieCloud/classes/LiveGroup/"
        + data._livegroup_objectid
    )

    for x in cover_command_list:

        if x == 10:
            light_command_data = (
                str(light_command_number)
                + "00000304"
                + str(mac_id)
                + "00fa6b69000100027700"
            )
        else:
            light_command_data = (
                str(light_command_number)
                + "00000304"
                + str(mac_id)
                + "00fa6b690"
                + str(x)
                + "0100017700"
            )

        bleData_request_data = {
            "data": light_command_data,
            "type": "bleData",
            "repeat": 2,
        }
        bleData_request = {
            "data": bleData_request_data,
            "from": data._userid,
            "time": unix_time(),
            "to": "ALL",
        }
        bleData = {"Cmd": 2, "Request": bleData_request, "_method": "PUT"}
        bleData.update(ID_param)

        request = httpx.post(api_url_web_livegroup_instance, json=bleData)

        cover_response.append(request)

    return cover_response


# log out not currently used
# def pixie_logout():

#    request = httpx.post(api_url_web_logout, json=ID_param)
#    json_data = json.dumps(request.json())

#    return
