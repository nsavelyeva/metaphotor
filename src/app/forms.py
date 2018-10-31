import os
from datetime import datetime
from wtforms import Form, validators, ValidationError, \
                    StringField, PasswordField, TextAreaField, \
                    SelectField, FloatField, DecimalField
from flask_wtf.file import FileField
from app import app


YEAR = datetime.now().year
DATE = '^\d\d\d\d-(0?[1-9]|1[0-2])-(0?[1-9]|[12][0-9]|3[01]) ' + \
       '(00|[0-9]|1[0-9]|2[0-3]):([0-9]|[0-5][0-9]):([0-9]|[0-5][0-9])$'  # e.g. '%Y-%m-%d %H:%M:%S'


def validate_file_exists(form, field):
    if not os.path.isfile(field.data):
        raise ValidationError('Cannot access file "%s". Is the path correct?' % field.data)


class MediaFilesForm(Form):
    user_id = SelectField('Ownership', coerce=int)
    path = StringField('Path', [validators.Length(min=5, max=1024)],
                       render_kw={'size': 140})
    duration = FloatField('Duration', [validators.InputRequired()], default=0,
                          render_kw={'size': 30, 'readonly': 'readonly'})
    title = StringField('Title', [validators.Length(min=5, max=265)], render_kw={'size': 140})
    tags = StringField('Tags', [validators.Length(min=3, max=256)], render_kw={'size': 140})
    description = TextAreaField('Description', [validators.Length(min=3, max=1024)],
                                render_kw={'rows': 3, 'cols': 100})
    comment = TextAreaField('Comment', [validators.Length(min=3, max=1024)],
                            render_kw={'rows': 3, 'cols': 100})
    location_id = SelectField('Location', coerce=int, render_kw={'onchange': 'load_coords()'})
    coords = StringField('Coordinates', render_kw={'size': 140})
    year = SelectField('Year', [validators.NumberRange(1970, YEAR)], coerce=int, default=YEAR,
                       choices=[(0, 'Not Detected')] + \
                               [(year, year) for year in range(1970, YEAR + 1)])
    created = StringField('Created', [validators.DataRequired(), validators.Regexp(regex=DATE)],
                          render_kw={'size': 140})


class LocationsForm(Form):
    city = StringField('City', [validators.DataRequired()],
                       render_kw={'size': 30, 'id': 'geo_city',
                                  'onchange': 'get_city_coords(this.value)'})
    country = StringField('Country', [validators.DataRequired()],
                          render_kw={'size': 30, 'id': 'geo_country', 'readonly': 'readonly'})
    code = StringField('Code', [validators.DataRequired()],
                          render_kw={'size': 30, 'id': 'geo_code', 'readonly': 'readonly'})
    latitude = FloatField('Latitude', [validators.DataRequired()],
                          render_kw={'size': 30, 'id': 'geo_latitude', 'readonly': 'readonly'})
    longitude = FloatField('Longitude', [validators.DataRequired()],
                           render_kw={'size': 30, 'id': 'geo_longitude', 'readonly': 'readonly'})


class TagsForm(Form):
    tag = StringField('Tag', [validators.DataRequired(), validators.Length(min=3, max=15)],
                      render_kw={'size': 30})


class UsersForm(Form):
    login = StringField('Username (login)', [validators.DataRequired()], render_kw={'size': 30})
    password = PasswordField('Password', [validators.DataRequired()], render_kw={'size': 30})


class LoginForm(Form):
    login = StringField('Login', [validators.DataRequired()], default='',
                        render_kw={'size': 30, 'width': '100px'})
    password = PasswordField('Password', [validators.DataRequired()], default='',
                           render_kw={'size': 30, 'width': '100px'})


class SettingsForm(Form):
    media_folder = StringField('Media Folder', [validators.DataRequired()], render_kw={'size': 70})
    ffmpeg_path = StringField('FFMPEG Location', [validators.DataRequired(), validate_file_exists],
                              render_kw={'size': 70})
    ffprobe_path = StringField('FFProbe Location',
                               [validators.DataRequired(), validate_file_exists],
                               render_kw={'size': 70})
    min_filesize = DecimalField('Min file size', [validators.NumberRange(524288, 4294967296)],
                                default=app.config['MIN_FILESIZE'], places=0,
                                render_kw={'size': 10})
    max_filesize = DecimalField('Max file size', [validators.NumberRange(524288, 4294967296)],
                                default=app.config['MAX_FILESIZE'], places=0,
                                render_kw={'size': 10})
    items_per_page = DecimalField('Items per page', [validators.NumberRange(1, 100)],
                                  default=app.config['ITEMS_PER_PAGE'], places=0,
                                  render_kw={'size': 10})


class UploadForm(Form):
    upload = FileField('Upload media file')
