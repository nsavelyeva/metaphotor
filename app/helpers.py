import os
import sys
import time
import json
import logging
from collections import OrderedDict
from multiprocessing.dummy import Pool as ThreadPool, Value, Lock
from werkzeug.utils import secure_filename
from . import db_queries
from .models import MediaFiles, get_time_str
from .metamedia import Photo


logging.basicConfig(level=logging.DEBUG, filename='posters.log', filemode='w',
                    format='%(asctime)-20s %(name)-12s %(levelname)-10s %(message)s',
                    datefmt='%Y-%m-%d %H:%M')


def pretty_size(size):
    """Convert integer number of bytes to human-friendly format."""
    for fmt in ['bytes', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB']:
        if abs(size) < 1024.0:
            return "%3.1f %s" % (size, fmt)
        size /= 1024.0
    return "%.1f %s" % (size, 'Yi')


def get_users_choices():
    users = [(user.id, user.login) for user in db_queries.get_all_users()]
    return users


def get_locations_choices():
    locations = [(loc.id, "%s, %s" % (loc.city.title(), loc.country.title()))
                 for loc in db_queries.get_all_locations()]
    return locations


def find_media_files(parent_folder, allowed_extensions):
    all_media_files = []
    for relative_path, subdirs, files in os.walk(parent_folder):
        subfolder = os.path.abspath(relative_path)
        media_files = [os.path.join(subfolder, fname) for fname in files
                       if fname[fname.rfind(".") + 1:].lower() in allowed_extensions]
        all_media_files.extend(media_files)
    return all_media_files


def parallel_scan(user_id, media_files):
    with open("scan.json", "w+") as _f:
        _f.write(json.dumps({"total": len(media_files), "passed": 0, "failed": 0}))
    total = len(media_files)
    passed, lock_passed = Value('i', 0), Lock()
    failed, lock_failed = Value('i', 0), Lock()
    args = [(user_id, path, total, passed, lock_passed, failed, lock_failed)
            for path in media_files]
    pool = ThreadPool(32)
    pool.starmap(single_scan, args)
    pool.close()
    pool.join()


def single_scan(user_id, path, total, passed, lock_passed, failed, lock_failed):
    photo = Photo(path)
    # Add tags if needed
    tags = [tag for tag in photo.tags.strip().split() if 3 <= len(tag) <= 15]
    for tag in tags:
        msg, style, obj = db_queries.create_tag(tag)
        logging.debug("%s %s %s %s\n" % (get_time_str(), style.upper(), path, msg))
    # Add location if needed
    msg, style, location = db_queries.create_location(photo.gps["city"],
                                                      photo.gps["country"])
    logging.debug("%s %s %s %s\n" % (get_time_str(), style.upper(), path, msg))
    coords = ",".join(str(item) for item in [photo.gps["latitude"], photo.gps["longitude"]] if item)
    # Add mediafile
    entry = MediaFiles(user_id, photo.path, photo.duration, photo.title, photo.description,
                       photo.comment, " ".join(tags), coords, location.id if location else 0,
                       photo.year, photo.created, photo.size)
    msg, style, obj = db_queries.create_mediafile(user_id, entry)
    logging.debug("%s %s %s %s\n" % (get_time_str(), style.upper(), path, msg))
    if style == "success":
        with lock_passed:
            passed.value += 1
    else:
        with lock_failed:
            failed.value += 1
    with open("scan.json", "w") as _f:
        _f.write(json.dumps({"total": total, "passed": passed.value, "failed": failed.value}))


def update_settings_file(settings, conf_file_path):
    """Settings are loaded from conf.py (which takes them from custom.json) at every launch.
    When settings are changed while app is running (through http://.../settings/update) -
    they are loaded into app.config dictionary.
    To "remember" them for next launches they are put into custom.json file.
    Hence, to avoid desynchronization, it is not recommended to edit custom.json manually.
    """
    with open(conf_file_path, "w+") as _f:
        _f.write(json.dumps(settings))
    return True


def collect_settings(app_conf):
    settings = OrderedDict()
    settings["MEDIA_FOLDER"] = {"value": app_conf["MEDIA_FOLDER"],
                                "comment": "Abs path to local folder"}
    settings["FFMPEG_PATH"] = {"value": app_conf["FFMPEG_PATH"],
                               "comment": "Abs path to ffmpeg executable"}
    settings["MIN_FILESIZE"] = {"value": "%s bytes" % app_conf["MIN_FILESIZE"],
                                "comment": pretty_size(app_conf["MIN_FILESIZE"])}
    settings["MAX_FILESIZE"] = {"value": "%s bytes" % app_conf["MAX_FILESIZE"],
                                "comment": pretty_size(app_conf["MAX_FILESIZE"])}
    settings["ITEMS_PER_PAGE"] = {"value": app_conf["ITEMS_PER_PAGE"], "comment": ""}
    return settings




################

class Data(object):
    def __init__(self, values, errors):
        self.value = values   # could be any structure
        self.errors = errors  # is always a list of strings, empty if everything is OK

    def __str__(self):
        result = {"VALUE": self.value, "ERRORS": self.errors}
        return json.dumps(result, indent=4, sort_keys=True)


def allowed_file(file_name, allowed_extensions):
    """A function to check the extension of the file upload."""
    is_allowed = False
    if "." in file_name:
        extension = file_name.rsplit(".", 1)[1].lower()
        is_allowed = extension in allowed_extensions    
    return is_allowed


def upload_file(request, app_conf, file_name=None):
    # check if the POST request has the file part
    data = Data(None, [])
    if "upload" not in request.files:
        data.errors.append(gmsg(4101))
    else:
        upload = request.files["upload"]
        # if a user does not select file, browser submits an empty part without filename
        if not upload.filename:
            data.errors.append(gmsg(4111))
        elif upload:
            file_allowed = allowed_file(upload.filename, app_conf["ALLOWED_EXTENSIONS"])
            if file_allowed:
                file_name = file_name if file_name else secure_filename(upload.filename)
                data.value = os.path.join(app_conf["UPLOAD_FOLDER"], file_name)
                upload.save(data.value)
            else:
                msg = ". Allowed extensions are %s" % ", ".join(app_conf["ALLOWED_EXTENSIONS"])
                data.errors.append(gmsg(4091, msg))
    return data
