"""Alert SMS text in Hindi and English. Keep these in sync with the DLT-approved templates."""

CROP_HI = {
    "gehu": "गेहूं",
    "chawal": "चावल",
    "sarson": "सरसों",
    "pyaaz": "प्याज",
    "aloo": "आलू",
    "tamatar": "टमाटर",
    "makka": "मक्का",
}

CROP_EN = {
    "gehu": "Wheat",
    "chawal": "Rice",
    "sarson": "Mustard",
    "pyaaz": "Onion",
    "aloo": "Potato",
    "tamatar": "Tomato",
    "makka": "Maize",
}


def _hi(crop, mandi, price, direction, limit, date):
    side = "ऊपर" if direction == "above" else "नीचे"
    return (
        f"Cropora AI: {CROP_HI[crop]} ka bhav {mandi} mein ab Rs {price:.0f} hai "
        f"({date}). Aapki limit Rs {limit:.0f} se {side}."
    )


def _en(crop, mandi, price, direction, limit, date):
    side = "above" if direction == "above" else "below"
    return (
        f"Cropora AI: {CROP_EN[crop]} at {mandi} is now Rs {price:.0f} ({date}), "
        f"{side} your limit of Rs {limit:.0f}."
    )


def build_message(lang, crop, mandi, price, direction, limit, date):
    args = (crop, mandi, price, direction, limit, date)
    if lang == "en":
        return _en(*args)
    if lang == "both":
        return _en(*args) + "\n" + _hi(*args)
    return _hi(*args)
