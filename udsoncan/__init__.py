import logging
import logging.config
from os import path

from udsoncan.exceptions import *
from udsoncan.response import Response
from udsoncan.request import Request

from udsoncan.common import *
from udsoncan.typing import *

__version__ = "1.23.1"
__license__ = "MIT"
__author__ = "Pier-Yves Lessard"

latest_standard = 2020
__default_log_config_file = path.join(
    path.dirname(path.abspath(__file__)), "logging.conf"
)


def setup_logging(config_file=__default_log_config_file):
    """
    This function setup the logger accordingly to the module provided cfg file
    """
    try:
        logging.config.fileConfig(config_file)
    except Exception as e:
        logging.warning(
            "Cannot load logging configuration from %s. %s:%s"
            % (config_file, e.__class__.__name__, str(e))
        )
