
from handlers.product import handle_product
from handlers.price import handle_price
from handlers.compare import handle_compare
from handlers.buy import handle_buy
from handlers.greeting import handle_greeting
from handlers.fallback import handle_fallback

def route_intent(intent, ctx, prev, msg):

    if intent == "greeting":
        return handle_greeting()

    if intent == "product":
        return handle_product(ctx)

    if intent == "price":
        return handle_price(ctx)

    if intent == "compare":
        return handle_compare()

    if intent == "buy":
        return handle_buy()

    return handle_fallback(ctx)
