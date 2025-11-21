import asyncio
import datetime
import json
import logging
import time

import httpx
import websockets
import ssl

from homeassistant.core import HomeAssistant 
from homeassistant.helpers.httpx_client import get_async_client 

from .const import (
    dev_has_usb,
    has_color,
    has_dimming,
    has_two_entities,
    is_cover,
    is_switch,
)

_LOGGER = logging.getLogger(__name__)

api_url = {
    "userquery": "https://www.pixie.app/p0/pixieCloud/functions/userQuery",
    "login": "https://www.pixie.app/p0/pixieCloud/login",
    "home": "https://www.pixie.app/p0/pixieCloud/classes/Home",
    "HP": "https://www.pixie.app/p0/pixieCloud/classes/HP",
    "livegroup": "https://www.pixie.app/p0/pixieCloud/classes/LiveGroup",
    "logout": "https://www.pixie.app/p0/pixieCloud/logout",
}


async def pixie_login(hass, config):
    # pixie plus hub is controlled from the cloud by accessing the foloowing url's
    # data required for login
    _LOGGER.debug("config", config)
    login_data = {
        "applicationid": config["applicationid"],
        "installationid": config["installationid"],
        "clientkey": config["clientkey"],
        "email": config["email"],
        "password": config["password"],
    }

    # session data has session speicifc data: sessionToken, userId, homeId
    session_data = await login(hass, login_data)

    live_group_data = await livegroup_get_objectID(hass, config, session_data)
    session_data.update(live_group_data)

    devices_list = await getdevices(hass, config, session_data)

    return (devices_list, session_data)


# check if user exist as part of config flow
def check_user(data):
    _LOGGER.info(f"checking user exists")
    body = {
        "email": data["email"],
    }
    headers = {
        "x-parse-application-id": data["applicationid"],
        "x-parse-installation-id": data["installationid"],
        "x-parse-client-key": data["clientkey"],
        "x-parse-revocable-session": "1",
    }
    req = httpx.post(api_url["userquery"], json=body, headers=headers)
    res = req.json()

    _LOGGER.debug("result", res)

    if "result" in res:
        return res["result"] == 1
    else:
        print(res)
        return False


async def login(hass, data):
    #_LOGGER.info(f"logging in")
    body = {"username": data["email"], "password": data["password"]}
    headers = {
        "x-parse-application-id": data["applicationid"],
        "x-parse-installation-id": data["installationid"],
        "x-parse-client-key": data["clientkey"],
        "x-parse-revocable-session": "1",
    }
    
    #req = httpx.post(api_url["login"], json=body, headers=headers)

    client = get_async_client(hass, False) 
    req = await client.post(api_url["login"], json=body, headers=headers)
    res = req.json()

    #async with httpx.AsyncClient() as client:
    #  req = await client.post(api_url["login"], json=body, headers=headers)
    #  res = req.json()

    _LOGGER.debug("result of login: %s", res)

    data = {
        "userid": res["objectId"],
        "homeid": res["curHome"]["objectId"] if "curHome" in res else await gethomeid(hass, data, res["sessionToken"]), 
        "sessiontoken": res["sessionToken"],
        "raw": res,
    }

    return data

async def gethomeid(hass, config, session_token):   
    body = {"where": {}, "skip": 0, "limit": 20}
                                 
    headers = {                        
        "x-parse-session-token": session_token,
        "x-parse-application-id": config["applicationid"],
        "x-parse-client-key": config["clientkey"],                        
    }                                           
                                
    client = get_async_client(hass, False)                          
    req = await client.get(api_url["home"], params=body, headers=headers)
    res = req.json()                                    
                                                                              
    return res["results"][0]["objectId"] 

async def livegroup_get_objectID(hass, config, session_data):
    body = {
        "where": json.dumps(
            {"GroupID": {"$regex": session_data["homeid"] + "$", "$options": "i"}}
        ),
        "limit": 2,
    }

    headers = {
        "x-parse-session-token": session_data["sessiontoken"],
        "x-parse-application-id": config["applicationid"],
        "x-parse-client-key": config["clientkey"],
    }

    client = get_async_client(hass, False) 
    req = await client.get(api_url["livegroup"], params=body, headers=headers)
    res = req.json()
    
    #req = httpx.get(api_url["livegroup"], params=body, headers=headers)
    #res = req.json()
    
    _LOGGER.debug("result of livegroup: %s", res)

    data = {
        "livegroup_objectid": res["results"][0]["objectId"],
        "bridge_name": res["results"][0]["Online"][0],
        "raw": res,
    }

    return data


def unix_time():
    return int(datetime.datetime.timestamp(datetime.datetime.now()) * 1000)


async def getdevices(hass, config, session_data):
    body = {"where": {}, "skip": 0, "limit": 20}

    headers = {
        "x-parse-session-token": session_data["sessiontoken"],
        "x-parse-application-id": config["applicationid"],
        "x-parse-client-key": config["clientkey"],
    }

    client = get_async_client(hass, False) 
    req = await client.get(api_url["home"], params=body, headers=headers)
    res = req.json()
    
    _LOGGER.debug("result of getdevices: %s", res)


    #req = httpx.get(api_url["home"], params=body, headers=headers)
    #res = req.json()

    return parse_devices(res, config, session_data)


def parse_devices(devices, config, session_data):
    if "error" in devices:
        if devices["code"] == 209:
            return _LOGGER.error("Login error, please reload the integration")
        else:
            return _LOGGER.error(f"Error getting devices: {devices}")

    numberofdevices = 0
    devices_list = list()
    applic_res = next(filter(lambda x: x['objectId'] == session_data["homeid"], devices["results"]))

    if not applic_res["onlineList"]:
        return _LOGGER.info(f"No onlineList in update, skipping")


    if "results" in devices:
        numberofdevices = len(applic_res["deviceList"])

    for i in range(numberofdevices):
        dev_id = applic_res["deviceList"][i]["id"]
        model_no = str(applic_res["deviceList"][i]["type"]).zfill(2) + str(
            applic_res["deviceList"][i]["stype"]
        ).zfill(2)

        _LOGGER.debug("model_no %s", model_no)

        if model_no == "0102":
            continue  # skips the gateway for now, doesn't add it to devices_list

        if model_no not in has_two_entities and model_no not in is_cover:
            try:
                if applic_res["onlineList"][str(dev_id)]["br"] > 0:
                    state = True
                elif applic_res["onlineList"][str(dev_id)]["br"] == 0:
                    state = ""
            except:
                _LOGGER.info(
                    "unable to get status for %s because it is not online",
                    applic_res["deviceList"][i]["name"],
                )
                continue

        if model_no in has_dimming:
            br_cur = (
                int(applic_res["onlineList"][str(dev_id)]["br"]) / 100
            ) * 255
        else:
            br_cur = ""

        if model_no in has_two_entities:
            # left first
            device_name = applic_res["deviceList"][i]["left_name"]
            master_device_name = applic_res["deviceList"][i]["name"]
            side = "left"
            try:
                if (applic_res["onlineList"][str(dev_id)]["r"] == 1) or (
                    applic_res["onlineList"][str(dev_id)]["r"] == 3
                ):
                    state = True
                else:
                    state = ""
            except:
                _LOGGER.info(
                    "unable to get status for %s because it is not online",
                    applic_res["deviceList"][i]["name"],
                )
                continue
        else:
            device_name = applic_res["deviceList"][i]["name"]
            master_device_name = ""
            side = ""

        if model_no in is_cover:
            state = None

        has_usb = ""

        devices_list.append(
            {
                "name": device_name,
                "id": applic_res["deviceList"][i]["id"],
                "br_cur": br_cur,
                "mac": applic_res["deviceList"][i]["mac"],
                "state": state,
                "type": applic_res["deviceList"][i]["type"],
                "stype": applic_res["deviceList"][i]["stype"],
                "email": config["email"],
                "applicationid": config["applicationid"],
                "installationid": config["installationid"],
                "clientkey": config["clientkey"],
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
                    "id": applic_res["deviceList"][i]["id"],
                    "br_cur": br_cur,
                    "mac": applic_res["deviceList"][i]["mac"],
                    "state": state,
                    "type": applic_res["deviceList"][i]["type"],
                    "stype": applic_res["deviceList"][i]["stype"],
                    "email": config["email"],
                    "applicationid": config["applicationid"],
                    "installationid": config["installationid"],
                    "clientkey": config["clientkey"],
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
            device_name = applic_res["deviceList"][i]["right_name"]
            side = "right"
            if (applic_res["onlineList"][str(dev_id)]["r"] == 2) or (
                applic_res["onlineList"][str(dev_id)]["r"] == 3
            ):
                state = True
            else:
                state = ""

            devices_list.append(
                {
                    "name": device_name,
                    "id": applic_res["deviceList"][i]["id"],
                    "br_cur": br_cur,
                    "mac": applic_res["deviceList"][i]["mac"],
                    "state": state,
                    "type": applic_res["deviceList"][i]["type"],
                    "stype": applic_res["deviceList"][i]["stype"],
                    "email": config["email"],
                    "applicationid": config["applicationid"],
                    "installationid": config["installationid"],
                    "clientkey": config["clientkey"],
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
    light_command_number = "00"
    mac_id = f"{data._id:02x}"
    model_no = str(data._type).zfill(2) + str(data._stype).zfill(2)

    if (state == "on") or (state == "00"):  # for on/off command
        if model_no in is_switch:  # for switch
            if data._has_usb:  # for USB
                state_command = "00"
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
                    state_command = "00"
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
                    state_command = "00"
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
            state_command = "00"
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
                effect_command = "00"
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
    bleData = {"Cmd": 2, "Request": bleData_request}
    # bleData.update(ID_param)

    api_url_web_livegroup_instance = (
        "https://www.pixie.app/p0/pixieCloud/classes/LiveGroup/"
        + data._livegroup_objectid
    )

    config = data.coordinator.config
    session_data = data.coordinator.session_data

    headers = {
        "x-parse-session-token": session_data["sessiontoken"],
        "x-parse-application-id": config["applicationid"],
        "x-parse-client-key": config["clientkey"],
    }

    request = httpx.put(api_url_web_livegroup_instance, json=bleData, headers=headers)
    _LOGGER.debug(bleData)
    _LOGGER.debug(request.url)
    _LOGGER.debug(request.text)

    # json_data = json.dumps(request.json())
    # ble_success = json.loads(json_data)
    # TODO check success

    return

async def create_ssl_context(hass: HomeAssistant) -> ssl.SSLContext:
    """Create an SSL context in a non-blocking way using Home Assistant's async executor."""
    return await hass.async_add_executor_job(ssl.create_default_context)

# connect to websocket to get updates
async def pixie_websocket_connect(hass: HomeAssistant, config, session_data, coordinator):
    # logger = logging.getLogger('websockets')
    # logger.setLevel(logging.DEBUG)
    # logger.addHandler(logging.StreamHandler())

    api_url_web_websocket = "wss://www.pixie.app/ws/p0/pixieCloud:443"

    # connect to ws
    ws_ID_param = {
        "applicationId": config["applicationid"],
        "sessionToken": session_data["sessiontoken"],
        "clientKey": config["clientkey"],
    }

    ws_connect = {"op": "connect"}
    ws_connect.update(ws_ID_param)

    # subscribe to livegroup
    ws_subscribe_livegroup_where = {"objectId": session_data["livegroup_objectid"]}
    ws_subscribe_livegroup_query = {
        "className": "LiveGroup",
        "where": ws_subscribe_livegroup_where,
    }
    ws_subscribe_livegroup = {
        "op": "subscribe",
        "query": ws_subscribe_livegroup_query,
        "requestId": 1,
        "sessionToken": session_data["sessiontoken"],
    }

    # subscribe to home
    ws_subscribe_home_where = {"objectId": session_data["homeid"]}
    ws_subscribe_home_query = {"className": "Home", "where": ws_subscribe_home_where}
    ws_subscribe_home = {
        "op": "subscribe",
        "query": ws_subscribe_home_query,
        "requestId": 2,
        "sessionToken": session_data["sessiontoken"],
    }

    # subscribe to HP
    ws_subscribe_HP_where = {
        "homeId": session_data["homeid"],
        "userId": session_data["userid"],
    }
    ws_subscribe_HP_query = {"className": "HP", "where": ws_subscribe_HP_where}
    ws_subscribe_HP = {
        "op": "subscribe",
        "query": ws_subscribe_HP_query,
        "requestId": 3,
        "sessionToken": session_data["sessiontoken"],
    }
    
    ssl_context = await create_ssl_context(hass)

    async for websocket in websockets.connect(api_url_web_websocket, ssl=ssl_context):
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
                    _LOGGER.debug(ws_update)
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
                                    ws_update, coordinator, config, session_data
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
                                _LOGGER.debug(ws_update)
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
                                _LOGGER.debug(ws_update)
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


def parse_ws_data(devices, coordinator, config, session_data):
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
                "br_cur": br_cur,
                "mac": devices["object"]["deviceList"][i]["mac"],
                "state": state,
                "type": devices["object"]["deviceList"][i]["type"],
                "stype": devices["object"]["deviceList"][i]["stype"],
                "email": config["email"],
                "applicationid": config["applicationid"],
                "installationid": config["installationid"],
                "clientkey": config["clientkey"],
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
        # _LOGGER.info("the interim devices list is: %s", devices_list)
        if model_no in dev_has_usb:
            has_usb = True

            for device in (
                coordinator.data
            ):  # usb state is not provided in the update so looking for existing state
                if (dev_id == device["id"]) and (device["has_usb"]):
                    state = device["state"]
                    # _LOGGER.info("state from coordinator data is: %s", state)

            devices_list.append(
                {
                    "name": device_name,
                    "id": devices["object"]["deviceList"][i]["id"],
                    "br_cur": br_cur,
                    "mac": devices["object"]["deviceList"][i]["mac"],
                    "state": state,
                    "type": devices["object"]["deviceList"][i]["type"],
                    "stype": devices["object"]["deviceList"][i]["stype"],
                    "email": config["email"],
                    "applicationid": config["applicationid"],
                    "installationid": config["installationid"],
                    "clientkey": config["clientkey"],
                    "userid": session_data["userid"],
                    "homeid": session_data["homeid"],
                    "livegroup_objectid": session_data["livegroup_objectid"],
                    "sessiontoken": session_data["sessiontoken"],
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
                    "br_cur": br_cur,
                    "mac": devices["object"]["deviceList"][i]["mac"],
                    "state": state,
                    "type": devices["object"]["deviceList"][i]["type"],
                    "stype": devices["object"]["deviceList"][i]["stype"],
                    "email": config["email"],
                    "applicationid": config["applicationid"],
                    "installationid": config["installationid"],
                    "clientkey": config["clientkey"],
                    "userid": session_data["userid"],
                    "homeid": session_data["homeid"],
                    "livegroup_objectid": session_data["livegroup_objectid"],
                    "sessiontoken": session_data["sessiontoken"],
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
                + "00fa6b69000101027700"
            )
        else:
            light_command_data = (
                str(light_command_number)
                + "00000304"
                + str(mac_id)
                + "00fa6b690"
                + str(x)
                + "0101017700"
            )

        bleData_request_data = {
            "data": light_command_data,
            "type": "bleData",
            "repeat": 2,
        }
        bleData_request = {
            "data": bleData_request_data,
            "from": data._email,
            "time": unix_time(),
            "to": "ALL",
        }
        bleData = {"Cmd": 2, "Request": bleData_request}
        # bleData.update(ID_param)

        headers = {
            "x-parse-session-token": data._sessiontoken,
            "x-parse-application-id": data._applicationid,
            "x-parse-client-key": data._clientkey,
        }
        _LOGGER.debug(f"cover request_headers: {headers}")
        _LOGGER.debug(f"cover request_data: {bleData}")

        request = httpx.put(
            api_url_web_livegroup_instance, json=bleData, headers=headers
        )
        result = request.json()
        #        request = httpx.post(api_url_web_livegroup_instance, json=bleData)

        cover_response.append(result)

    return cover_response


# log out not currently used
# def pixie_logout():

#    request = httpx.post(api_url_web_logout, json=ID_param)
#    json_data = json.dumps(request.json())

#    return
