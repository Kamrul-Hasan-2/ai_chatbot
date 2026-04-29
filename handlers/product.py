
from services.api_service import search_products

def handle_product(ctx):
    if not ctx.get("cat"):
        return "Apni kon category khujchen?"

    products = search_products(ctx)
    if not products:
        return "Kono product pawa jay nai"

    return str(products[:3])
