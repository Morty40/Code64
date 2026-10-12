
def delay(n):
    return f"ldx #{n}\n_loop: dex\nbne _loop\n"
