from datetime import datetime
from wtforms import Form, validators, ValidationError, \
                    StringField, SelectField, TextAreaField, FloatField, DecimalField
from flask_wtf.file import FileField
from sqlalchemy import exc
from app import app


YEAR = datetime.now().year
DATE = '^\d\d\d\d-(0?[1-9]|1[0-2])-(0?[1-9]|[12][0-9]|3[01]) ' + \
       '(00|[0-9]|1[0-9]|2[0-3]):([0-9]|[0-5][0-9]):([0-9]|[0-5][0-9])$' # %Y-%m-%d %H:%M:%S'


class MediaFilesForm(Form):
    user_id = SelectField('Owner', coerce=int)
    path = StringField('Path', [validators.Length(min=5, max=1024)],
                       render_kw={'size': 140})
    duration = FloatField('Duration', [validators.InputRequired()], default=0,
                          render_kw={'size': 30})
    title = StringField('Title', [validators.Length(min=5, max=265)],
                        render_kw={'size': 140})
    description = TextAreaField('Description', [validators.Length(max=1024)],
                                render_kw={'rows': 3, 'cols': 100})
    comment = TextAreaField('Comment', [validators.Length(max=1024)],
                            render_kw={'rows': 3, 'cols': 100})
    tags = StringField('Tags', [validators.Length(min=5, max=256)],
                       render_kw={'size': 140})
    location_id = SelectField('Location', coerce=int)
    year = SelectField('Year', [validators.NumberRange(1970, YEAR)], coerce=int,
                       default=YEAR, choices=[(year, year) for year in range(1970, YEAR)])
    created = StringField('Created', [validators.DataRequired(), validators.Regexp(regex=DATE)],
                          render_kw={'size': 140})


class LocationsForm(Form):
    city = StringField('City', [validators.DataRequired()],
                       render_kw={'size': 30, 'id': 'geo_city',
                                  'onchange': 'get_city_coords(this.value)'})
    country = StringField('Country', [validators.DataRequired()],
                          render_kw={'size': 30, 'id': 'geo_country', 'readonly': 'readonly'})
    latitude = FloatField('Latitude', [validators.DataRequired()],
                          render_kw={'size': 30, 'id': 'geo_latitude', 'readonly': 'readonly'})
    longitude = FloatField('Longitude', [validators.DataRequired()],
                           render_kw={'size': 30, 'id': 'geo_longitude', 'readonly': 'readonly'})


class TagsForm(Form):
    tag = StringField('Tag', [validators.DataRequired(), validators.Length(min=3, max=15)],
                      render_kw={'size': 30})


class UsersForm(Form):
    login = StringField('Login',
                        [validators.DataRequired()], render_kw={'size': 30})
    password = StringField('Password',
                           [validators.DataRequired()], render_kw={'size': 30})


class LoginForm(Form):
    login = StringField('Login',
                        [validators.DataRequired()], render_kw={'size': 30})
    password = StringField('Password',
                           [validators.DataRequired()], render_kw={'size': 30})


class SettingsForm(Form):
    media_folder = StringField('Media Folder',
                               [validators.DataRequired()], render_kw={'size': 70})
    ffmpeg_path = StringField('FFMPEG Location',
                              [validators.DataRequired()], render_kw={'size': 70})
    min_filesize = DecimalField('Min file size', [validators.NumberRange(524288, 4294967296)],
                                default=app.config['MIN_FILESIZE'], places=0,
                                render_kw={'size': 10})
    max_filesize = DecimalField('Max file size', [validators.NumberRange(524288, 4294967296)],
                                  default=app.config['MAX_FILESIZE'], places=0,
                                  render_kw={'size': 10})
    items_per_page = DecimalField('Items per page', [validators.NumberRange(1, 100)],
                                  default=app.config['ITEMS_PER_PAGE'], places=0,
                                  render_kw={'size': 10})

