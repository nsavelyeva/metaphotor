import os
import re
import logging
from sqlalchemy import or_, and_, exc, func
from .models import MediaFiles, Locations, Users, Tags, db_session, to_dict, get_time_str
from . import geo_tools


def remove_previously_scanned(path):
    """Remove DB entries of all media files prefixed with the given path."""
    query = db_session.query(MediaFiles) \
        .filter(MediaFiles.path.like(f'{path}%'))
    query.delete(synchronize_session='fetch')
    db_session.commit()
    return query.count()


def is_path_registered(path):
    """Verify if the given path already exists in the database and return a corresponding boolean."""
    result = db_session.query(MediaFiles).filter_by(path=path).all()
    return True if result else False


def stats_data_by_type():
    """Collect entries from database and organize them into a structure acceptable by highcharts."""
    photos = db_session.query(MediaFiles.size).filter(MediaFiles.duration == 0)
    videos = db_session.query(MediaFiles.size).filter(MediaFiles.duration > 0)
    result = [{'name': 'Photos', 'color': '#76BCEB',
               'data': [photos.with_entities(func.sum(MediaFiles.size)).all()[0][0],
                        photos.count()]},
              {'name': 'Videos', 'color': '#397DAA',
               'data': [videos.with_entities(func.sum(MediaFiles.size)).all()[0][0],
                        videos.count()]}]
    return result


def stats_data_by_year():
    """
    Collect entries from database and organize them into a structure acceptable by highcharts.
    Note: this method will work properly if there is at least 1 photo and 1 video file.
    """
    videos = db_session.query(MediaFiles.year, func.count(MediaFiles.year)) \
                       .filter(MediaFiles.duration > 0) \
                       .group_by(MediaFiles.year) \
                       .all()
    photos = db_session.query(MediaFiles.year, func.count(MediaFiles.year)) \
                       .filter(MediaFiles.duration == 0) \
                       .group_by(MediaFiles.year) \
                       .all()
    years = sorted(list(set([item[0] for item in videos + photos])), reverse=True)
    videos_by_year = {}
    photos_by_year = {}
    data_by_type_year = []
    for year in years:
        for item in videos:
            if year == item[0]:
                videos_by_year.update({year: item[1]})
            elif year not in videos_by_year:
                videos_by_year.update({year: 0})
        for item in photos:
            if year == item[0]:
                photos_by_year.update({year: item[1]})
            elif year not in photos_by_year:
                photos_by_year.update({year: 0})
        data_by_type_year.append({'name': year,
                                  'data': [photos_by_year[year], videos_by_year[year]]})
    data_by_year_type = {'years': years,
                         'values': [{'name': 'Photos', 'color': '#76BCEB',
                                     'data': [count for year, count in photos_by_year.items()]},
                                    {'name': 'Videos', 'color': '#397DAA',
                                     'data': [count for year, count in videos_by_year.items()]}
                                    ]}
    return data_by_year_type, data_by_type_year


def stats_data_by_location():
    """Collect entries from database and organize them into a structure acceptable by highcharts."""
    by_city = db_session.query(Locations.city, func.count(MediaFiles.id)) \
                        .outerjoin(MediaFiles, MediaFiles.location_id == Locations.id) \
                        .group_by(Locations.city) \
                        .all()
    by_country = db_session.query(Locations.country, func.count(MediaFiles.id)) \
                           .outerjoin(MediaFiles, MediaFiles.location_id == Locations.id) \
                           .group_by(Locations.country) \
                           .all()
    data_by_city = [{'name': item[0].title(), 'y': item[1]} for item in by_city]
    data_by_country = [{'name': item[0].title(), 'y': item[1]} for item in by_country]
    return data_by_city, data_by_country


def top_mediafiles(user_id, fields, sort_by, sort_desc=True, limit=10, randomize=False):
    """Construct a query to collect entries for various top-lists."""
    query = MediaFiles.query \
        .join(Locations, MediaFiles.location_id == Locations.id) \
        .join(Users, MediaFiles.user_id == Users.id) \
        .filter(MediaFiles.user_id == int(user_id))
    if randomize:
        query = query.order_by(func.random())
    else:
        query = query.order_by(sort_by.desc() if sort_desc else sort_by.asc())
    query = query.limit(limit).add_columns(*fields)
    logging.debug('Query executed: %s' % query)
    return query


def get_all_mediafiles(user_id, params=None, fields=None):
    """Construct a query to perform a sophisticated search for media files entries in the DB."""
    fields = fields or [MediaFiles.id, MediaFiles.user_id, MediaFiles.path, MediaFiles.duration,
                        MediaFiles.size, MediaFiles.title, MediaFiles.comment, MediaFiles.tags,
                        MediaFiles.description, MediaFiles.coords, MediaFiles.location_id,
                        MediaFiles.year, MediaFiles.created, MediaFiles.imported,
                        MediaFiles.updated, MediaFiles.accessed, MediaFiles.visits]
    query = MediaFiles.query \
                      .outerjoin(Locations, MediaFiles.location_id == Locations.id) \
                      .outerjoin(Users, MediaFiles.user_id == Users.id)

    year = params.get('year', 'any')
    if year != 'any' and re.match('[1-2]{1}[0-9]{3}', year) or year == '0':
        query = query.filter(MediaFiles.year == year)

    location = params.get('location', 'any')
    if location != 'any':
        query = query.filter(MediaFiles.location_id == location)

    if user_id != -1:  # user_id = -1 will not apply filtering on ownership (used for statistics)
        public = params.get('ownership_public')
        private = params.get('ownership_private')
        if private or public:
            ownership = []
            if public:
                ownership.append(MediaFiles.user_id == 0)
            if private:
                ownership.append(MediaFiles.user_id == int(user_id))
            query = query.filter(or_(*ownership))
        else:  # If none of Public/Private selected, then result must be empty
            query = query.filter(MediaFiles.user_id == -1)

    entry = params.get('search', '').strip()
    matching = params.get('tags_matching')
    if entry:
        other_matches = []
        if params.get('search_in_path'):
            other_matches.append(MediaFiles.path.contains(entry))
        if params.get('search_in_title'):
            other_matches.append(MediaFiles.title.contains(entry))
        if params.get('search_in_description'):
            other_matches.append(MediaFiles.description.contains(entry))
        if params.get('search_in_comment'):
            other_matches.append(MediaFiles.comment.contains(entry))
        query = query.filter(or_(*other_matches))
        # Note: tags filtering is applied if no other terms are selected
        if params.get('search_in_tags') and not other_matches:
            tag_matches = []
            for tag in entry.split():
                tag_matches.append(MediaFiles.tags.contains(tag))
            if matching == 'strict':
                query = query.filter(and_(*tag_matches))
            else:
                query = query.filter(or_(*tag_matches))
    query = query.add_columns(*fields).order_by(func.random())
    logging.debug('Query executed: %s' % query)
    return query


def get_all_tags(fields=None):
    """Construct a query to retrieve given fields of all entries from table 'tags'."""
    fields = fields or [Tags.id, Tags.tag]
    query = Tags.query.order_by(Tags.tag.asc()).add_columns(*fields)
    logging.debug('Query executed: %s' % query)
    return query


def get_all_users(fields=None):
    """Construct a query to retrieve given fields of all entries from table 'users'."""
    fields = fields or [Users.id, Users.login]
    query = Users.query.add_columns(*fields)
    logging.debug('Query executed: %s' % query)
    return query


def get_all_locations(fields=None):
    """Construct a query to retrieve given fields of all entries from table 'locations'."""
    fields = fields or [Locations.id, Locations.city, Locations.country,
                        Locations.latitude, Locations.longitude]
    query = Locations.query.order_by(Locations.country.asc(), Locations.city.asc()) \
                           .add_columns(*fields)
    logging.debug('Query executed: %s' % query)
    return query


def find_user_by_login(login, as_dict=False):
    """Retrieve user data from DB by user's login."""
    query = db_session.query(Users).filter_by(login=login)
    logging.debug('Query executed: %s' % query)
    data = query.first()
    if as_dict:
        columns = Users.__table__.columns.keys()
        data = to_dict(query, columns)
    return data


def find_location_by_attributes(city, country):
    """Retrieve location data by city and country."""
    query = db_session.query(Locations) \
                      .filter(and_(Locations.city == city.strip().title(),
                                   Locations.country == country.strip().title())
                              )
    logging.debug('Query executed: %s' % query)
    data = query.first()
    return data


def get_mediafile_details(mediafile_id, fields):
    """
    Retrieve mediafile data by mediafile id - only given fields will be collected.
    Additionally, values of 'accessed' and 'visits' fields will be updated.
    """
    query = MediaFiles.query \
                      .join(Locations, MediaFiles.location_id == Locations.id) \
                      .join(Users, MediaFiles.user_id == Users.id) \
                      .filter(MediaFiles.id == mediafile_id) \
                      .add_columns(*fields)
    logging.debug('Query executed: %s' % query)
    data = to_dict(query.first(), fields)
    values = {'accessed': get_time_str(), 'visits': data['visits'] + 1 if 'visits' in data else 0}
    if values['visits']:
        update_mediafile_values(mediafile_id, values)
    return data


def get_mediafile(mediafile_id, as_dict=False):
    """Retrieve mediafile data by mediafile id - all fields will be collected."""
    query = db_session.query(MediaFiles).filter_by(id=mediafile_id)
    logging.debug('Query executed: %s' % query)
    data = query.first()
    if as_dict:
        columns = MediaFiles.__table__.columns.keys()
        data = to_dict(data, columns)
    return data


def get_tag(tag_id, as_dict=False):
    """Retrieve tag data by tag id - all fields will be collected."""
    query = db_session.query(Tags).filter_by(id=tag_id)
    logging.debug('Query executed: %s' % query)
    data = query.first()
    if as_dict:
        columns = Tags.__table__.columns.keys()
        data = to_dict(data, columns)
    return data


def get_user(user_id, as_dict=False):
    """Retrieve user data by user id - all fields will be collected."""
    query = db_session.query(Users).filter_by(id=user_id)
    logging.debug('Query executed: %s' % query)
    data = query.first()
    if as_dict:
        columns = Users.__table__.columns.keys()
        data = to_dict(data, columns)
    return data


def get_location(location_id, as_dict=False):
    """Retrieve location data by location id - all fields will be collected."""
    query = db_session.query(Locations).filter_by(id=location_id)
    logging.debug('Query executed: %s' % query)
    data = query.first()
    if as_dict:
        columns = Locations.__table__.columns.keys()
        data = to_dict(data, columns)
    return data


def create_mediafile(user_id, media_object):
    """Create an entry in 'mediafiles' table."""
    media_file = MediaFiles(user_id or 0, media_object.path, media_object.duration,
                            media_object.title, media_object.description, media_object.comment,
                            media_object.tags, media_object.coords, media_object.location_id or 0,
                            media_object.year or 0, media_object.created, media_object.size)
    try:
        db_session.add(media_file)
        db_session.commit()
    except exc.IntegrityError as err:
        db_session.rollback()
        return 'Cannot add Media File "%s" - already exists: %s.' % (media_object.path, err), \
               'warning', None
    except Exception as err:
        db_session.rollback()
        return 'Cannot add Media File "%s" due to: %s.' % (media_object.path, err), \
               'warning', None
    return 'Media File "%s" has been added.' % media_object.path, 'success', media_file


def create_tag(name):
    """Create an entry in 'tags' table."""
    name = name.strip().lower()
    tag = Tags(name)
    try:
        db_session.add(tag)
        db_session.commit()
    except exc.IntegrityError as err:
        db_session.rollback()
        return 'Tag "%s" has not been added - already exists: %s.' % (name, err), 'warning', None
    return 'Tag "%s" has been added.' % name, 'success', tag


def create_user(login, password):
    """Create an entry in 'users' table."""
    user = Users(login, password)
    try:
        db_session.add(user)
        db_session.commit()
    except exc.IntegrityError as err:
        db_session.rollback()
        return 'User "%s" has not been added - already exists: %s.' % (login, err), 'warning', None
    return 'User "%s" has been added.' % login, 'success', user


def create_location(city, country, code, latitude=None, longitude=None):
    """Create an entry in 'locations' table."""
    city = city.strip().lower() if city else ''
    country = country.strip().lower() if country else ''
    code = code.strip().upper() if code else ''
    if city:
        try:
            if not (isinstance(latitude, float) and isinstance(longitude, float)):
                latitude, longitude = geo_tools.get_coords(city)
            location = Locations(latitude, longitude, city, country, code)
            db_session.add(location)
            db_session.commit()
        except exc.IntegrityError as err:
            db_session.rollback()
            location = find_location_by_attributes(city, country)
            return 'Location "%s, %s" has not been added - already exists: %s.' \
                   % (city, country, err), 'warning', location
    else:
        return 'Location "%s, %s" has not been added - bad values.' \
               % (city, country), 'warning', None
    return 'Location "%s, %s [%s] (%s, %s)" has been added.' \
           % (city, country, code, latitude, longitude), 'success', location


def update_mediafile_values(mediafile_id, values):
    """Update only given values for the entry in 'mediafiles' table."""
    db_session.query(MediaFiles).filter_by(id=mediafile_id).update(values)
    db_session.commit()
    return 'Updated Media File #%s - <a href="/mediafiles/edit/%s">edit again</a>?' \
           % (mediafile_id, mediafile_id), 'success'


def update_mediafile(request_form, mediafile_id):
    """Update an entry in 'mediafiles' table."""
    values = {'user_id': request_form.get('user_id'),
              'path': request_form.get('path'),
              'duration': request_form.get('duration'),
              'size': os.path.getsize(request_form.get('path')),
              'title': request_form.get('title'),
              'description': request_form.get('description'),
              'comment': request_form.get('comment'),
              'tags': request_form.get('tags'),
              'coords': request_form.get('coords'),
              'location_id': request_form.get('location_id'),
              'year': request_form.get('year'),
              'created': request_form.get('created'),
              'updated': get_time_str()}
    return update_mediafile_values(mediafile_id, values)   # tuple of success message and style


def update_tag(request_form, tag_id):
    """Update an entry in 'tags' table."""
    values = {'tag': request_form.get('tag').lower()}
    db_session.query(Tags).filter_by(id=tag_id).update(values)
    db_session.commit()
    return 'Updated tag #%s: %s.' % (tag_id, values['tag']), 'success'


def update_user(request_form, user_id, password_hash=None):
    """Update an entry in 'users' table."""
    values = {'login': request_form.get('login').strip(),
              'password': password_hash if password_hash else request_form.get('password').strip()}
    db_session.query(Users).filter_by(id=user_id).update(values)
    db_session.commit()
    return 'Updated user #%s: %s.' % (user_id, values['login']), 'success'


def update_location(request_form, location_id):
    """Update an entry in 'locations' table."""
    values = {'latitude': request_form.get('latitude'), 'longitude': request_form.get('longitude'),
              'city': request_form.get('city'), 'country': request_form.get('country')}
    db_session.query(Locations).filter_by(id=location_id).update(values)
    db_session.commit()
    return 'Updated location #%s: %s, %s.' \
           % (location_id, values['city'].title(), values['country'].title()), 'success'


def remove_mediafile(mediafiles_id):
    """Remove an entry from 'mediafiles' table."""
    mediafile = MediaFiles.query.get(mediafiles_id)
    db_session.delete(mediafile)
    db_session.commit()
    return 'Removed MediaFile #%s "%s" from database.' % (mediafiles_id, mediafile.path), 'success'


def remove_tag(tag_id):
    """Remove an entry from 'tags' table."""
    tag = Tags.query.get(tag_id)
    db_session.delete(tag)
    db_session.commit()
    return 'Tag #%s (%s) has been deleted.' % (tag_id, tag.tag), 'success'


def remove_user(user_id):
    """Remove an entry from 'users' table."""
    user = Users.query.get(user_id)
    if user_id in [0, 1]:
        return 'Removal of default User #%s (%s) is forbidden.' % (user_id, user.login), 'warning'
    db_session.delete(user)
    db_session.commit()
    return 'User #%s (%s) has been deleted.' % (user_id, user.login), 'success'


def remove_location(location_id):
    """Remove an entry from 'locations' table (if there are no media files linked to it)."""
    location = Locations.query.get(location_id)
    if location_id == 0:
        msg = 'Removal of default Location #0 (city: "%s", country: "%s") is forbidden.' % \
              (location.city.title(), location.country.title())
        return msg, 'warning'
    affected_count = db_session.query(MediaFiles).filter_by(location_id=location_id).count()
    if affected_count:
        msg = 'Cannot remove Location #%s (%s, %s) because it has %s mediafile(s) using it.' % \
              (location.id, location.city.title(), location.country.title(), affected_count)
        return msg, 'warning'
    db_session.delete(location)
    db_session.commit()
    return 'Location #%s (%s, %s) has been deleted.' \
           % (location_id, location.city.title(), location.country.title()), 'success'
