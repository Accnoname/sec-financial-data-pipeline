import logging

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO
)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

