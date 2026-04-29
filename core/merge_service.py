
def merge_context(new, old):

    if new.get("category") and old.get("cat") and new["category"] != old.get("cat"):
        return {"cat": new["category"], "brand":"", "title":"", "price":""}

    return {
        "cat": new.get("category") or old.get("cat"),
        "brand": new.get("brand") or old.get("brand"),
        "title": new.get("title") or old.get("title"),
        "price": new.get("price") or old.get("price"),
    }
