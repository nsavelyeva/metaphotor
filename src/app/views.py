import os
import json
from functools import wraps
from flask import session, render_template, redirect, abort, url_for, \
    request, jsonify, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from app import app
from .forms import MediaFilesForm, LocationsForm, TagsForm, SettingsForm, \
    UsersForm, LoginForm, UploadForm
from .models import MediaFiles, Locations, Users, Tags, db_session, paginate, get_time_str
from .metamedia import MultiMedia
from . import db_queries
from . import geo_tools
from . import helpers


def login_required(route_function):
    """
    A function to be used as a decorator for routing functions which require user's authentication.

    :param route_function: a function which requires user authentication.
    :return: a decorated function.
    """
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        if session.get('logged_in'):
            return route_function(*args, **kwargs)
        return redirect(url_for('login', next=request.url))
    return decorated_function


@app.route('/_scan')
def scan():
    """
    On AJAX request - scan the media folder app.config['MEDIA_FOLDER']
    and register all discovered media files with public access.
    Only files with allowed extensions (see app.config['ALLOWED_EXTENSIONS']) will be processed.

    Note! Entries of previously scanned files (in fact, entries about all public files - user_id=0)
          will be removed from database. Other tables (tags, locations, users) will be left intact.

    :return: a jsonified response containing the total number of discovered files.
    """
    all_media_files = helpers.collect_media_files(app.config['MEDIA_FOLDER'], app.config, False)
    db_queries.remove_previously_scanned(app.config['MEDIA_FOLDER'])
    public_user_id = 0  # just to emphasize that all scanned files will be available for any user
    helpers.parallel_scan(app.config, public_user_id, all_media_files)
    return jsonify(total=len(all_media_files))


@app.route('/_scan_increment')
def scan_increment():
    """
    On AJAX request - scan the watch folder app.config['WATCH_FOLDER']
    and register all discovered media files with public access.
    Only files with allowed extensions (see app.config['ALLOWED_EXTENSIONS']) will be processed.

    Note! Entries of previously scanned files will not be affected.
          If a file already exists in media folder, no overwrites will happen,
          and the increment file will remain in watch folder.

    :return: a jsonified response containing the total number of discovered files.
    """
    all_media_files = helpers.collect_media_files(app.config['WATCH_FOLDER'], app.config, True)
    public_user_id = 0  # just to emphasize that all scanned files will be available for any user
    helpers.parallel_scan(app.config, public_user_id, all_media_files)
    return jsonify(total=len(all_media_files))


@app.route('/_scan_status')
def scan_status():
    """
    On AJAX request - read scan statistics from 'scan.json' file:
    - numbers of total/passed/failed files;
    - a string of semicolon-separated absolute paths of declined files.

    :return: a jsonified response of scan statistics.
    """
    with open('scan.json', 'r+') as scan_progress_file:
        data = json.loads(scan_progress_file.read())
    return jsonify(total=data['total'],
                   failed=data['failed'],
                   passed=data['passed'],
                   declined=data['declined'])


@app.route('/_hint')
def hint():
    """
    On AJAX request - return the list of all non-hidden (i.e. not prefixed with a dot) sub-folders of the given folder.
    This is used to pop up hints when uploading a new media file,
    so moving a new file into desired location becomes more human-friendly.
    In fact, all the path hints will start with the value specified in app.config['MEDIA_FOLDER'].

    Note: the folders not prefixed with app.config['MEDIA_FOLDER']) will result in empty list of hints.
          It is allowed to specify not yet existing sub-folders.

    :return: a list of strings - names of all non-hidden sub-folders of the folder provided in the request.
    """
    hints = []
    folder = request.args.get('folder').strip()
    folder = folder[:folder.rfind('/')]
    if folder.startswith(app.config['MEDIA_FOLDER']):
        hints = [{'hint': os.path.join(folder, item)} for item in os.listdir(folder)
                 if not item.startswith('.') and os.path.isdir(os.path.join(folder, item))]
    return jsonify(hints)


@app.route('/_get_city_coords')
def get_city_coords():
    """
    On AJAX request - for the given city, detect country and GEO coordinates of a city center.

    :return: a jsonified response containing GEO details (latitude, longitude, city, country -
             all values will be empty strings if GEO position detection failed),
             and an error message (empty string if GEO position detection was successful).
    """
    latitude = longitude = city = country = code = error = ''
    form_city = request.args.get('city').strip().lower()
    if form_city:
        latitude, longitude = geo_tools.get_coords(form_city)
        city, country, code = geo_tools.get_address(latitude, longitude)
    if not country:
        error = 'Could not get Geo coordinates for city "%s".' % form_city
        city = form_city
    return jsonify(latitude=latitude, longitude=longitude, country=country, city=city, code=code,
                   error=error)


@app.route('/_load_coords')
def load_coords():
    form_city = request.args.get('city').strip().lower()  # a city to change to
    form_coords = request.args.get('coords').strip()      # current coords
    if ',' in form_coords:  # if there are current coords
        form_latitude, form_longitude = [item.strip() for item in form_coords.split(',')]
        city = geo_tools.get_address(form_latitude, form_longitude)[0]  # a city of current coords
        city = city.strip().lower() if city else ''  # just to be safe if current coords are invalid
        if form_city == city:
            coords = form_coords  # keep current coords if current city is same as to be changed
        else:
            latitude, longitude = geo_tools.get_coords(form_city)  # get coords of city center
            coords = ','.join([str(latitude), str(longitude)]) if latitude and longitude else ''
    else:  # if current coords are not specified, get coords of city [to be changed to] center
        latitude, longitude = geo_tools.get_coords(form_city)
        coords = ','.join([str(latitude), str(longitude)]) if latitude and longitude else ''
    return jsonify(coords=coords)


@app.route('/_update_visits_accessed')
def update_visits_accessed():
    """
    On AJAX request - increment visits and set current date & time as accessed value.

    :return: a jsonified response containing an error message.
    """
    mediafile_id = int(request.args.get('mediafile_id').strip())
    mediafile = db_queries.get_mediafile(mediafile_id, as_dict=True)
    values = {'accessed': get_time_str(), 'visits': mediafile['visits'] + 1}
    msg, style = db_queries.update_mediafile_values(mediafile_id, values)
    error = '' if style == 'success' else msg
    return jsonify(error=error)


@app.route('/load_mediafile/<path:abs_path>')
def download_file(abs_path):
    """
    Send the contents of a file to the client -
    this is used to display photo or video as a static file on the web pages.

    :param abs_path: an absolute path to the file.
    """
    abs_path = abs_path.replace('/', os.sep).replace('opt/metaphotor/app/', '')
    return send_file(abs_path)


@app.route('/home')
@app.route('/about')
@app.route('/')
def home():
    """Route to the page containing the description of MetaPhotor app."""
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Route to the login page.
    If a user is already authenticated, nothing will happen, just a flash message will be displayed.
    A warning message will be flashed if a user fails to sign in and the login form will be shown.
    Once a user successfully logs in, a session containing user info (id, name) will be created and
    a successful message will be flashed on the web page.
    """
    if session.get('logged_in'):
        flash('You are already signed in. Do you want to <a href="/logout">sign out</a>?',
              'success')
        return list_mediafiles()
    form = LoginForm(request.form)
    if request.method == 'POST':
        user = db_queries.find_user_by_login(request.form.get('login', ''))
        if user and check_password_hash(user.password, request.form.get('password', '')):
            session['logged_in'] = True
            session['user_name'] = user.login
            session['user_id'] = user.id
            return redirect(url_for('list_mediafiles'))
        else:
            flash('Login failed: username or password is incorrect.', 'warning')
    return render_template('form.html', session=session, form=form, submit_name='Sign In')


@app.route("/logout")
def logout():
    """
    Destroy the session: flash a message and set user id to 0 which means 'anonymous' -
    i.e. only video and photo files which have user_id=0 will be available for viewing only,
    and for changing app settings, uploading new files, [re-]scan of media files
    a user will be redirected to fill in the login form.
    """
    session['logged_in'] = False
    session['user_name'] = ''
    session['user_id'] = 0
    flash('Signed out.', 'success')
    return redirect(url_for('login'))


@app.route('/statistics')
def statistics():
    """Collect various statistics to be displayed using highcharts."""
    data_by_type = db_queries.stats_data_by_type()
    data_by_year_type, data_by_type_year = db_queries.stats_data_by_year()
    data_by_city, data_by_country = db_queries.stats_data_by_location()
    return render_template('statistics.html', session=session,
                           data_by_type=json.dumps(data_by_type),
                           data_by_year_type=json.dumps(data_by_year_type),
                           data_by_type_year=json.dumps(data_by_type_year),
                           data_by_city=json.dumps(data_by_city),
                           data_by_country=json.dumps(data_by_country))


def __top_stats(top_field_name, user_id=None, limit=10, sort_desc=True, randomize=False, info=None):
    """A supplementary function to collect entries for top-lists."""
    # Current active user or public or any forced user if specified:
    user_id = session.get('user_id', 0) if user_id is None else user_id
    model_field = getattr(MediaFiles, top_field_name)
    fields = [MediaFiles.id, MediaFiles.year, MediaFiles.path, model_field, MediaFiles.coords,
              MediaFiles.location_id, Locations.city, Locations.country, Locations.code]
    locations = db_queries.get_all_locations([Locations.id, Locations.city, Locations.country])
    query = db_queries.top_mediafiles(user_id, fields, model_field, sort_desc, limit, randomize)
    data, points = helpers.get_media_per_countries_counts(user_id, query.all())
    return render_template('top.html', session=session, rows=paginate(query, 1, limit).items,
                           locations=locations, points=points, data=data, info=info,
                           top_field=top_field_name, fields=['year', 'path'] + [top_field_name])


@login_required
@app.route('/statistics/favourites')
def stats_favourites():
    """Route to a view page of 10 most visited snapshots among owned by current authorized user."""
    info = {'header': 'Favourites Top-10',
            'text': 'Below is the list of 10 most visited snapshots among owned by you.'}
    return __top_stats('visits', session.get('user_id', None), info=info)


@app.route('/statistics/popular')
def stats_popular():
    """Route to a view page of 10 most visited snapshots among public ones."""
    info = {'header': 'Popular Top-10',
            'text': 'Below is the list of 10 most visited snapshots among public ones.'}
    return __top_stats('visits', 0, info=info)


@app.route('/statistics/new')
def stats_new():
    """Route to a view page of 10 recently created public snapshots."""
    info = {'header': 'Brand New Top-10',
            'text': 'Below is the list of 10 snapshots recently taken.'}
    return __top_stats('created', 0, info=info)


@app.route('/statistics/fresh')
def stats_fresh():
    """Route to a view page of 10 recently created public snapshots."""
    info = {'header': 'Fresh Top-10',
            'text': 'Below is the list of 10 public snapshots with metadata recently updated.'}
    return __top_stats('updated', 0, info=info)


@app.route('/statistics/latest')
def stats_imported():
    """Route to a view page of 10 public snapshots recently imported into MetaPhotor."""
    info = {'header': 'Latest Top-10',
            'text': 'Below is the list of 10 public snapshots recently imported to MetaPhotor.'}
    return __top_stats('imported', 0, info=info)


@app.route('/statistics/hot')
def stats_lastviewed():
    """Route to a view page of 10 recently accessed public snapshots."""
    info = {'header': 'Hot Top-10',
            'text': 'Below is the list of 10 public snapshots recently accessed.'}
    return __top_stats('accessed', 0, info=info)


@app.route('/statistics/mix')
def stats_mix():
    """Route to a view page of 100 public snapshots selected randomly."""
    info = {'header': 'Mix-100',
            'text': 'Below is the list of 100 public snapshots selected randomly.'}
    return __top_stats('id', 0, 100, randomize=True, info=info)


@app.route('/statistics/map')
def geo_map():
    """Route to the web page to display snapshots counts and geo points on the world map."""
    fields = [MediaFiles.coords, MediaFiles.location_id,
              Locations.city, Locations.country, Locations.code]
    params = {'search': '', 'tags_matching': 'lazy', 'year': 'any', 'location': 'any'}
    query = db_queries.get_all_mediafiles(-1, params, fields)
    data, points = helpers.get_media_per_countries_counts(session.get('user_id', 0), query.all())
    return render_template('map.html', session=session, points=points, data=data)


@app.route('/mediafiles/list', defaults={'page': 1}, methods=['GET'])
@app.route('/mediafiles/list/<int:page>', methods=['GET'])
@app.route('/albums', defaults={'page': 1}, methods=['GET'])
@app.route('/albums/', defaults={'page': 1}, methods=['GET'])
@app.route('/albums/<int:page>', methods=['GET'])
def list_mediafiles(page):
    """
    Route to the web page containing a search form to find media files by different attributes.
    Search results will be paginated, a message about the number of found items will be flashed,
    and one out of three viewing templates will be selected: list (default), tiles or gallery.

    :param page: a page number for pagination, default is 1 (pages start from 1).
    """
    fields = [MediaFiles.id, MediaFiles.year, MediaFiles.path, MediaFiles.tags, MediaFiles.coords,
              MediaFiles.location_id, Locations.city, Locations.country, Locations.code]
    locations = db_queries.get_all_locations([Locations.id, Locations.city, Locations.country])
    params = request.args or {'search': '', 'tags_matching': 'lazy', 'view_mode': 'list',
                              'ownership_public': 'on', 'year': 'any', 'location': 'any'}
    query = db_queries.get_all_mediafiles(session.get('user_id', 0), params, fields)
    pagination = paginate(query, page, app.config['ITEMS_PER_PAGE'])
    flash('Found items: %s.' % pagination.total, 'info')
    data, points = helpers.get_media_per_countries_counts(session.get('user_id', 0), query.all())
    template = 'media%s.html' % params['view_mode'] \
        if params.get('view_mode') in ['list', 'tiles', 'gallery'] else 'medialist.html'
    return render_template(template, rows=pagination.items, pagination=pagination,
                           session=session, args=request.args, locations=locations,
                           params='&'.join('%s=%s' % (key, value) for key, value in params.items()),
                           points=points, data=data,
                           table='mediafiles', fields=[field.__dict__['key'] for field in fields])


@app.route('/mediafiles/view/<int:mediafile_id>', methods=['GET'])
def view_mediafile(mediafile_id):
    """
    For the given media file, display all the information stored about it in the database.
    File size of the media file will be displayed both in bytes and human-friendly format.

    :param mediafile_id: an id of the media file in the database.
    """
    fields = [MediaFiles.id, Users.login, MediaFiles.path, MediaFiles.duration, MediaFiles.size,
              MediaFiles.title, MediaFiles.description, MediaFiles.comment, MediaFiles.tags,
              MediaFiles.coords, Locations.city, Locations.country, Locations.code, MediaFiles.year,
              MediaFiles.created, MediaFiles.imported, MediaFiles.updated, MediaFiles.accessed,
              MediaFiles.visits, MediaFiles.location_id]
    media_file = db_queries.get_mediafile_details(mediafile_id, fields)
    if not media_file:
        abort(404, 'Media file #%s is missing (was deleted or never existed).' % mediafile_id)
    data, points = helpers.get_media_per_countries_counts(session.get('user_id', 0), [media_file])
    return render_template('item.html', session=session, table='mediafiles', fields=media_file,
                           item=media_file, points=points, data=data,
                           size=helpers.pretty_size(media_file['size']))


@app.route('/mediafiles/inspect/<int:mediafile_id>', methods=['GET'])
def inspect_mediafile(mediafile_id):
    """
    Compare metadata stored in the DB with actual metadata written into the media file.

    :param mediafile_id: an id of the media file in the database.
    """
    fields = [MediaFiles.id, Users.login, MediaFiles.path, MediaFiles.duration, MediaFiles.size,
              MediaFiles.title, MediaFiles.description, MediaFiles.comment, MediaFiles.tags,
              MediaFiles.coords, Locations.city, MediaFiles.year, MediaFiles.created,
              MediaFiles.imported, MediaFiles.updated, MediaFiles.accessed, MediaFiles.visits]
    item_db = db_queries.get_mediafile_details(mediafile_id, fields)
    if not item_db:
        abort(404, 'Media file #%s is missing (was deleted or never existed).' % mediafile_id)
    item_file = MultiMedia.detect(item_db['path'], app.config,
                                  ffmpeg_path=app.config['FFMPEG_PATH'],
                                  ffprobe_path=app.config['FFPROBE_PATH'])
    setattr(item_file, 'city', item_file.gps['city'])
    setattr(item_file, 'coords', '%s,%s' % (item_file.gps['latitude'], item_file.gps['longitude'])
                                 if item_file.gps['latitude'] else '')
    return render_template('inspect.html', session=session,
                           item_db=item_db, item_file=item_file.__dict__,
                           size=helpers.pretty_size(item_db['size']), fields=item_db)


@app.route('/mediafiles/delete/', methods=['POST'])
@login_required
def delete_mediafile():
    """
    Having an id of the media file, remove a database entry about it, and remove the file from disk!
    Message(s) about the operation result will be flashed.
    """
    if request.form and 'item' in request.form:
        media_file = db_queries.get_mediafile(int(request.form.get('item', type=int)))
        msg, style = db_queries.remove_mediafile(media_file.id)
        flash(msg, style)
        try:
            os.remove(media_file.path)
            flash('Removed media file "%s" from disk.' % media_file.path, 'success')
        except OSError as err:
            flash('Cannot remove media file "%s" due to %s.' % (media_file.path, err), 'warning')
    return redirect(url_for('list_mediafiles'))


@app.route('/mediafiles/add', methods=['GET', 'POST'])
@login_required
def upload_media_file():
    """
    Upload a photo/video file - available for authenticated users only.
    Once the file is uploaded, the entry about it gets created in the database,
    and the user will be redirected to the edit form to fill in metadata details.
    At that 'edit' stage the user can:
     - change file ownership (by modifying user_id)
     - move the file to a different folder by changing its path, nonexisting folders will be created
    """
    form = UploadForm(request.form)
    if request.method == 'POST' and form.validate():
        user_id = session.get('user_id', 0)  # in fact, user_id is never 0 (we use @login_required)
        upload_result = helpers.upload_file(user_id, request, app.config)
        if not upload_result.value:
            for error in upload_result.errors:
                flash(error, 'danger')
            return redirect(url_for('upload_media_file'))
        add_result = helpers.add_mediafile(user_id, upload_result.value, app.config)
        errors = upload_result.errors + add_result.errors
        if errors:
            for error in errors:
                flash(error, 'danger')
            if not upload_result.errors and os.path.isfile(upload_result.value):
                os.remove(upload_result.value)
        else:
            flash('File "%s" has been uploaded and saved in the database.' % upload_result.value,
                  'success')
            return redirect(url_for('edit_mediafile', mediafile_id=add_result.value.id))
    info = helpers.get_subfolders_list(app.config['MEDIA_FOLDER']).value
    return render_template('upload.html', session=session, form=form, info=info,
                           submit_name='Upload')


@app.route('/mediafiles/edit/<int:mediafile_id>', methods=['GET', 'POST'])
@login_required
def edit_mediafile(mediafile_id):
    """
    Having mediafile_id, update database entry about the media file and update media file if needed:
    - if file path is changed, the file will be moved to new location
      (if successful, next is allowed to proceed with);
    - update metadata in the database (if successful, next is allowed to proceed with);
    - add new tags if any to the database;
    - finally, inject metadata into the file on disk
      (using FFMPEG executable for videos or Python module pyexif to edit EXIF tags for photos).
    """
    media = db_queries.get_mediafile(mediafile_id)
    if not media:
        abort(404, 'Media file #%s is missing (was deleted or never existed).' % mediafile_id)
    form = MediaFilesForm(obj=media) if request.method == 'GET' else MediaFilesForm(request.form)
    form.user_id.choices = helpers.get_users_choices()
    form.location_id.choices = helpers.get_locations_choices()
    if request.method == 'POST' and form.validate():
        new_path = request.form.get('path', '').strip()
        if media.path.strip().lower() != new_path.lower():  # need to try moving the file
            result = helpers.move_file(media.path, new_path)
            for error in result.errors:
                flash(error, 'danger')
            if not result.errors:
                flash('File has been moved to "%s".' % result.value, 'success')
            else:  # Override to the old path if file copying failed
                form.path.data = media.path
        file_metadata_changed = media.description != request.form.get('description', '').strip() \
                                or media.title != request.form.get('title', '').strip() \
                                or media.tags != request.form.get('tags', '').strip() \
                                or media.comment != request.form.get('comment', '').strip() \
                                or media.location_id != request.form.get('location_id') \
                                or media.coords != request.form.get('coords', '').strip()
        # Get ready to write updated metadata into database for the given media file:
        # get GPS info, update coords value:
        gps = None
        location_id = request.form.get('location_id')
        if location_id:  # need to keep city and country from location but original coords from file
            coords = request.form.get('coords', '').split(',')  # returns [''] if coords == ''
            location = db_queries.get_location(location_id)
            gps = {'city': location.city, 'country': location.country, 'code': location.code,
                   'latitude': coords[0], 'longitude': coords[-1]}
        # Now update metadata for the media file in the database
        # (at this stage the file on disk is left intact):
        msg, style = db_queries.update_mediafile(request.form, mediafile_id)
        flash(msg, style)
        if style == 'success':
            # Once metadata for media file is updated, we need to add tags
            # (if there are some new ones) to Tags table:
            tags = [tag for tag in request.form.get('tags').strip().split() if 3 <= len(tag) <= 15]
            for tag in tags:
                db_queries.create_tag(tag)
            # Finally, if metadata was changed then inject updated metadata into media file on disk:
            if file_metadata_changed:
                multimedia = MultiMedia.detect(request.form.get('path', '').strip(),
                                               app.config,
                                               ffmpeg_path=app.config['FFMPEG_PATH'],
                                               ffprobe_path=app.config['FFPROBE_PATH'])
                if multimedia.write_metadata(request.form.get('title'),
                                             request.form.get('description'),
                                             request.form.get('tags'),
                                             request.form.get('comment'),
                                             gps,
                                             request.form.get('created')):
                    flash('Updated metadata injection into %s was completed.' % new_path, 'success')
                else:
                    flash('Failed to inject updated metadata into %s.' % new_path, 'danger')
            else:
                flash('No need to re-inject file metadata into "%s".' % new_path, 'info')
            return redirect(url_for('list_mediafiles'))
    else:
        form.path.data = media.path
    return render_template('form.html', session=session, form=form, submit_name='Save')


@app.route('/locations/list', defaults={'page': 1}, methods=['GET'])
@app.route('/locations/list/<int:page>', methods=['GET'])
def list_locations(page):
    """
    Retrieve information about all locations stored in the DB and display them as a paginated list.

    :param page: a page number for pagination, default is 1 (pages start from 1).
    """
    fields = [Locations.id, Locations.latitude, Locations.longitude,
              Locations.city, Locations.country, Locations.code]
    query = db_queries.get_all_locations(fields)
    pagination = paginate(query, page, app.config['ITEMS_PER_PAGE'])
    flash('Found locations: %s.' % pagination.total, 'info')
    return render_template('list.html', rows=pagination.items, pagination=pagination,
                           session=session, table='locations',
                           fields=[field.__dict__['key'] for field in fields])


@app.route('/locations/view/<int:location_id>', methods=['GET'])
def view_location(location_id):
    """
    Having a location id, route to a page to display the location details stored in the database.
    If successful, redirect to a page containing a paginated list of all locations stored in the DB.
    """
    location = db_queries.get_location(location_id, as_dict=True)
    if not location:
        abort(404, 'Location #%s is missing (was deleted or never existed).' % location_id)
    return render_template('item.html', session=session, item=location)


@app.route('/locations/edit/<int:location_id>', methods=['GET', 'POST'])
@login_required
def edit_location(location_id):
    """
    Having a location id, route to a web page to edit the location entry in the database.
    If successful, redirect to a page containing a paginated list of all locations stored in the DB.
    """
    location = db_queries.get_location(location_id)
    if not location:
        abort(404, 'Location #%s is missing (was deleted or never existed).' % location_id)
    form = LocationsForm(obj=location)
    if request.method == 'POST' and form.validate():
        msg, style = db_queries.update_location(request.form, location_id)
        flash(msg, style)
        if style == 'success':
            return redirect(url_for('list_locations'))
    return render_template('form.html', session=session, form=form, submit_name='Save')


@app.route('/locations/delete/', methods=['POST'])
@login_required
def delete_location():
    """
    Having a location id, remove the location entry from the database.
    If successful, redirect to a page containing a paginated list of all locations stored in the DB.
    """
    if request.form and 'item' in request.form:
        location_id = request.form.get('item', type=int)
        msg, style = db_queries.remove_location(location_id)
        flash(msg, style)
    return redirect(url_for('list_locations'))


@app.route('/locations/add', methods=['GET', 'POST'])
@login_required
def add_location():
    """
    Route to the form to create a location: once a city name is entered into the form field,
    GEO coordinates and country name will be automatically loaded in the other form fields.
    If everything is successful, an entry about the location will be created in the DB, and the user
    will be redirected to a page containing a paginated list of all locations stored in the DB.
    """
    form = LocationsForm(request.form)
    if request.method == 'POST' and form.validate():
        msg, style, location = db_queries.create_location(form.city.data, form.country.data,
                                                          form.code.data,
                                                          form.latitude.data, form.longitude.data)
        flash(msg, style)
        if style == 'success':
            return redirect(url_for('list_locations'))
    return render_template('form.html', session=session, form=form, submit_name='Save')


@app.route('/tags/list', defaults={'page': 1}, methods=['GET'])
@app.route('/tags/list/<int:page>', methods=['GET'])
def list_tags(page):
    """
    Retrieve information about all tags stored in the DB and display them as a paginated list.

    :param page: a page number for pagination, default is 1 (pages start from 1).
    """
    fields = [Tags.id, Tags.tag]
    query = db_queries.get_all_tags(fields)
    pagination = paginate(query, page, app.config['ITEMS_PER_PAGE'])
    flash('Found tags: %s.' % pagination.total, 'info')
    return render_template('list.html', rows=pagination.items, pagination=pagination,
                           session=session, table='tags',
                           fields=[field.__dict__['key'] for field in fields])


@app.route('/tags/view/<int:tag_id>', methods=['GET'])
def view_tag(tag_id):
    """Having a tag id, route to the page to view the tag details."""
    tag = db_queries.get_tag(tag_id, as_dict=True)
    if not tag:
        abort(404, 'Tag #%s is missing (was deleted or never existed).' % tag_id)
    return render_template('item.html', session=session, item=tag)


@app.route('/tags/edit/<int:tag_id>', methods=['GET', 'POST'])
@login_required
def edit_tag(tag_id):
    """
    Having a tag id, route to the form to edit a database entry about the existing tag.
    If successful, redirect to a web page containing a paginated list of all tags stored in the DB.
    """
    tag = db_queries.get_tag(tag_id)
    if not tag:
        abort(404, 'Tag #%s is missing (was deleted or never existed).' % tag_id)
    form = TagsForm(obj=tag)
    if request.method == 'POST' and form.validate():
        msg, style = db_queries.update_tag(request.form, tag_id)
        flash(msg, style)
        if style == 'success':
            return redirect(url_for('list_tags'))
    return render_template('form.html', session=session, form=form, submit_name='Save')


@app.route('/tags/delete/', methods=['POST'])
@login_required
def delete_tag():
    """
    Having a tag id, remove the tag entry from the database.
    If successful, redirect to a web page containing a paginated list of all tags stored in the DB.
    """
    if request.form and 'item' in request.form:
        tag_id = request.form.get('item', type=int)
        msg, style = db_queries.remove_tag(tag_id)
        flash(msg, style)
    return redirect(url_for('list_tags'))


@app.route('/tags/add', methods=['GET', 'POST'])
@login_required
def add_tag():
    """
    Route to the form to create a new tag in the database.
    If successful, redirect to a web page containing a paginated list of all tags stored in the DB.
    """
    form = TagsForm(request.form)
    if request.method == 'POST' and form.validate():
        msg, style, tag = db_queries.create_tag(form.tag.data)
        flash(msg, style)
        if style == 'success':
            return redirect(url_for('list_tags'))
    return render_template('form.html', session=session, form=form, submit_name='Save')


@app.route('/users/list', defaults={'page': 1}, methods=['GET'])
@app.route('/users/list/<int:page>', methods=['GET'])
def list_users(page):
    """
    Retrieve information about all users stored in the DB and display them as a paginated list.

    :param page: a page number for pagination, default is 1 (pages start from 1).
    """
    fields = [Users.id, Users.login]
    query = db_queries.get_all_users(fields)
    pagination = paginate(query, page, app.config['ITEMS_PER_PAGE'])
    flash('Found users: %s.' % pagination.total, 'info')
    return render_template('list.html', rows=pagination.items, pagination=pagination,
                           session=session, table='users',
                           fields=[field.__dict__['key'] for field in fields])


@app.route('/users/view/<int:user_id>', methods=['GET'])
@login_required
def view_user(user_id):
    """
    Having a user id, route to the web page to view user details.
    For now, this is available for all authenticated users. TODO: for admins only.
    Password hashes will be masked as asterisks.
    """
    user = db_queries.get_user(user_id, as_dict=True)
    if not user:
        abort(404, 'User #%s is missing (was deleted or never existed).' % user_id)
    return render_template('item.html', session=session, item=user)


@app.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    """
    Having a user id, edit a database entry about the user and flash a message about the result.
    For now, this is available for all authenticated users. TODO: for admins only.
    If a password is changed, new hash will be calculated and it will update old hash in the DB.
    If a blank password is specified, a message will be flashed and old hash will remain in the DB.
    If everything is successful, redirect to the web page containing a paginated users list.
    Note: the user with user_id=0 is not allowed for changes since it represents all anonymous users
          and is responsible for access to media files with user_id=0 for public viewing.
    """
    user = db_queries.get_user(user_id)
    if not user:
        abort(404, 'User #%s is missing (was deleted or never existed).' % user_id)
    form = UsersForm(obj=user)
    if request.method == 'POST' and form.validate():
        password_hash = None
        new_password = request.form.get('password', '').strip()
        if not new_password:
            flash('The password is not changed because blank passwords are not allowed.', 'warning')
        elif form.password.data != new_password:  # if password was changed, store its hash in DB
            password_hash = generate_password_hash(new_password, 'sha256')
        msg, style = db_queries.update_user(request.form, user_id, password_hash)
        flash(msg, style)
        if style == 'success':
            return redirect(url_for('list_users'))
    return render_template('form.html', session=session, form=form, submit_name='Save')


@app.route('/users/delete/', methods=['POST'])
@login_required
def delete_user():
    """
    Having a user id, delete a user from the database and flash a message about the result.
    For now, this is available for all authenticated users. TODO: for admins only.
    Note: the user with user_id=0 is not allowed for removal since it represents all anonymous users
          and is responsible for access to media files with user_id=0 for public viewing.
    """
    if request.form and 'item' in request.form:
        user_id = request.form.get('item', type=int)
        msg, style = db_queries.remove_user(user_id)
        flash(msg, style)
    return redirect(url_for('list_users'))


@app.route('/users/add', methods=['GET', 'POST'])
@login_required
def add_user():
    """
    Route to the form to add a user into the DB (for now, available for all authenticated users).
    Password hashes will be stored in the database instead of clear-text passwords.
    If successful, redirect to the paginated list of all users stored in the database;
    otherwise - a user will be prompted to fill the form again.
    """
    form = UsersForm(request.form)
    if request.method == 'POST' and form.validate():
        password_hash = generate_password_hash(form.password.data.strip(), 'sha256')
        msg, style, user = db_queries.create_user(form.login.data.strip(), password_hash)
        flash(msg, style)
        if style == 'success':
            return redirect(url_for('list_users'))
    return render_template('form.html', session=session, form=form, submit_name='Save')


@app.route('/settings/update', methods=['GET', 'POST'])
@login_required
def settings_update():
    """
    Route to the page to change values of customizable application settings stored in custom.json.
    If validation of changed settings fails, user will be prompted to fill in the form again, and
    the form values will be loaded from app.config.
    Values in app.config will be updated only if custom.json gets successfully updated.
    """
    form = SettingsForm(request.form)
    if request.method == 'POST' and form.validate():
        settings = {'MEDIA_FOLDER': request.form.get('media_folder'),
                    'WATCH_FOLDER': request.form.get('watch_folder'),
                    'FFMPEG_PATH': request.form.get('ffmpeg_path'),
                    'FFPROBE_PATH': request.form.get('ffprobe_path'),
                    'MIN_FILESIZE': int(request.form.get('min_filesize')),
                    'MAX_FILESIZE': int(request.form.get('max_filesize')),
                    'ITEMS_PER_PAGE': int(request.form.get('items_per_page'))}
        if helpers.update_settings_file(settings, app.config['SETTINGS_FILE']):
            app.config.update(settings)  # reload config only after successful file update
            flash('Settings have been updated', 'success')
        else:
            flash('Could not save settings', 'danger')
        return render_template('settings.html',
                               session=session, settings=helpers.collect_settings(app.config))
    form.media_folder.data = app.config['MEDIA_FOLDER']
    form.watch_folder.data = app.config['WATCH_FOLDER']
    form.ffmpeg_path.data = app.config['FFMPEG_PATH']
    form.ffprobe_path.data = app.config['FFPROBE_PATH']
    form.min_filesize.data = app.config['MIN_FILESIZE']
    form.max_filesize.data = app.config['MAX_FILESIZE']
    form.items_per_page.data = app.config['ITEMS_PER_PAGE']
    return render_template('form.html', session=session, form=form, submit_name='Apply')


@app.route('/settings/restore', methods=['GET', 'POST'])
@login_required
def settings_restore():
    """Route to the page to restore default values of customizable application settings."""
    default_settings = {'MEDIA_FOLDER': '/opt/metaphotor/app/media',
                        'WATCH_FOLDER': '/opt/metaphotor/app/watch',
                        'FFMPEG_PATH': '/usr/bin/ffmpeg',
                        'FFPROBE_PATH': '/usr/bin/ffprobe',
                        'MIN_FILESIZE': 524288, 'MAX_FILESIZE': 1073741824, 'ITEMS_PER_PAGE': 100}
    if helpers.update_settings_file(default_settings, app.config['SETTINGS_FILE']):
        app.config.update(default_settings)
        flash('Loaded default settings', 'success')
    else:
        flash('Could not restore settings', 'danger')
    actual_settings = helpers.collect_settings(app.config)
    return render_template('settings.html', session=session, settings=actual_settings)


@app.route('/settings', methods=['GET'])
@app.route('/settings/view', methods=['GET'])
def settings_view():
    """Route to the page for viewing the current custom settings."""
    settings = helpers.collect_settings(app.config)
    return render_template('settings.html', session=session, settings=settings)


@app.errorhandler(404)
def page_not_found(error):
    """Route to the page which handles '404 Not Found' errors."""
    return render_template('error.html', session=session, code=404, error=error), 404


@app.errorhandler(500)
def internal_server_error(error):
    """Route to the page which handles '500 Internal Server Error' errors."""
    return render_template('error.html', session=session, code=500, error=error), 500


@app.teardown_appcontext
def shutdown_session(exception=None):
    """Remove DB session when application exits."""
    db_session.remove()
