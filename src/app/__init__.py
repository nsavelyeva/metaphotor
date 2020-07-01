from logging.config import dictConfig
from flask import Flask
from conf import conf


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


app = Flask(__name__, template_folder='templates')
app.secret_key = 'While drinkers drink drinks, builders build buildings & coders code code.'
app.url_map.strict_slashes = False
app.jinja_env.globals.update(url_for_other_page=url_for_other_page)


# Create upload and download folders if they do not exist:
app.config.from_object(conf.DevConf)
for folder in [app.config['UPLOAD_FOLDER'], 'app/%s' % app.config['DOWNLOAD_FOLDER']]:
    conf.mkdir_if_not_exists(app.config['APP_FOLDER'], folder)


from .views import *
