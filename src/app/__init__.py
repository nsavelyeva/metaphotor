import os
import errno
import logging as log
from logging.config import dictConfig
from flask import Flask
from conf import DevConf


dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})


def url_for_other_page(page):
    args = request.view_args.copy()
    args['page'] = page
    return url_for(request.endpoint, **args)


def mkdir_if_not_exists(abs_path, dir_name):
    """Create all non-existing folders mentioned in the given absolute path."""
    full_path = os.path.normpath(os.path.join(abs_path, dir_name))
    try:
        os.makedirs(full_path)
    except OSError as err:
        if err.errno != errno.EEXIST:
            log.error('Could not create directory "%s" due to error: %s.' % (full_path, err))
            raise
    return True


app = Flask(__name__, template_folder='templates')
app.secret_key = 'While drinkers drink drinks, builders build buildings & coders code code.'
app.url_map.strict_slashes = False
app.jinja_env.globals.update(url_for_other_page=url_for_other_page)


# Create upload and download folders if they do not exist:
app.config.from_object(DevConf)
for folder in [app.config['UPLOAD_FOLDER'], 'app/%s' % app.config['DOWNLOAD_FOLDER']]:
    mkdir_if_not_exists(app.config['APP_FOLDER'], folder)


from .views import *
