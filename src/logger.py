from loguru import logger


def setup_logger():

    logger.remove()

    logger.add("arow_{time}.log")
