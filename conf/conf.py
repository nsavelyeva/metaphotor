import os
import errno
import json


CONFIG_FOLDER = os.path.dirname(os.path.abspath(__file__))
CUSTOM_SETTINGS_FILE = os.path.join(CONFIG_FOLDER, "custom.json")
with open(CUSTOM_SETTINGS_FILE, "r") as _f:
    CUSTOM_SETTINGS = json.loads(_f.read().strip())


def mkdir_if_not_exists(abs_path, dir_name):
    full_path = os.path.normpath(os.path.join(abs_path, dir_name))
    try:
        os.makedirs(full_path)
    except OSError as err:
        if err.errno != errno.EEXIST:
            print("Could not create directory %s: %s" % (full_path, err))
            raise
    return True


class BaseConf(object):
    """
    Base configuration including settings configurable by user
    """

    APP_FOLDER = CONFIG_FOLDER[:-5]  # strip "/conf" (Linux) or "\conf" (Windows)
    CONFIG_FOLDER = CONFIG_FOLDER
    SETTINGS_FILE = CUSTOM_SETTINGS_FILE
    DATABASE = os.path.join(CONFIG_FOLDER, "..", "metaphotor.db")
    SQLALCHEMY_DATABASE_URI = "sqlite:///%s" % DATABASE
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.normpath("app/uploads")  # will be created if does not exist
    DOWNLOAD_FOLDER = "downloads"  # will be created if does not exist
    ALLOWED_EXTENSIONS = ["jpg", "jpeg"] #, "mov", "mp4"]
    TESTING = False
    # Below will be configurable by user:
    MEDIA_FOLDER = CUSTOM_SETTINGS["MEDIA_FOLDER"]
    FFMPEG_PATH = CUSTOM_SETTINGS["FFMPEG_PATH"]
    MIN_FILESIZE = CUSTOM_SETTINGS["MIN_FILESIZE"]
    MAX_FILESIZE = CUSTOM_SETTINGS["MAX_FILESIZE"]
    ITEMS_PER_PAGE = CUSTOM_SETTINGS["ITEMS_PER_PAGE"]


class DevConf(BaseConf):
    """
    Development configuration
    """

    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProdConf(BaseConf):
    """
    Production configuration
    """

    DEBUG = False
    SQLALCHEMY_ECHO = False
