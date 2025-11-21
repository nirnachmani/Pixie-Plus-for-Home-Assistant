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
