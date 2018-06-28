from sqlalchemy import func, or_, and_, exc, desc, inspect
from sqlalchemy.orm import class_mapper, load_only, Load
from .models import MediaFiles, Locations, Users, Tags, db_session, to_dict, get_time_str
from . import geo_tools


## Mediafiles-related queries:
def find_mediafiles(fields, entry):
    #query = MediaFiles.query.join(Locations, MediaFiles.location_id == Locations.id)
    query = db_session.query(MediaFiles, Locations) \
                      .join(Locations) \
                      .filter(or_(MediaFiles.title.contains(entry),
                                  MediaFiles.description.contains(entry),
                                  MediaFiles.tags.contains(entry),
                                  MediaFiles.comment.contains(entry))
                              ) \
                      .add_columns(*fields)
    return query


def get_all_mediafiles(fields=None):
    fields = fields or [MediaFiles.id, MediaFiles.user_id, MediaFiles.path, MediaFiles.duration, MediaFiles.size,
              MediaFiles.title, MediaFiles.description, MediaFiles.comment, MediaFiles.tags,
              MediaFiles.coords, MediaFiles.location_id, MediaFiles.year, MediaFiles.created,
              MediaFiles.imported, MediaFiles.updated, MediaFiles.accessed, MediaFiles.visits]
    query = MediaFiles.query \
                      .join(Locations, MediaFiles.location_id == Locations.id) \
                      .join(Users, MediaFiles.user_id == Users.id) \
                      .add_columns(*fields)
    #query = db_session.query(MediaFiles, Locations).join(Locations)
    return query


def find_mediafiles_by_location(location_id, fields):
    query = MediaFiles.query \
                      .join(Locations, MediaFiles.location_id == Locations.id) \
                      .filter(Locations.id == location_id) \
                      .add_columns(*fields)
    return query

# +
def get_mediafile_details(mediafile_id, fields):
    query = MediaFiles.query \
                      .join(Locations, MediaFiles.location_id == Locations.id) \
                      .join(Users, MediaFiles.user_id == Users.id) \
                      .filter(MediaFiles.id == mediafile_id) \
                      .add_columns(*fields)
    data = to_dict(query.first(), fields)
    values = {'accessed': get_time_str(), 'visits': data['visits'] + 1}
    update_mediafile_values(mediafile_id, values)
    return data


def get_mediafile(mediafile_id):
    query = db_session.query(MediaFiles).filter_by(id=mediafile_id)
    data = query.first()
    return data

#+
def create_mediafile(user_id, media_object):
    user = db_session.query(Users).filter(Users.id == user_id).first()
    try:
        media_file = MediaFiles(user.id, media_object.path, media_object.duration,
                                media_object.title, media_object.description, media_object.comment,
                                media_object.tags, media_object.coords, media_object.location_id,
                                media_object.year, media_object.created, media_object.size)
        db_session.add(media_file)
        db_session.commit()
    except exc.IntegrityError as err:
        db_session.rollback()
        return 'Media file "%s" has not been added - already exists: %s.' % (media_object.path, err), \
               'warning', None
    return 'Media file "%s" has been added.' % media_object.path, \
           'success', media_file

#+
def remove_previously_scanned():
    data = db_session.query(MediaFiles).filter_by(user_id=0).delete()
    db_session.commit()
    return data


def update_mediafile_values(mediafiles_id, values):
    db_session.query(MediaFiles).filter_by(id=mediafiles_id).update(values)
    db_session.commit()
    return 'Updated Media File # %s.' % mediafiles_id, 'success'


def update_mediafile(request_form, mediafiles_id):
    values = {'user_id': request_form.get('user_id'),
              'path': request_form.get('path'),
              'duration': request_form.get('duration'),
              #'size': request_form.get('size'),
              'title': request_form.get('title'),
              'description': request_form.get('description'),
              'comment': request_form.get('comment'),
              'tags': request_form.get('tags'),
              'coords': request_form.get('coords'),
              'location_id': request_form.get('location_id'),
              'year': request_form.get('year'),
              'created': request_form.get('created'),
              #'imported': request_form.get('imported'),
              'updated': get_time_str(),
              #'accessed': request_form.get('accessed'),
              #'visits': request_form.get('visits'),
             }
    return update_mediafile_values(mediafiles_id, values)   # tuple of success message and style


def remove_mediafile(mediafiles_id):
    media_file = MediaFiles.query.get(mediafiles_id)
    db_session.delete(media_file)
    db_session.commit()
    return 'Removed Media File # %s from database and local storage.' % mediafiles_id, 'success'

## Users-related queries:
def get_all_users(*fields):
    fields = fields or [Users.id, Users.login]
    data = Users.query.add_columns(*fields)
    return data

#+
def get_user(user_id, as_dict=False):
    query = db_session.query(Users).filter_by(id=user_id)
    data = query.first()
    if as_dict:
        columns = Users.__table__.columns.keys()
        data = to_dict(data, columns)
    return data

#
def create_user(login, password):
    try:
        user = Users(login, password)
        db_session.add(user)
        db_session.commit()
    except exc.IntegrityError as err:
        db_session.rollback()
        return 'User "%s" has not been added - already exists.' % login, 'info', \
               db_session.query(Users).filter_by(login=login).first()
    return 'User "%s" has been added.' % login, 'success', user

#
def update_user(request_form, user_id):
    values = {'login': request_form.get('login').strip(),
              'password': request_form.get('password').strip()}
    db_session.query(Users).filter_by(id=user_id).update(values)
    db_session.commit()
    return 'Updated user #%s: %s.' % (user_id, values['login']), 'success'

#
def remove_user(user_id):
    user = Users.query.get(user_id)
    db_session.delete(user)
    db_session.commit()
    return 'User #%s (%s) has been deleted.' % (user_id, user.login), 'success'


## Tags-related queries:
def get_all_tags(fields):
    data = Tags.query.add_columns(*fields)
    return data

#+
def get_tag(tag_id, as_dict=False):
    query = db_session.query(Tags).filter_by(id=tag_id)
    data = query.first()
    if as_dict:
        columns = Tags.__table__.columns.keys()
        data = to_dict(data, columns)
    return data

#
def create_tag(name):
    name = name.strip().lower()
    try:
        tag = Tags(name)
        db_session.add(tag)
        db_session.commit()
    except exc.IntegrityError as err:
        db_session.rollback()
        return 'Tag "%s" has not been added - already exists.' % name, 'info', \
               db_session.query(Tags).filter_by(tag=name).first()
    return 'Tag "%s" has been added.' % name, 'success', tag

#
def update_tag(request_form, tag_id):
    values = {'tag': request_form.get('tag').lower()}
    db_session.query(Tags).filter_by(id=tag_id).update(values)
    db_session.commit()
    return 'Updated tag #%s: %s.' % (tag_id, values['tag']), 'success'

#
def remove_tag(tag_id):
    tag = Tags.query.get(tag_id)
    db_session.delete(tag)
    db_session.commit()
    return 'Tag #%s (%s) has been deleted.' % (tag_id, tag.tag), 'success'


## Locations-related queries:
#+
def find_location_by_attributes(city, country):
    query = db_session.query(Locations) \
                      .filter(and_(Locations.city == city.strip().lower(),
                                   Locations.country == country.strip().lower())
                              )
    data = query.first()
    return data

#+
def get_all_locations(*fields):
    fields = fields or [Locations.id, Locations.city, Locations.country,
                        Locations.latitude, Locations.longitude]
    query = Locations.query.add_columns(*fields)
    return query

#+
def get_location(location_id, as_dict=False):
    query = db_session.query(Locations).filter_by(id=location_id)
    data = query.first()
    if as_dict:
        columns = Locations.__table__.columns.keys()
        data = to_dict(data, columns)
    return data

#+
def create_location(city, country, latitude=None, longitude=None):
    city = city.strip().lower()
    country = country.strip().lower()
    if city:
        try:
            if not (isinstance(latitude, float) and isinstance(longitude, float)):
                latitude, longitude = geo_tools.get_coords(city)
            location = Locations(latitude, longitude, city, country)
            db_session.add(location)
            db_session.commit()
        except exc.IntegrityError as err:
            db_session.rollback()
            return 'Location "%s, %s" has not been added - already exists.' % (city, country), \
               'info', find_location_by_attributes(city, country)
    else:
        return 'Location "%s, %s" has not been added - bad values.' % (city, country), \
               'info', None
    return 'Location "%s, %s (%s, %s)" has been added.' % (city, country, latitude, longitude), \
           'success', location

#+
def update_location(request_form, location_id):
    values = {'latitude': request_form.get('latitude'),
              'longitude': request_form.get('longitude'),
              'city': request_form.get('city'),
              'country': request_form.get('country')}
    db_session.query(Locations).filter_by(id=location_id).update(values)
    db_session.commit()
    return 'Updated location #%s: %s, %s.' % (location_id,
                                              values['city'].title(), values['country'].title()), \
           'success'

#+
def remove_location(location_id):
    if location_id == 0:
        return 'Removal of Location #0 is forbidden.', 'warning'
    location = Locations.query.get(location_id)
    affected_count = db_session.query(MediaFiles).filter_by(location_id=location_id).count()
    if affected_count:
        msg = 'Cannot remove Location #%s (%s, %s) because it has %s mediafile(s) using it.' % \
              (location.id, location.city.title(), location.country.title(), affected_count)
        return msg , 'warning'
    db_session.delete(location)
    db_session.commit()
    return 'Location #%s (%s, %s) has been deleted.' % (location_id, location.city.title(),
                                                        location.country.title()), \
           'success'
