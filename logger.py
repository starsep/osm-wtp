from funcy import log_durations


def info(message: str):
    print(message)


log_duration = log_durations(lambda msg: info("⌛ " + msg))
with_duration = log_durations(lambda msg: info("⌛ " + msg))
