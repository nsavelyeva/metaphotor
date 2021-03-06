import json
from datetime import datetime
from flask_sqlalchemy import Pagination
from sqlalchemy import exc
from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey, create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, relationship, backref
from sqlalchemy.ext.declarative import declarative_base
from app import app
from .data import USERS, PLACES


engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], convert_unicode=True)

db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()


def to_dict(data, columns):
    """Convert a model class instance into a dictionary."""
    result = {}
    columns = [col.key if hasattr(col, 'key') else col for col in columns]
    if isinstance(data, list):
        data = data[1:]
        transform = lambda i: {columns[i]: data[i]}
    else:
        transform = lambda i: {columns[i]: getattr(data, columns[i])}
    i = 0
    while i < len(columns):
        try:
            result.update(transform(i))
        except AttributeError:
            return {}
        i += 1
    return result


def get_time_str():
    """Get current date & time as a string in a fixed human-friendly format."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def paginate(query, page, per_page):
    """Create a Pagination instance to be used in HTML templates."""
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    pagination = Pagination(query, page, per_page, query.count(), items)
    return pagination


class MediaFiles(Base):
    __tablename__ = 'mediafiles'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    user_relation = relationship('Users', backref=backref('mediafiles', lazy='dynamic'))
    path = Column(Text(), unique=True)
    duration = Column(Float)
    size = Column(Integer)
    title = Column(String(265))
    description = Column(Text())
    comment = Column(Text())
    tags = Column(String(256))
    coords = Column(String(50))
    location_id = Column(Integer, ForeignKey('locations.id'))
    location_relation = relationship('Locations', backref=backref('mediafiles', lazy='dynamic'))
    year = Column(Integer)
    created = Column(String(30))
    imported = Column(String(30))
    updated = Column(String(30))
    accessed = Column(String(30))
    visits = Column(Integer)

    def __init__(self, user_relation, path, duration, title, description, comment, tags,
                 coords, location_relation, year, created, size):
        """
        An initializer for the database entry object.
        Note: Adding .replace('\x00', '') to string literals to avoid PostgreSQL error:
        "A string literal cannot contain NUL (0x00) characters." - please refer to:
        https://groups.google.com/forum/#!topic/django-developers/D1gvXYCezEc
        https://www.postgresql.org/message-id/200712170734.lBH7YdG9034458%40wwwmaster.postgresql.org
        """
        self.user_id = user_relation
        self.path = path.replace('\x00', '')
        self.duration = duration
        self.size = size
        self.title = title.replace('\x00', '')
        self.description = description.replace('\x00', '')
        self.comment = comment.replace('\x00', '')
        self.tags = tags.replace('\x00', '')
        self.coords = coords.replace('\x00', '')
        self.location_id = location_relation
        self.year = year
        self.created = created.replace('\x00', '')
        self.imported = get_time_str()
        self.updated = ''
        self.accessed = ''
        self.visits = 0

    def __repr__(self):
        return '[Metadata for file #%s]' % self.id

    def __str__(self):
        info = '''MediaFile: %s
\tOwnership: %s
\tTitle: %s
\tDescription: %s
\tTags: %s
\tComment: %s
\tCreated: %s
\tYear: %s
\tGPS: %s
\tLocation id: %s
\tDuration: %s
\tSize: %s
\tImported: %s
\tUpdated: %s
\tAccessed: %s
\tVisits: %s''' % (self.path, self.user_id, self.title, self.description, self.tags, self.comment,
                   self.created, self.year, self.coords, self.location_id, self.duration, self.size,
                   self.imported, self.updated, self.accessed, self.visits)
        return info


class Tags(Base):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    tag = Column(String(20), unique=True)

    def __init__(self, tag):
        self.tag = tag

    def __repr__(self):
        return 'Tag #%s: %s' % (self.id, self.tag)

    def __str__(self):
        return json.dumps(self, indent=4, sort_keys=True)


class Users(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    login = Column(String(20), unique=True)
    password = Column(String(100))

    def __init__(self, login, password):
        self.login = login
        self.password = password

    def __repr__(self):
        return '[User #%s]' % self.id

    def __str__(self):
        return json.dumps(self, indent=4, sort_keys=True)


class Locations(Base):
    __tablename__ = 'locations'

    id = Column(Integer, primary_key=True)
    latitude = Column(Float, unique=True)
    longitude = Column(Float, unique=True)
    city = Column(String(30), unique=True)
    country = Column(String(30))
    code = Column(String(2))

    def __init__(self, latitude, longitude, city, country, code):
        self.city = city
        self.country = country
        self.latitude = latitude
        self.longitude = longitude
        self.code = code.upper()

    def __repr__(self):
        return '[Location #%s]' % self.id

    def __str__(self):
        info = '''Location # %s
\tLatitude: %s
\tLongitude: %s
\tCity: %s
\tCountry: %s
\tCountry code: %s''' % (self.id, self.latitude, self.longitude, self.city, self.country, self.code)
        return info


@app.before_first_request
def startup():
    """Create database and all the tables, insert all predefined data into tables."""
    Base.metadata.create_all(engine)
    # Add all predefined locations, default (unknown) location will have id=0:
    for place in PLACES:
        latitude, longitude, city, country, code = place
        location = Locations(latitude, longitude, city, country, code)
        if place == PLACES[0]:
            location.id = 0
        db_session.add(location)
    # Add all predefined users, default (reserved for public access) user will have id=0:
    for user in USERS:
        login, password = user
        person = Users(login, password)
        if user == USERS[0]:
            person.id = 0
        db_session.add(person)
    # Commit all the above queries:
    try:
        db_session.commit()
    except exc.IntegrityError:
        db_session.rollback()
