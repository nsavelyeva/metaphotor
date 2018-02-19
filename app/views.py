import json
from flask import session, render_template, redirect, url_for, request, jsonify, flash, send_from_directory
from app import app
from .forms import MediaFilesForm, LocationsForm, TagsForm, UsersForm, LoginForm, SettingsForm, validators #, get_locations_choices
from .models import MediaFiles, Locations, Users, Tags, db_session, paginate #, db
from . import db_queries
from . import geo_tools
from . import helpers

#+
@app.route("/_scan")
def scan():
    all_media_files = helpers.find_media_files(app.config["MEDIA_FOLDER"],
                                               app.config["ALLOWED_EXTENSIONS"])
    db_queries.remove_previously_scanned()
    helpers.parallel_scan(session.get("user_id", 0), all_media_files)
    return jsonify(total=len(all_media_files))

#+
@app.route("/_scan_status")
def scan_status():
    with open("scan.json", "r+") as _f:
        data = json.loads(_f.read())
    return jsonify(total=data["total"], failed=data["failed"], passed=data["passed"])

#+
@app.route("/_get_city_coords")
def get_city_coords():
    latitude = longitude = city = country = error = ""
    form_city = request.args.get("city").strip().lower()
    if form_city:
        latitude, longitude = geo_tools.get_coords(form_city)
        city, country = geo_tools.get_address(latitude, longitude)
    if not country:
        error = "Could not get Geo coordinates for city '%s'." % form_city
        city = form_city
    return jsonify(latitude=latitude, longitude=longitude, country=country, city=city, error=error)

#+
@app.route("/")
def home():
    return render_template("home.html")

#+
@app.route("/about")
def about():
    return render_template("about.html")

## CRUD for mediafiles:
#+
@app.route("/mediafiles/list", defaults={"page": 1}, methods=["GET"])
@app.route("/mediafiles/list/<int:page>", methods=["GET"])
@app.route("/albums", defaults={"page": 1}, methods=["GET"])
@app.route("/albums/<int:page>", methods=["GET"])
def list_mediafiles(page):
    fields = [MediaFiles.id, MediaFiles.year, MediaFiles.path, MediaFiles.tags]
    if request.args and "entry" in request.args.to_dict():
        entry = str(request.args.to_dict()["entry"])
        query = db_queries.find_mediafiles(fields, entry)
    else:
        query = db_queries.get_all_mediafiles(fields)
    pagination = paginate(query, page, app.config["ITEMS_PER_PAGE"])
    flash("Found items: %s" % pagination.total, "info")
    return render_template("list.html", rows=pagination.items, pagination=pagination,
                           table="mediafiles", fields=[field.__dict__["key"] for field in fields])

#
@app.route("/mediafiles/view/<int:mediafile_id>", methods=["GET"])
def view_mediafile(mediafile_id):
    fields = [MediaFiles.id, Users.login, MediaFiles.path, MediaFiles.duration, MediaFiles.size,
              MediaFiles.title, MediaFiles.description, MediaFiles.comment, MediaFiles.tags,
              MediaFiles.coords, Locations.city, MediaFiles.year, MediaFiles.created,
              MediaFiles.imported, MediaFiles.updated, MediaFiles.accessed, MediaFiles.visits]
    mediafile = db_queries.get_mediafile_details(mediafile_id, fields)
    return render_template("item.html", item=mediafile, fields=mediafile)

#
@app.route("/mediafiles/delete/", methods=["POST"])
def delete_mediafile():
    if request.form and "item" in request.form:
        mediafile_id = int(request.form.get("item", type=int))
        msg, style = db_queries.remove_mediafile(mediafile_id)
        flash(msg, style)
    return redirect(url_for("list_mediafiles"))


@app.route("/mediafiles/add", methods=["GET", "POST"])
def add_mediafile():
    # TODO
    form = MediaFilesForm(request.form)
    if request.method == "POST" and form.validate():
        values = []
        msg, style, media_file = db_queries.create_mediafile(values)
        flash(msg, style)
        if style == "success":
            return redirect(url_for("list_mediafiles"))
    return render_template("anyform.html", form=form, submit_name="Save")


@app.route("/mediafiles/edit/<int:mediafile_id>", methods=["GET", "POST"])
def edit_mediafile(mediafile_id):
    if request.method == "GET":
        form = MediaFilesForm(obj=db_queries.get_mediafile(mediafile_id))
    else:
        form = MediaFilesForm(request.form)
    form.user_id.choices = helpers.get_users_choices()
    form.location_id.choices = helpers.get_locations_choices()
    if request.method == "POST" and form.validate():
        msg, style = db_queries.update_mediafile(request.form, mediafile_id)
        flash(msg, style)
        if style == "success":
            return redirect(url_for("list_mediafiles"))
    return render_template("anyform.html", form=form, submit_name="Save")





## CRUD for locations:
# +
@app.route("/locations/list", defaults={"page": 1}, methods=["GET"])
@app.route("/locations/list/<int:page>", methods=["GET"])
def list_locations(page):
    fields = [Locations.id,
              Locations.latitude, Locations.longitude, Locations.city, Locations.country]
    query = db_queries.get_all_locations(fields)
    pagination = paginate(query, page, app.config["ITEMS_PER_PAGE"])
    flash("Found locations: %s" % pagination.total, "info")
    return render_template("list.html", rows=pagination.items, pagination=pagination,
                           table="locations", fields=[field.__dict__["key"] for field in fields])

# +
@app.route("/locations/view/<int:location_id>", methods=["GET"])
def view_location(location_id):
    location = db_queries.get_location(location_id, as_dict=True)
    return render_template("item.html", item=location)

# +
@app.route("/locations/edit/<int:location_id>", methods=["GET", "POST"])
def edit_location(location_id):
    location = db_queries.get_location(location_id)
    form = LocationsForm(obj=location)
    if request.method == "POST" and form.validate():
        msg, style = db_queries.update_location(request.form, location_id)
        flash(msg, style)
        if style == "success":
            return redirect(url_for("list_locations"))
    return render_template("anyform.html", form=form, submit_name="Save")

# +
@app.route("/locations/delete/", methods=["POST"])
def delete_location():
    if request.form and "item" in request.form:
        location_id = int(request.form.get("item", type=int))
        msg, style = db_queries.remove_location(location_id)
        flash(msg, style)
    return redirect(url_for("list_locations"))

# +
@app.route("/locations/add", methods=["GET", "POST"])
def add_location():
    form = LocationsForm(request.form)
    if request.method == "POST" and form.validate():
        msg, style, language = db_queries.create_location(form.city.data, form.country.data,
                                                          form.latitude.data, form.longitude.data)
        flash(msg, style)
        if style == "success":
            return redirect(url_for("list_locations"))  # TODO: do we need redirect to locations?
    return render_template("anyform.html", form=form, submit_name="Save")


## CRUD for tags:

@app.route("/tags/list", defaults={"page": 1}, methods=["GET"])
@app.route("/tags/list/<int:page>", methods=["GET"])
def list_tags(page):
    fields = [Tags.id, Tags.tag]
    query = db_queries.get_all_tags(fields)
    pagination = paginate(query, page, app.config["ITEMS_PER_PAGE"])
    flash("Found tags: %s" % pagination.total, "info")
    return render_template("list.html", rows=pagination.items, pagination=pagination,
                           table="tags", fields=[field.__dict__["key"] for field in fields])


@app.route("/tags/view/<int:tag_id>", methods=["GET"])
def view_tag(tag_id):
    tag = db_queries.get_tag(tag_id, as_dict=True)
    return render_template("item.html", item=tag)


@app.route("/tags/edit/<int:tag_id>", methods=["GET", "POST"])
def edit_tag(tag_id):
    tag = db_queries.get_tag(tag_id)
    form = TagsForm(obj=tag)
    if request.method == "POST" and form.validate():
        msg, style = db_queries.update_tag(request.form, tag_id)
        flash(msg, style)
        if style == "success":
            return redirect(url_for("list_tags"))
    return render_template("anyform.html", form=form, submit_name="Save")


@app.route("/tags/delete/", methods=["POST"])
def delete_tag():
    if request.form and "item" in request.form:
        tag_id = int(request.form.get("item", type=int))
        msg, style = db_queries.remove_tag(tag_id)
        flash(msg, style)
    return redirect(url_for("list_tags"))


@app.route("/tags/add", methods=["GET", "POST"])
def add_tag():
    form = TagsForm(request.form)
    if request.method == "POST" and form.validate():
        msg, style, language = db_queries.create_tag(form.tag.data)
        flash(msg, style)
        if style == "success":
            return redirect(url_for("list_tags"))
    return render_template("anyform.html", form=form, submit_name="Save")


## CRUD for users:

@app.route("/users/list", defaults={"page": 1}, methods=["GET"])
@app.route("/users/list/<int:page>", methods=["GET"])
def list_users(page):
    fields = [Users.id, Users.login]
    query = db_queries.get_all_users(fields)
    pagination = paginate(query, page, app.config["ITEMS_PER_PAGE"])
    flash("Found users: %s" % pagination.total, "info")
    return render_template("list.html", rows=pagination.items, pagination=pagination,
                           table="users", fields=[field.__dict__["key"] for field in fields])


@app.route("/users/view/<int:user_id>", methods=["GET"])
def view_user(user_id):
    user = db_queries.get_user(user_id, as_dict=True)
    return render_template("item.html", item=user)


@app.route("/users/edit/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    user = db_queries.get_user(user_id)
    form = UsersForm(obj=user)
    if request.method == "POST" and form.validate():
        msg, style = db_queries.update_user(request.form, user_id)
        flash(msg, style)
        if style == "success":
            return redirect(url_for("list_users"))
    return render_template("anyform.html", form=form, submit_name="Save")


@app.route("/users/delete/", methods=["POST"])
def delete_user():
    if request.form and "item" in request.form:
        user_id = int(request.form.get("item", type=int))
        msg, style = db_queries.remove_user(user_id)
        flash(msg, style)
    return redirect(url_for("list_users"))


@app.route("/users/add", methods=["GET", "POST"])
def add_user():
    form = UsersForm(request.form)
    if request.method == "POST" and form.validate():
        msg, style, language = db_queries.create_user(form.login.data.strip(),
                                                      form.password.data.strip())
        flash(msg, style)
        if style == "success":
            return redirect(url_for("list_users"))
    return render_template("anyform.html", form=form, submit_name="Save")


@app.route("/statistics")
def get_statistics():
    data = db_queries.get_statistics()
    return jsonify(result=data)

@app.route("/settings/update", methods=["GET", "POST"])
def settings_update():
    form = SettingsForm(request.form)
    form.media_folder.data = app.config["MEDIA_FOLDER"]
    form.ffmpeg_path.data = app.config["FFMPEG_PATH"]
    form.min_filesize.data = app.config["MIN_FILESIZE"]
    form.max_filesize.data = app.config["MAX_FILESIZE"]
    form.items_per_page.data = app.config["ITEMS_PER_PAGE"]
    if request.method == "POST" and form.validate():
        settings = {"MEDIA_FOLDER": request.form.get("media_folder"),
                    "FFMPEG_PATH": request.form.get("ffmpeg_path"),
                    "MIN_FILESIZE": int(request.form.get("min_filesize")),
                    "MAX_FILESIZE": int(request.form.get("max_filesize")),
                    "ITEMS_PER_PAGE": request.form.get("items_per_page")}
        if helpers.update_settings_file(settings, app.config["SETTINGS_FILE"]):
            app.config.update(settings)  # reload config only after successful file update
            flash("Settings have been updated", "success")
        else:
            flash("Could not save settings", "danger")
        return render_template("settings.html", settings=helpers.collect_settings(app.config))
    return render_template("anyform.html", form=form, submit_name="Apply")


@app.route("/settings/restore", methods=["GET", "POST"])
def settings_restore():
    # TODO: set empty strings as defaults for MEDIA_FOLDER and FFMPEG_PATH
    settings = {"MEDIA_FOLDER": "C:\\_WORK_\\Non-projects\\development\\data",
                "FFMPEG_PATH": "C:\\Users\\Natallia_Savelyeva\\Downloads\\ffmpeg-3.4-win64-static\\bin\\ffmpeg.exe",
                "MIN_FILESIZE": 524288, "MAX_FILESIZE": 1073741824, "ITEMS_PER_PAGE": 10}
    if helpers.update_settings_file(settings, app.config["SETTINGS_FILE"]):
        app.config.update(settings)
        flash("Loaded default settings", "success")
    else:
        flash("Could not restore settings", "danger")
    return render_template("settings.html", settings=helpers.collect_settings(app.config))


@app.route("/settings", methods=["GET"])
@app.route("/settings/view", methods=["GET"])
def settings_view():
    return render_template("settings.html", settings=helpers.collect_settings(app.config))


@app.errorhandler(404)
def page_not_found(e):
    error = "Page Not Found"
    return render_template("error.html", code=404, error=error), 404


@app.errorhandler(500)
def internal_server_error(e):
    error = "Internal Server Error"
    return render_template("error.html", code=500, error=error), 500


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()




