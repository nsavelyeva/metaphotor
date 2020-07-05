import os
import json


def init_conf(settings_file):
    """
    Create persist/conf.json file if not exists, otherwise read settings from it.
    Return settings as a dictionary.
    """
    try:
        with open(settings_file, 'r') as _f:
            custom_settings = json.loads(_f.read().strip())
    except FileNotFoundError:
        custom_settings = {'MEDIA_FOLDER': '/opt/metaphotor/app/media',
                           'WATCH_FOLDER': '/opt/metaphotor/app/watch',
                           'FFMPEG_PATH': '/usr/bin/ffmpeg',
                           'FFPROBE_PATH': '/usr/bin/ffprobe',
                           'MIN_FILESIZE': 524288,
                           'MAX_FILESIZE': 1073741824,
                           'ITEMS_PER_PAGE': 100}
        with open(settings_file, 'w') as _f:
            _f.write(json.dumps(custom_settings))
    return custom_settings


APP_FOLDER = os.path.dirname(os.path.abspath(__file__))  # in fact, this is the abs path of 'src' folder
CUSTOM_SETTINGS_FILE = os.path.join(APP_FOLDER, 'persist', 'conf.json')
CUSTOM_SETTINGS = init_conf(CUSTOM_SETTINGS_FILE)


class BaseConf:
    """Base configuration including settings configurable by user."""
    APP_FOLDER = APP_FOLDER
    CONFIG_FOLDER = APP_FOLDER
    SETTINGS_FILE = CUSTOM_SETTINGS_FILE
    DATABASE = os.environ.get('POSTGRES_DB', 'metaphotor')
    SQLALCHEMY_DATABASE_URI = 'postgresql://%s:%s@postgresql:5432/%s' % (
                              os.environ.get('POSTGRES_USER', 'postgres'),
                              os.environ.get('POSTGRES_PASSWORD', 'password'),
                              DATABASE)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.normpath('app/uploads')  # will be created if does not exist
    DOWNLOAD_FOLDER = 'downloads'  # will be created if does not exist
    ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'mov', 'mp4', 'mpg', 'mpeg', '3gp', 'avi']
    TESTING = False
    # Below will be configurable by user:
    MEDIA_FOLDER = CUSTOM_SETTINGS['MEDIA_FOLDER']  # a folder with photos & videos to be imported
    WATCH_FOLDER = CUSTOM_SETTINGS['WATCH_FOLDER']  # a folder with photos & videos to be imported as increment
    FFMPEG_PATH = CUSTOM_SETTINGS['FFMPEG_PATH']    # an absolute path to FFmpeg executable
    FFPROBE_PATH = CUSTOM_SETTINGS['FFPROBE_PATH']  # an absolute path to FFprobe executable
    MIN_FILESIZE = CUSTOM_SETTINGS['MIN_FILESIZE']  # a number of bytes
    MAX_FILESIZE = CUSTOM_SETTINGS['MAX_FILESIZE']  # a number of bytes
    ITEMS_PER_PAGE = CUSTOM_SETTINGS['ITEMS_PER_PAGE']


class DevConf(BaseConf):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProdConf(BaseConf):
    """Production configuration."""
    DEBUG = False
    SQLALCHEMY_ECHO = False
