# PIXIE Plus for Home Assistant

## Overview

This is a custom integration for Home Assistant that connects with PIXIE Plus smart home products made by [SAL](https://www.pixieplus.com/) (Australia). 

PIXIE offers a suite of Bluetooth Mesh smart home products for controlling various aspects of your home - including lights, blinds, garage doors, gates, fans, and appliances. This integration supports a variety of these devices with capabilities including dimming, colors, effects, and more.

> **⚠️ Important Note:** Installation requires technical knowledge and is not straightforward. This integration has been tested on limited systems and may require modifications to work with your setup. While not officially supported, I may be able to provide limited assistance.

## Supported Devices

The integration currently supports:

- **Smart Switches & Dimmers**
  - Smart Switch G3 (SWL600BTAM)
  - Smart Dimmer G3 (SDD300BTAM)
  - Smart Switch G2 (SWL350BT)
  - Smart Dimmer G2 (SDD350BT)
  - rippleSHIELD DIMMER (SDD400SFI)

- **Smart Plugs & Outlets**
  - Smart Plug (ESS105/BT)
  - Smart Socket Outlet (SP023/BTAM)

- **LED & Lighting**
  - Flexi Smart LED Strip (FLP12V2M/RGBBT)
  - Flexi Streamline (FLP24V2M)
  - LED Strip Controller (LT8915DIM/BT)

- **Control Devices**
  - Dual Relay Control (PC206DR/R/BTAM)
  - Blind & Signal Control (PC206BS/R/BTAM)

## Prerequisites

- A working PIXIE Plus Hub
- All devices must be already set up in the PIXIE Plus app
- Internet connection (local-only mode is not supported)

## Installation Guide

### Step 1: Copy Files
Copy the integration files into your Home Assistant `custom_components` folder and restart Home Assistant.

### Step 2: Add Integration
1. Go to Home Assistant → Settings → Devices & Services → Integrations
2. Click the "ADD INTEGRATION" button
3. Search for "PIXIE Plus" and select it
4. You will be prompted to enter your credentials

### Step 3: Required Credentials
You will need to provide:
1. Your PIXIE Plus username and password
2. Three additional parameters:
   - ApplicationID
   - InstallationID
   - client-key (previously called JavaScriptKey)

## How to Retrieve Required Parameters

These parameters are required for API communication but are not readily available. Below are several methods to obtain them:

> **⚠️ Important:** Using the parameters from your primary device will invalidate the session on that device. It's best to use a spare device or create a new account specifically for Home Assistant integration to avoid conflicts with your main PIXIE Plus app.

### Method 1: Using mitmproxy (Android)
1. Set up a rooted virtual Android device (Android SDK recommended)
2. Install the mitmproxy CA certificate as a system certificate
   - Follow [these instructions](https://docs.mitmproxy.org/stable/howto-install-system-trusted-ca-android/)
3. Install the PIXIE Plus app on the virtual phone
4. Configure the proxy settings on the virtual phone to point to mitmproxy
5. Log in to the PIXIE Plus app
6. Look for a POST request to `/p0/PIXIECloud/login` in mitmproxy
7. The required parameters will be in the request headers

### Method 2: Using mitmproxy + WireGuard (iOS/iPhone/iPad) - Windows
*With thanks to [hoskerism](https://github.com/hoskerism) and [brendanmckenzie](https://github.com/brendanmckenzie) for documenting this method*

1. Install PIXIE Plus and WireGuard on your iOS device
2. Install mitmproxy on your Windows computer
3. Run mitmweb in 'Normal' mode first:
   ```
   mitmweb
   ```
4. On your iOS device, set up the proxy settings on your WiFi network to use your Windows PC's IP address and the default port of 8080
5. On your iOS device, browse to mitm.it using Safari
6. Download the iOS certificate, install it and trust it following the instructions on the download page
7. Restart mitmproxy, this time in WireGuard mode:
   ```
   mitmweb --mode wireguard
   ```
8. On your iOS device, start the WireGuard app and create a new tunnel using the QR code displayed on the mitmproxy webpage
9. Enable the tunnel (you should now start to see traffic being captured in mitmproxy)
10. Log in to the PIXIE Plus app on your iOS device
11. Inspect the traffic for www.PIXIE.app in mitmproxy
12. Look for the `applicationId`, `clientKey` (previously JavaScriptKey), and `installationId` in the headers

### Method 3: Using mitmproxy + WireGuard (iOS/iPhone/iPad) - Mac
*With thanks to [brendanmckenzie](https://github.com/brendanmckenzie) for documenting this method*

1. Install mitmproxy on your Mac
2. Install WireGuard and the mitmproxy SSL certificate on your iOS device
3. Run mitmproxy in WireGuard mode on your Mac:
   ```
   mitmweb --mode wireguard
   ```
4. Configure WireGuard on your iOS device using the QR code displayed by mitmproxy
5. With WireGuard active, all traffic from your iOS device will be routed through mitmproxy
6. Log in to the PIXIE Plus app
7. Find the required values in the captured traffic

### Method 4: Using Proxyman (iPhone)
1. Install Proxyman on your computer
2. Set up Proxyman to intercept HTTPS traffic from your iPhone
3. Create a new PIXIE Plus account (important to avoid conflicts)
4. Log in with this new account in the PIXIE Plus app
5. Monitor the network traffic for requests to the PIXIE Plus API
6. Look for the same parameters in the request headers

> **Note:** These parameters appear to be stable and should only need to be retrieved once. They have been observed to work for months without needing to be refreshed.

## Configuration for Cover Devices

For the Blind & Signal Control device, additional configuration is required in `configuration.yaml`:

```yaml
PIXIE_plus:
  cover:
    blind_sc_171: # name of the cover as in the PIXIE Plus app but lowercase with underscores
        open: 2  # button position in the control panel
        close: 8
        stop: 5
```

The numbers correspond to button positions in the PIXIE Plus app control panel:
```
1, 2, 3
4, 5, 6
7, 8, 9
```

> **Important:** Use the original button positions even if you've rearranged them in the app.

## Known Issues

- **Smart Plug (ESS105/BT)**: The USB port state cannot be determined when initially loading the integration. State changes are tracked after loading, but if the state changes while Home Assistant is down, it won't be recorded correctly.

## Limitations

- The integration doesn't support PIXIE Plus groups, scenes, schedules, or timers (use Home Assistant for these functions)
- Only works with a PIXIE Plus Hub (doesn't support direct Bluetooth connections)
- Requires cloud connectivity (local-only mode is not currently possible)

## Support

This integration is provided as-is with limited support. Feel free to use, modify, and extend the code as needed for your own setup. I may be able to answer an occasional question (if I know the answer) but generally won’t have much time to spend on that.
