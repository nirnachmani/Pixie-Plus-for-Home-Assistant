"""Constants for the pixie_plus integration."""

DOMAIN = "pixie_plus"

hardware_list = {
    "0102": "Gateway G3 - SGW3BTAM",
    "2213": "Smart Switch G3 - SWL600BTAM",
    "2313": "Smart dimmer G3 - SDD300BTAM",
    "0107": "Smart plug - ESS105/BT",
    "2702": "Flexi smart LED strip - FLP12V2M/RGBBT",
    "2402": "Flexi Streamline - FLP24V2M",
    "2403": "LED Strip Controller - LT8915DIM/BT",
    "0208": "Smart Socket Outlet - SP023/BTAM",
    "1002": "Dual Relay Control - PC206DR/R/BTAM",
    "1102": "Blind & Signal Control - PC206BS/R/BTAM",
    "2212": "Smart Switch G2 - SWL350BT",
    "2312": "Smart Dimmer G2 - SDD350BT",
    "2311": "Smart Dimmer G2 - SDD350BT",
}

is_light = ["2213", "2313", "2702", "2402", "2403", "2212", "2312", "2311"]
has_dimming = ["2313", "2702", "2402", "2403", "2312", "2311"]
has_color = ["2702"]
has_white = []
is_switch = ["0107", "0208", "1002"]
has_two_entities = ["0208", "1002"]
dev_has_usb = ["0107"]
is_cover = ["1102"]

supported_features = {
    "2702": ["EFFECT"],
}

effect_list = {
    "2702": ["flash", "strobe", "fade", "smooth"],
}
