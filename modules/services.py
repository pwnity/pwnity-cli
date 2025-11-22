# modules/services.py
from modules.logger import Logger
from modules.config_parser import ConfigParser

config = ConfigParser()
log = Logger(config=config)