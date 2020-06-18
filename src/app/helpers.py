import os
import time
import subprocess
import shutil
import json
import logging
from collections import OrderedDict
from multiprocessing.dummy import Pool as ThreadPool, Value, Lock
from werkzeug.utils import secure_filename
from .models import MediaFiles, get_time_str
from .metamedia import MultiMedia, get_file_ctime, format_timestamp
from . import db_queries
from .data import COUNTRIES


class Data:
    """A class to be used as a form of a return value for supporting functions."""
    def __init__(self, values, errors):
        self.value = values     # could be any structure
        self.errors = errors    # is always a list of strings, empty if everything is successful

    def __str__(self):
        result = {'VALUE': self.value, 'ERRORS': self.errors}
        return json.dumps(result, indent=4, sort_keys=True)


def write_scan_error(msg):
    """
    Append the given message as a new line to the text file 'scan_err.log', which is cleaned before each scan/rescan.
    """
    with open('scan_err.log', 'a') as scan_errors_file:
        scan_errors_file.write(msg + '\n')


def get_subfolders_list(path):
    """
    Discover sub-folders of the given folder recursively.

    :param path: a string containing an absolute or relative path.
    :return: the instance of class Data(),
             where value is the message containing the list of all discovered sub-folders,
             and the errors is always an empty list,
             because cases if the folder doesn't exist or the given path is a file
             are considered normal, and empty string is returned as value.
    """
    info = ''
    for root, folder, files in os.walk(path):
        for subfolder in folder:
            info += '%s\n' % os.path.join(root, subfolder)
    return Data(info, [])


def move_file(old_path, new_path):
    """
    Move the file to the new location (simply by renaming old path into new path),
    non-existing folders mentioned in the new path will be created.

    :param old_path: an absolute path of the file to be moved/renamed.
    :param new_path: an absolute path of the file the existing file to be moved/renamed into
    :return: an instance of class Data() containing a success message as a value & a list of errors,
             (value message will be empty if the list of errors is not empty).
    """
    if not os.path.isfile(old_path):
        return Data('', ['Cannot move "%s" because it does not exist or is not a file.' % old_path])
    if '.' not in new_path.split(os.sep)[-1]:
        return Data('', ['Cannot move "%s": no file extension detected in its path.' % new_path])
    if os.path.isfile(new_path):
        return Data('', ['Cannot move "%s": destination "%s" already exists.'
                         % (old_path, new_path)])
    file_name = new_path.split(os.sep)[-1]
    try:
        os.makedirs(new_path[:-len(file_name) - 1], exist_ok=True)
        shutil.copy2(old_path, new_path)
        shutil.copystat(old_path, new_path)
        os.remove(old_path)
    except (FileNotFoundError, FileExistsError, PermissionError) as err:
        return Data(old_path, ['Cannot move "%s" to "%s" due to: %s.' % (old_path, new_path, err)])
    return Data(new_path, [])


def run_ffmpeg(ffmpeg_path, ffmpeg_opts):
    """
    Run FFMPEG command.

    :param ffmpeg_path: an absolute path to the FFMPEG executable (i.e. 1st part of the command).
    :param ffmpeg_opts: a string containing the rest of the command (i.e. all the command options).
    :return: an instance of class Data(), where value is the stdout of the command and errors is
             the list with one element (stderr) if the command failed
             or an empty list if the command was successful.
    """
    command = '%s %s' % (ffmpeg_path, ffmpeg_opts)
    stdout, stderr = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) \
                               .communicate()
    return Data(stdout, [] if not stderr else [stderr])


def pretty_size(size):
    """Convert integer number of bytes to a string in a human-friendly format."""
    for fmt in ['bytes', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB']:
        if abs(size) < 1024.0:
            return '%3.1f %s' % (size, fmt)
        size /= 1024.0
    return '%.1f %s' % (size, 'Yi')


def get_users_choices():
    """
    Get users information from DB to be used to prepare options for HTML select tag in the forms.

    :return: a list of tuples (user_id, user_login).
    """
    users = [(user.id, user.login) for user in db_queries.get_all_users()]
    return users


def get_locations_choices():
    """
    Get locations information from DB to be used to prepare options for HTML select tag in forms.

    :return: a list of tuples (location_id, 'city, country').
    """
    locations = [(loc.id, '%s, %s' % (loc.country.title(), loc.city.title()))
                 for loc in db_queries.get_all_locations()]
    return locations


def is_allowed_file(file_name, allowed_extensions):
    """
    A function to check the extension of the file upload.

    :param file_name: an absolute path of the media file to analyze its extension.
    :param allowed_extensions: a list of strings representing file extensions in lower case, e.g.:
                               ['jpg', 'jpeg', 'mov', 'mp4'].
    :return: True if file's extension is in the list of allowed extensions, False otherwise.
    """
    is_allowed = False
    if '.' in file_name:
        extension = file_name.rsplit('.', 1)[1].lower()
        is_allowed = extension in allowed_extensions
    return is_allowed


def upload_file(user_id, request, app_config, file_name=None):
    """
    Upload the file to the specified location.
    Note, the file creation year will be the current year.
    If the given location does not start with app.config[MEDIA_FOLDER] or contains hidden sub-folders,
    then the file will be saved in app.config[UPLOAD_FOLDER] inside a sub-folder named as user id.

    :param user_id: an integer number of user id which will be considered as owner (0 for public).
    :param request: an instance of request coming from browser.
    :param app_config: a dictionary containing the application configuration settings (=app.config).
    :param file_name:
    :return: an instance of class Data() where value is the absolute path to the uploaded file.
    """
    data = Data(None, [])
    # Check if the POST request has the file part
    if 'upload' not in request.files:
        data.errors.append('Cannot upload file: no file part.')
    else:
        upload = request.files['upload']
        # If a user does not select file, browser submits an empty part without filename
        if not upload.filename:
            data.errors.append('Cannot upload file: no file selected.')
        elif upload:
            file_allowed = is_allowed_file(upload.filename, app_config['ALLOWED_EXTENSIONS'])
            if file_allowed:
                file_name = file_name or secure_filename(upload.filename)
                folder = request.form.get('folder', '').strip()
                user_folder = folder if folder.startswith(app_config['MEDIA_FOLDER']) \
                                        and '/.' not in folder \
                                        and '..' not in folder \
                                     else os.path.join(app_config['APP_FOLDER'],
                                                       app_config['UPLOAD_FOLDER'],
                                                       str(user_id))
                if not os.path.exists(user_folder):
                    os.makedirs(user_folder, 0o700, exist_ok=True)
                data.value = os.path.join(user_folder, file_name)
                if os.path.isfile(data.value):
                    data.errors.append('Cannot upload file: already exists.')
                else:
                    upload.save(data.value)
                    last_accessed_timestamp = time.time()
                    last_modified_timestamp = int(request.form.get('last_modified')) / 1000.0
                    os.utime(data.value, (last_accessed_timestamp, last_modified_timestamp or last_accessed_timestamp))
            else:
                msg = 'Allowed extensions are %s.' % ', '.join(app_config['ALLOWED_EXTENSIONS'])
                data.errors.append('Cannot upload file: file is not accepted. ' + msg)
    return data


def collect_media_files(parent_folder, app_config, check_db=False):
    """
    Collect absolute paths of media files from the given folder recursively into a list of strings.
    Files having not supported extensions will be skipped.
    Errors occurred during the scan will be saved to scan_err.log file (note: this file is cleaned before each scan).

    :param parent_folder: a folder to scan the files in.
    :param app_config: a dictionary of app settings to use values of allowed extensions, media and watch folders.
    :param check_db: a boolean to perform additional check if the path is already registered in the database
                     (makes sense to use True for incremental scans and False to initial scans and full re-scans).
    :return: a list of strings representing absolute paths of discovered media files.
    """
    all_media_files = []
    declined = ''  # a string of semicolon-separated list of absolute paths of declined files.
    for relative_path, subdirs, files in os.walk(parent_folder):
        sub_folder = os.path.abspath(relative_path)
        for file_name in files:
            path = os.path.join(sub_folder, file_name)
            if file_name[file_name.rfind('.') + 1:].lower() in app_config['ALLOWED_EXTENSIONS']:
                if check_db is True:
                    if db_queries.is_path_registered(path.replace(app_config['WATCH_FOLDER'],
                                                                  app_config['MEDIA_FOLDER'], 1)):
                        declined += '%s;' % path
                    else:
                        all_media_files.append(path)
                else:
                    all_media_files.append(path)
            else:
                declined += '%s;' % path
    with open('scan.json', 'w') as scan_progress_file:
        data = json.dumps({'total': len(all_media_files), 'passed': 0, 'failed': 0, 'declined': declined})
        scan_progress_file.write(data)
    with open('scan_err.log', 'w'):
        pass
    return all_media_files


def parallel_scan(app_config, user_id, media_files):
    """
    Once the app is launched for the first scan (when there is no database) or in order to re-scan,
    analyzing media files will be performed on demand (as authorized user, navigate to /settings and
    click 'Scan Media Files' button).
    To speed-up the scan process, 32 threads max will be used for this task.
    During the scan process files metadata is retrieved from files and is registered in the DB.

    :param app_config: a dictionary containing the application configuration settings (=app.config).
    :param user_id: an integer number of user id which will be considered as owner (0 for public).
    :param media_files: a list of strings - absolute paths of media files to be processed.
    :return: True.
    """
    passed, lock_passed = Value('i', 0), Lock()
    failed, lock_failed = Value('i', 0), Lock()
    args = [(app_config, user_id, path, passed, lock_passed, failed, lock_failed)
            for path in media_files]
    pool = ThreadPool(2)
    pool.starmap(single_scan, args)
    pool.close()
    pool.join()
    return True


def single_scan(app_config, user_id, path, passed, lock_passed, failed, lock_failed):
    """
    Analyze a single media file:
    read EXIF tags from photo files or custom metadata from video files
    and write this information into the database.
    The scan progress (number of total/passed/failed files) is written into 'scan.json' file.

    :param app_config: a dictionary containing the application configuration settings (=app.config).
    :param user_id: an integer number of user id which will be considered as owner (0 for public).
    :param path: an absolute path to the photo or video file.
    :param passed: an integer value - a count of all successfully processed media files.
    :param lock_passed: a Lock() value to stay safe-thread in counting successfully processed files.
    :param failed: an integer value - a count of all processed media files which failed.
    :param lock_failed: a Lock() value to stay safe-thread in counting failed files.

    :return: True if no errors occurred during the scan, otherwise False.
    """
    declined = ''
    if path.startswith(app_config['WATCH_FOLDER']):
        old_path = path
        path = path.replace(app_config['WATCH_FOLDER'], app_config['MEDIA_FOLDER'], 1)
        result = move_file(old_path, path)
        if result.errors:
            write_scan_error('%s failed: cannot move to %s due to %s' % (old_path, path, ';'.join(result.errors)))
            return False
    try:
        data = add_mediafile(user_id, path, app_config)
    except Exception as err:
        msg = '%s failed due to %s' % (path, err)
        write_scan_error(msg)
        data = Data(None, [msg])
    with open('scan.json', 'r+') as scan_progress_file:
        if data.value:
            with lock_passed:
                passed.value += 1
        else:
            with lock_failed:
                failed.value += 1
                declined = path
        content = json.loads(scan_progress_file.read())
        if declined:
            content['declined'] += ';%s' % declined
        content['passed'] = passed.value
        content['failed'] = failed.value
        scan_progress_file.seek(0)
        scan_progress_file.write(json.dumps(content))
        scan_progress_file.truncate()
    return False if data.errors else True


def add_mediafile(user_id, path, app_config):
    """
    From the given path detect a media type (photo or video) and read metadata from the file -
    EXIF tags from photo files or custom metadata from video files, -
    and create an entry in the database containing all available metadata.
    If new tags or locations are detected, they will be added to the database.
    Original GEO coordinates will be stored - i.e. not overridden with the coordinates
    of the city center when location is automatically detected by the coordinates with geopy module.

    .. note :: any allowed non-MP4 video will be converted into MP4 to be displayable in browsers.

    :param user_id: an integer number of user id which will be considered as owner (0 for public).
    :param path: an absolute path to the photo or video file.
    :param app_config: a dictionary containing the application configuration settings (=app.config).
    :return: an instance of Data() class, where
             value is an instance of Photo()/Video() class (or None if adding a media file failed),
             and errors is the list of messages - empty if adding a media file was successful.
    """
    multimedia = MultiMedia.detect(path, app_config,
                                   ffmpeg_path=app_config['FFMPEG_PATH'],
                                   ffprobe_path=app_config['FFPROBE_PATH'])
    # File creation year of the original file
    created = format_timestamp(get_file_ctime(path), '%Y-%m-%d %H:%M:%S')
    # Convert non-MP4 videos into MP4 (tested for '3gp', 'mpg', 'mpeg', 'mov', 'avi' - works well)
    if multimedia.path[multimedia.path.rfind('.') + 1:].lower() not in ['jpg', 'jpeg', 'mp4']:
        metadata = '-metadata copyright="%s" ' % created
        multimedia.convert_to_mp4(' -y -vcodec h264 -acodec aac -strict -2 -b:a 384k %s' % metadata)
    # Add tags if new ones were discovered
    tags = [tag for tag in multimedia.tags.strip().split() if 3 <= len(tag) <= 15]
    for tag in tags:
        msg, style, obj = db_queries.create_tag(tag)
        logging.debug('%s %s %s %s\n' % (get_time_str(), style.upper(), path, msg))
    # Add location if a new one is detected
    msg, style, location = db_queries.create_location(multimedia.gps['city'],
                                                      multimedia.gps['country'],
                                                      multimedia.gps['code'])
    logging.debug('%s %s %s %s\n' % (get_time_str(), style.upper(), path, msg))
    # Add media file with its original coords, does not depend on location coords of the city center
    coords = ','.join(str(item)
                      for item in [multimedia.gps['latitude'], multimedia.gps['longitude']] if item)
    entry = MediaFiles(user_id, multimedia.path, multimedia.duration, multimedia.title,
                       multimedia.description, multimedia.comment, ' '.join(tags), coords,
                       location.id, multimedia.year, multimedia.created, multimedia.size)
    msg, style, obj = db_queries.create_mediafile(user_id, entry)
    logging.debug('%s %s %s %s\n' % (get_time_str(), style.upper(), path, msg))
    return Data(obj, [] if obj else [msg])


def update_settings_file(settings, conf_file_path):
    """
    Settings are loaded from conf.py (which takes them from custom.json) at every launch.
    When settings are changed while app is running (through http://.../settings/update) -
    they are loaded into app.config dictionary.
    To 'remember' them for next launches they are put into custom.json file.
    Hence, to avoid de-synchronization, it is not recommended to edit custom.json manually.

    :param settings: a dictionary containing applications settings (see CUSTOM_SETTINGS in conf.py).
    :param conf_file_path: an absolute or relative path to custom.json file.
    :return: True.
    """
    with open(conf_file_path, 'w') as custom_settings_file:
        custom_settings_file.write(json.dumps(settings))
    return True


def collect_settings(app_config):
    """
    Retrieve current custom settings.

    :param app_config: a dictionary containing the application configuration settings (=app.config).
    :return: an ordered dictionary containing custom settings.
    """
    settings = OrderedDict()
    settings['MEDIA_FOLDER'] = {'value': app_config['MEDIA_FOLDER'],
                                'comment': 'Abs path to local folder containing media files'}
    settings['WATCH_FOLDER'] = {'value': app_config['WATCH_FOLDER'],
                                'comment': 'Abs path to local folder for incremental file ingestion'}
    settings['FFMPEG_PATH'] = {'value': app_config['FFMPEG_PATH'],
                               'comment': 'Abs path to ffmpeg executable'}
    settings['FFPROBE_PATH'] = {'value': app_config['FFPROBE_PATH'],
                                'comment': 'Abs path to ffprobe executable'}
    settings['MIN_FILESIZE'] = {'value': '%s bytes' % app_config['MIN_FILESIZE'],
                                'comment': pretty_size(app_config['MIN_FILESIZE'])}
    settings['MAX_FILESIZE'] = {'value': '%s bytes' % app_config['MAX_FILESIZE'],
                                'comment': pretty_size(app_config['MAX_FILESIZE'])}
    settings['ITEMS_PER_PAGE'] = {'value': app_config['ITEMS_PER_PAGE'], 'comment': ''}
    return settings


def get_media_per_countries_counts(user_id, mediafiles):
    """
    Prepare data to be displayed on highmaps: a number of shapshots made in the country, geo points.

    :param user_id: a user id, needed to collect owned items.
    :param mediafiles: a list of dicts or query.all()-like results of mediafiles collected from DB.

    :return: a tuple of jsonified data (counts, points) prepared to be displayed on highmaps.
    """
    counts = []  # a list of dicts, each contains a number of vidoes/photos made in the country
    points = []  # GeoPoints, list of dicts: {'name': <city>, 'lat': <latitude>, 'lon': <longitude>}
    for mediafile in mediafiles:
        if 'coords' not in mediafile:
            mediafile = mediafile._asdict()
        coords = mediafile['coords'].split(',')
        params = {'search': '', 'view_mode': 'list', 'tags_matching': 'lazy', 'year': 'any',
                  'ownership_public': 'on', 'ownership_private': 'on',
                  'location': mediafile['location_id']}  # always collect public and owned files
        for country in COUNTRIES:
            if mediafile['code'].upper() == country['code']:
                count = len(db_queries.get_all_mediafiles(user_id, params).all())
                counts.append({'name': country['name'], 'value': count, 'code': mediafile['code']})
                points.append({'name': mediafile['city'].title(),
                               'lat': coords[0], 'lon': coords[-1]})
    points = {'name': 'Points', 'type': 'mappoint', 'data': points}
    return json.dumps(counts), json.dumps(points)
