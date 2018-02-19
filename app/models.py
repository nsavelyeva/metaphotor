import json
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy, Pagination
from sqlalchemy import func, or_, exc, desc
from app import app
from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey, create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, relationship, backref
from sqlalchemy.ext.declarative import declarative_base
engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"], convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()



#db = SQLAlchemy(app)


def to_dict(data, columns):
    result = {}
    columns = [col.key if hasattr(col, "key") else col for col in columns]
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
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def paginate(query, page, per_page):
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    pagination = Pagination(query, page, per_page, query.count(), items)
    return pagination


class MediaFiles(Base):
    __tablename__ = "mediafiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    user_relation = relationship("Users",
                                 backref=backref("mediafiles", lazy="dynamic"))
    path = Column(Text(1024), unique=True)
    duration = Column(Integer)
    size = Column(Integer)
    title = Column(String(265))
    description = Column(Text(1024))
    comment = Column(Text(1024))
    tags = Column(String(256))
    coords = Column(String(27))
    location_id = Column(Integer, ForeignKey("locations.id"))
    location_relation = relationship("Locations",
                                     backref=backref("mediafiles", lazy="dynamic"))
    year = Column(Integer)
    created = Column(String(30))
    imported = Column(String(30))
    updated = Column(String(30))
    accessed = Column(String(30))
    visits = Column(Integer)

    def __init__(self, user_relation, path, duration, title, description, comment,
                 tags, coords, location_relation, year, created, size):
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
        self.updated = ""
        self.accessed = ""
        self.visits = 0

    def __repr__(self):
        return "[Metadata for file #%s]" % self.id

    def __str__(self):
        info = """MediaFile: %s
	Owner: %s
	Title: %s
	Description: %s
	Tags: %s
	Comment: %s
	Created: %s
	Year: %s
	GPS: %s
	Location id: %s
	Duration: %s
	Size: %s
	Imported: %s
	Updated: %s
	Accessed: %s
	Visits: %s
	""" % (self.path, self.user_id,
           self.title, self.description, self.tags, self.comment,
           self.created, self.year, self.coords, self.location_id, self.duration, self.size,
           self.imported, self.updated, self.accessed, self.visits)
        return info


class Tags(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True)
    tag = Column(String(20), unique=True)

    def __init__(self, tag):
        self.tag = tag

    def __repr__(self):
        return "Tag #%s: %s" % (self.id, self.tag)

    def __str__(self):
        return json.dumps(self, indent=4, sort_keys=True)


class Users(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    login = Column(String(20), unique=True)
    password = Column(String(20))

    def __init__(self, login, password):
        self.login = login
        self.password = password

    def __repr__(self):
        return "[User #%s]" % self.id

    def __str__(self):
        return json.dumps(self, indent=4, sort_keys=True)


class Locations(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True)
    latitude = Column(Float, unique=True)
    longitude = Column(Float, unique=True)
    city = Column(String(30), unique=True)
    country = Column(String(30))

    def __init__(self, latitude, longitude, city, country):
        self.city = city
        self.country = country
        self.latitude = latitude
        self.longitude = longitude

    def __repr__(self):
        return "[Location #%s]" % self.id

    def __str__(self):
        info = """Location # %s
	Latitude: %s
	Longitude: %s
	City: %s
	Country: %s
	""" % (self.id, self.latitude, self.longitude, self.city, self.country)
        return info



@app.before_first_request
def startup():
    # TODO: create default content for Locations, Users, Tags
    #db.create_all()
    Base.metadata.create_all(engine)
    places = [(0, 0, "", ""),
              (53.87303611111111, 27.65790833333333, 'minsk', 'belarus')]
    for place in places:
        latitude, longitude, city, country = place
        location = Locations(latitude, longitude, city, country)
        if place == places[0]:
            location.id = 0
        db_session.add(location)

    users = [('', ''),
             ('minsk', 'belarus')]
    for user in users:
        login, password = user
        person = Users(login, password)
        if user == users[0]:
            person.id = 0
        db_session.add(person)
    try:
        db_session.commit()
    except exc.IntegrityError:
        db_session.rollback()






'''
#class MediaFiles(db.Model):
class MediaFiles(Base):
    __tablename__ = "mediafiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user_relation = db.relationship("Users",
                                    backref=db.backref("mediafiles", lazy="dynamic"))
    path = db.Column(db.Text(1024), unique=True)
    duration = db.Column(db.Integer)
    size = db.Column(db.Integer)
    title = db.Column(db.String(265))
    description = db.Column(db.Text(1024))
    comment = db.Column(db.Text(1024))
    tags = db.Column(db.String(256))
    coords = db.Column(db.String(27))
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"))
    location_relation = db.relationship("Locations",
                                        backref=db.backref("mediafiles", lazy="dynamic"))
    year = db.Column(db.Integer, unique=True)
    created = db.Column(db.String(30))
    imported = db.Column(db.String(30))
    updated = db.Column(db.String(30))
    accessed = db.Column(db.String(30))
    visits = db.Column(db.Integer)

    def __init__(self, user_relation, path, duration, title, description, comment,
                 tags, coords, location_relation, year, created, size):
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
        self.updated = ""
        self.accessed = ""
        self.visits = 0

    def __repr__(self):
        return "[Metadata for file #%s]" % self.id

    def __str__(self):
        info = """MediaFile: %s
	Owner: %s
	Title: %s
	Description: %s
	Tags: %s
	Comment: %s
	Created: %s
	Year: %s
	GPS: %s
	Location id: %s
	Duration: %s
	Size: %s
	Imported: %s
	Updated: %s
	Accessed: %s
	Visits: %s
	""" % (self.path, self.user_id,
           self.title, self.description, self.tags, self.comment,
           self.created, self.year, self.coords, self.location_id, self.duration, self.size,
           self.imported, self.updated, self.accessed, self.visits)
        return info

#class Tags(db.Model)
class Tags(Base):
    __tablename__ = "tags"
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(20), unique=True)

    def __init__(self, tag):
        self.tag = tag

    def __repr__(self):
        return "Tag #%s: %s" % (self.id, self.tag)

    def __str__(self):
        return json.dumps(self, indent=4, sort_keys=True)


class Users(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(20), unique=True)
    password = db.Column(db.String(20))

    def __init__(self, login, password):
        self.login = login
        self.password = password

    def __repr__(self):
        return "[User #%s]" % self.id

    def __str__(self):
        return json.dumps(self, indent=4, sort_keys=True)

#class Locations(db.Model)
class Locations(Base):
    __tablename__ = "locations"
    id = db.Column(db.Integer, primary_key=True)
    latitude = db.Column(db.Float, unique=True)
    longitude = db.Column(db.Float, unique=True)
    city = db.Column(db.String(30), unique=True)
    country = db.Column(db.String(30), unique=True)

    def __init__(self, latitude, longitude, city, country):
        self.latitude = latitude
        self.longitude = longitude
        self.city = city
        self.country = country

    def __repr__(self):
        return "[Location #%s]" % self.id

    def __str__(self):
        info = """Location # %s
	Latitude: %s
	Longitude: %s
	City: %s
	Country: %s
	""" % (self.id, self.latitude, self.longitude, self.city, self.country)
        return info



@app.before_first_request
def startup():
    # TODO: create default content for Locations, Users, Tags
    #db.create_all()
    Base.metadata.create_all(engine)
    places = [(0, 0, "", ""),
              (53.87303611111111, 27.65790833333333, 'minsk', 'belarus')]
    for place in places:
        latitude, longitude, city, country = place
        location = Locations(latitude, longitude, city, country)
        if place == places[0]:
            location.id = 0
        db.session.add(location)

    users = [('', ''),
             ('minsk', 'belarus')]
    for user in users:
        login, password = user
        person = Users(login, password)
        if user == users[0]:
            person.id = 0
        db.session.add(person)
    try:
        db.session.commit()
    except exc.IntegrityError:
        db.session.rollback()
'''
