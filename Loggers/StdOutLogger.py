import logging
import sys

class StdoutLogger:
    def __init__(self, name='logger', level=logging.INFO):
        # Create a logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Check if handlers already exist to avoid adding them multiple times
        if not self.logger.handlers:

        # Create a handler for writing to stdout
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(level)

            # Create a formatter and set it for the handler
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)

            # Add the handler to the logger
            self.logger.addHandler(handler)

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def critical(self, message):
        self.logger.critical(message)   