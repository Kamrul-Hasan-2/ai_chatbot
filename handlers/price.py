
from services.api_service import search_products

def handle_price(ctx):
    if not ctx.get("cat"):
        return "Kon product er price?"

    products = search_products(ctx)
    if not products:
        return "Price pawa jay nai"

    return "Price: " + str(products[0].get("price","N/A"))
