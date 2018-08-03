# TODO: add default locations
import json
from datetime import datetime
from flask_sqlalchemy import Pagination
from sqlalchemy import exc
from app import app
from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, scoped_session, relationship, backref
from sqlalchemy.ext.declarative import declarative_base


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
        result.update(transform(i))
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
    path = Column(Text(1024), unique=True)
    duration = Column(Integer)
    size = Column(Integer)
    title = Column(String(265))
    description = Column(Text(1024))
    comment = Column(Text(1024))
    tags = Column(String(256))
    coords = Column(String(27))
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
        self.user_id = user_relation
        self.path = path
        self.duration = duration
        self.size = size
        self.title = title
        self.description = description
        self.comment = comment
        self.tags = tags
        self.coords = coords
        self.location_id = location_relation
        self.year = year
        self.created = created
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
    password = Column(String(20))

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


@event.listens_for(Engine, 'connect')
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Support multiple requests causing database lock (see https://www.sqlite.org/faq.html#q5)."""
    cursor = dbapi_connection.cursor()
    cursor.execute('PRAGMA busy_timeout=10000')
    cursor.close()


@app.before_first_request
def startup():
    """Create database and all the tables, insert all predefined data into tables."""
    Base.metadata.create_all(engine)
    # Add all predefined locations, default (unknown) location will have id=0:
    places = [(0, 0, 'unknown', 'n/a', ''),
              (53.87303611111111, 27.65790833333333, 'minsk', 'belarus', 'by')]
    for place in places:
        latitude, longitude, city, country, code = place
        location = Locations(latitude, longitude, city, country, code)
        if place == places[0]:
            location.id = 0
        db_session.add(location)
    # Add all predefined users, default (reserved for public access) user will have id=0:
    users = [
      ('public', ''),
      ('admin', 'sha256$nF1Y8wmz$db14a63bb3a2a728ca80b2e952901d3cfbcbd89bfc47c0be3eb1a66908ec6f5c')
    ]
    for user in users:
        login, password = user
        person = Users(login, password)
        if user == users[0]:
            person.id = 0
        db_session.add(person)
    # Commit all the above queries:
    try:
        db_session.commit()
    except exc.IntegrityError:
        db_session.rollback()
