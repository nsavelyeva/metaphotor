MetaPhotor is a web-application to serve as a small media-centre for personal and family photos and videos.

Reason:
  * I wanted to keep family photos & videos on a home server and search through them from a browser - by tags, locations, etc.
  * Moreover, I wanted my changes to metadata to be stored inside the media files in order to let them survive after copying/moving files.
  * I got inspired by EXIF and FFMPEG, Highcharts + Highmaps, and Mapping APIs.

Tools:
  * Back-end: Flask microframework on the top of Python 3, modules geopy, PIL & piexif, ffmpy (requires FFMPEG executables), multiprocessing.dummy for threading, argparse & logging.
  * Database: PostgreSQL + SQLAlchemy.
  * Front-end: Bootstrap + jQuery + Font Awesome + higcharts & highmaps. All js/css are downloaded but you can adjust links to use CDN.
  * Deployment: docker-compose.yml to run the whole environment in three separate containers: Nginx, PostgreSQL and Flask+uWSGI+FFMPEG.

Howto:
  * Deploy the app:
    - Navigate to the folder "metaphotor/deploy/variant-docker".
    - Adjust values for environment variables in ".env" file.
    - Run the command "docker-compose up -d --build" in a terminal window.
  * Import video and photo files:
    - Open http://localhost/login in your browser and login as "admin/admin" (note, default admin password can be changed at http://localhost/users/edit/1).
    - At http://localhost/settings make sure the absolute path to the media folder is correct and click on "Scan Media Files" button.
  * Stop all containers:
    - Run the command "docker-compose down -v" in a terminal window (note, this is safe to keep the data since PostgreSQL stores it in the folder "metaphotor/deploy/variant-docker/volumes/postgresql_data").
  * Remove data about media files from the database, if you wish to start over with initial deployment:
    - Stop all containers as described above.
    - Remove the folder "metaphotor/deploy/variant-docker/volumes/postgresql_data".

Features:
  * Discover photo and video files on the local storage and display the ongoing scan progress.
    Note: video will be forcibly converted to MP4.
  * Sophisticated search for media files in the database based on their metadata - by tags/year/location/... .
  * Read/Modify metadata inside photo and video files.
  * Compare metadata stored in the database and metadata stored inside media files.
  * Statistics in the form of pie charts and histograms.
  * Geo positioning of a photo/video on the world map including indication of snapshots count per country.
  * Ownership support for media files:
      - scanned files are considered as public;
      - ownership of any file can be changed any time by any authorized user.
  * Listing media files:
      - pagination;
      - gallery, tiles and list views;
      - Top-10 lists: most visited, last created/updated files, etc.
      - Mix-100 list: videos and photos selected randlomly.
  * Besides MediaFiles, support of CRUD-operations for Locations, Users, Tags.
  * Simplified adding location by city, i.e. coordinates, country and country code are automatically detected by city name.
  * Web interface to view/modify application settings.
  * Support options to launch MetaPhotor from command line and application logging.
  * User authentication to support files ownership and restrictions to view non-public pages. Note: you can start using the app as user admin/admin.
  * Dockerized deployment with docker-compose YAML file.
