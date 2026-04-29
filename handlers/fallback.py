
def handle_fallback(ctx):
    if ctx.get("cat"):
        return "আরও বিস্তারিত বলবেন?"
    return "আপনি কোন ক্যাটাগরি খুঁজছেন?"
