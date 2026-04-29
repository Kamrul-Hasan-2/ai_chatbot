
def detect_intent(message):
    msg = message.lower()

    if any(x in msg for x in ["hi","hello","assalamu"]):
        return {"intent":"greeting","entities":{}}

    if any(x in msg for x in ["buy","order","kivabe"]):
        return {"intent":"buy","entities":{}}

    if any(x in msg for x in ["which","konti","valo"]):
        return {"intent":"compare","entities":{}}

    if any(x in msg for x in ["price","koto","dam","under"]):
        return {"intent":"price","entities":{}}

    if "laptop" in msg:
        return {"intent":"product","entities":{"category":"Laptop"}}

    return {"intent":"unknown","entities":{}}
