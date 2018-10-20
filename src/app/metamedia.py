"""A module to read/write metadata in photo and video files."""
import os
import platform
import subprocess
import shutil
import logging
import datetime
import re
import json
import piexif
import piexif.helper
from PIL import Image
from ffmpy import FFmpeg, FFprobe, FFRuntimeError, FFExecutableNotFoundError
from abc import ABC, abstractmethod


EMPTY = bytes(''.encode('utf8'))


def get_file_ctime(path):
    """Get file creation timestamp."""
    if not os.path.isfile(path):
        return None
    if platform.system().lower() == 'windows':
        # need getctime as https://docs.python.org/3/library/os.html#os.stat says,
        # but it seems to work wrong: e.g. actual result shows st_ctime > st_mtime:
        # >>> print(os.stat(<path>))
        # os.stat_result(st_mode=33206, st_ino=562949953426081, st_dev=844210706, st_nlink=1,
        #                st_uid=0, st_gid=0, st_size=15618908, st_atime=1532179025,
        #                st_mtime=1296303144, st_ctime=1532179024)
        return os.path.getmtime(path)
    else:
        stat = os.stat(path)
        try:
            return stat.st_birthtime
        except AttributeError:
            # this is probably Linux, and there is no easy way to get creation time,
            # so the last modified date will be taken.
            return stat.st_mtime


def format_timestamp(timestamp, fmt='%Y-%m-%d %H:%M:%S.%f'):
    """Convert given timestamp into string in a human-friendly format."""
    return datetime.datetime.fromtimestamp(timestamp).strftime(fmt)


class Media(ABC):

    def __init__(self, path):
        self.path = path
        self.size = os.path.getsize(path) if os.path.isfile(path) else None
        self.media = None
        self.metadata = self.read_metadata()
        self.duration = None
        self.title = ''
        self.description = ''
        self.tags = ''
        self.comment = ''
        self.created = ''
        self.year = ''
        self.gps = {'city': '', 'country': '', 'code': '', 'latitude': None, 'longitude': None}
        self._parse_metadata()

    @abstractmethod
    def read_metadata(self):
        """Obtain metadata of the media file."""
        pass

    @abstractmethod
    def write_metadata(self, title, description, tags, comment, gps=None, datetime=None):
        """Update metadata of the media file."""
        pass

    @abstractmethod
    def _parse_metadata(self):
        """From all available metadata, collect only desired values and keep them as attributes."""
        pass

    def _get_year(self):
        """
        Algorithm:
             - if available, take year from metadata creation date (i.e. from self.created)
             - or, take it from file creation date (Windows) or file last-modified date (Linux)
        Note: return None if file does not exist or cannot be accessed
        """
        if self.created:
            return int(self.created[:4])
        timestamp = get_file_ctime(self.path)
        if timestamp:
            return format_timestamp(timestamp, '%Y')
        return None

    def __str__(self):
        """Override __str__ to be able to print() the object in a human-friendly mode."""
        gps = 'coords=(%s,%s)\tcountry=%s\tcity=%s' % \
              (self.gps.get('latitude', ''), self.gps.get('longitude', ''),
               self.gps.get('country', '').title(), self.gps.get('city', '').title())
        info = ('%s: %s\n\tTitle: %s\n\tDescription: %s\n\tTags: %s\n\tComment: %s\n\t' +
                'Created: %s\n\tYear: %s\n\tGPS: %s\n\tDuration: %s\n\tSize: %s bytes\n') % \
               (self.__class__.__name__, self.path,
                self.title, self.description, self.tags, self.comment,
                self.created, self.year, gps, self.duration, self.size)
        return info


class Photo(Media):
    """A class to read & write metadata inside a photo file using Python PIL and piexif modules."""

    def __init__(self, path):
        super().__init__(path)
        self.duration = 0  # All images have 0 duration

    def load_media(self):
        """Load the Photo JPEG-file using PIL.image()."""
        image = None
        try:
            image = Image.open(self.path)
        except IOError as err:
            logging.error('Could not read media: %s.' % err)
        return image

    def read_metadata(self):
        """Obtain EXIF metadata of the Photo JPEG-file using piexif.load()."""
        metadata = None
        self.media = self.load_media()
        if self.media and self.media.info and 'exif' in self.media.info:
            metadata = piexif.load(self.media.info['exif'])
        return metadata

    def write_metadata(self, title, description, tags, comment, gps=None, datetime=None):
        """Update EXIF metadata of the Photo JPEG-file using piexif.dump() and PIL.image.save()."""
        if not self.metadata:
            return False
        if datetime:  # e.g. '2015:01:29 21:29:29'
            self.metadata['0th'][piexif.ImageIFD.DateTime] = datetime
        self.metadata['0th'][piexif.ImageIFD.DocumentName] = title
        self.metadata['0th'][piexif.ImageIFD.ImageDescription] = description
        self.metadata['0th'][piexif.ImageIFD.ImageHistory] = tags
        self.metadata['Exif'][piexif.ExifIFD.UserComment] = piexif.helper.UserComment.dump(comment)
        # GPSMapDatum example value: '53.87303611111111,27.65790833333333,minsk,belarus,by'
        if gps:
            self.metadata['GPS'][piexif.GPSIFD.GPSMapDatum] = \
            '%(latitude)s,%(longitude)s,%(city)s,%(country)s,%(code)s' % \
            {key: value or '' for key, value in gps.items()}
        exif_bytes = piexif.dump(self.metadata)
        try:
            self.media.save(self.path, 'jpeg', exif=exif_bytes)
        except IOError as err:
            logging.error('Cannot save "%s" after metadata update due to: %s.' % (self.path, err))
            return False
        return True

    def _get_exif_datetime(self):
        """Read datetime value from EXIF Tags and format it as a string 'YYYY-mm-dd HH:MM:SS'."""
        pattern = '^[12]{1}[0-9]{3}.[01]{1}[0-9]{1}.[0-3]{1}[0-9]{1}.' + \
                  '[0-2]{1}[0-9]{1}.[0-5]{1}[0-9]{1}.[0-5]{1}[0-9]{1}$'  # 'YYYY?mm?dd?HH?MM?SS'
        dat = self.metadata['0th'].get(piexif.ImageIFD.DateTime, EMPTY).decode('utf-8')
        if re.match(pattern, dat):  # e.g. '2015:01:29 21:29:29'
            parts = {'year': dat[0:4], 'month': dat[5:7], 'day': dat[8:10],
                     'hour': dat[11:13], 'minute': dat[14:16], 'second': dat[17:19]}
            return '%(year)s-%(month)s-%(day)s %(hour)s:%(minute)s:%(second)s' % parts
        logging.error('Cannot format EXIF Datetime: "%s" -> "YYYY-mm-dd HH:MM:SS"' % dat)
        return None

    @staticmethod
    def _exif_gps_to_coords(value):
        """Convert Geo-coordinate collected from EXIF GPS into a float degree value."""
        degree = float(value[0][0]) / float(value[0][1])
        minute = float(value[1][0]) / float(value[1][1])
        second = float(value[2][0]) / float(value[2][1])
        return degree + (minute / 60.0) + (second / 3600.0)

    def _get_exif_gps_coords(self):
        """Return a tuple (latitude, longitude) if available, or (None, None) otherwise."""
        latitude = longitude = None
        gps_latitude = self.metadata['GPS'].get(piexif.GPSIFD.GPSLatitude)
        gps_latitude_ref = self.metadata['GPS'].get(piexif.GPSIFD.GPSLatitudeRef)
        gps_longitude = self.metadata['GPS'].get(piexif.GPSIFD.GPSLongitude)
        gps_longitude_ref = self.metadata['GPS'].get(piexif.GPSIFD.GPSLongitudeRef)
        if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:
            latitude = self._exif_gps_to_coords(gps_latitude)
            if gps_latitude_ref.decode('utf-8') != 'N':
                latitude = -latitude
            longitude = self._exif_gps_to_coords(gps_longitude)
            if gps_longitude_ref.decode('utf-8') != 'E':
                longitude = -longitude
        return latitude, longitude

    def __get_metadata_value(self, item, value, default=EMPTY):
        """A supplementary getter method to shorten the code."""
        return self.metadata[item].get(value, default).decode('utf-8').replace('\x00', '')

    def _parse_metadata(self):
        """Collect desired values from EXIF data and keep them as attributes."""
        if not self.metadata:
            return False
        self.title = self.__get_metadata_value('0th', piexif.ImageIFD.DocumentName)
        self.description = self.__get_metadata_value('0th', piexif.ImageIFD.ImageDescription)
        self.comment = self.__get_metadata_value('Exif', piexif.ExifIFD.UserComment) \
                           .replace('ASCII', '')
        self.tags = self.__get_metadata_value('0th', piexif.ImageIFD.ImageHistory)
        self.created = self._get_exif_datetime() or ''
        self.year = self.year or self._get_year() or ''
        # Now try to get GPSMapDatum value if exists, or collect GPS tags and convert to address
        gps_info = self.__get_metadata_value('GPS', piexif.GPSIFD.GPSMapDatum).split(',')
        try:  # attempt to keep at least city+country if coords are not set
            self.gps = {'city': gps_info[2].strip(), 'country': gps_info[3].strip(),
                        'code': gps_info[4].strip(),
                        'latitude': float(gps_info[0]) if gps_info[0] else None,
                        'longitude': float(gps_info[1]) if gps_info[1] else None}
        except (ValueError, IndexError) as err:
            logging.warning('Failed to read GPSDatum value for %s.' % self.path)
            latitude, longitude = self._get_exif_gps_coords()
            if latitude and longitude:
                city, country, code = geo_tools.get_address(latitude, longitude)
                self.gps = {'city': city, 'country': country, 'code': code,
                            'latitude': latitude, 'longitude': longitude}
            else:
                logging.warning('EXIF GPS info is incorrect/missing for %s: %s' % (self.path, err))
                return False
        return True


class Video(Media):
    """
    A class to read & write metadata inside a video file using FFMPEG and FFprobe executables.
    Note: according to https://wiki.multimedia.cx/index.php/FFmpeg_Metadata,
    the following 17 metadata items are supported in QuickTime/MOV/MP4/M4A/et al.:
        title, author, album_artist, album, grouping, composer, year, track, comment, genre,
        copyright, description, synopsis, show, episode_id, network, lyrics.
    Since this list does not contain anything explicitly related to GPS info, tags list and
    date in custom format, these fields were selected: album for GPS info, grouping for tags, and
    copyright for date (e.g. 2015-01-29 21:29:29).
    Note, once video files are imported/uploaded into MetaPhotor - they are converted into MP4.
    """

    def __init__(self, path, ffmpeg_path, ffprobe_path):
        self.ffmpeg = ffmpeg_path
        self.ffprobe = ffprobe_path
        super().__init__(path)

    def read_metadata(self):
        """
        Obtain metadata of the video file in JSON format using FFprobe from FFMPEG.

        :Example of equivalent of FFprobe command and its output:

        > ffprobe.exe -v quiet -of json -show_format -show_private_data -i video.mp4
        {
            "format": {
                "filename": "drive:\\path\\to\\video.mp4",
                "nb_streams": 2,
                "nb_programs": 0,
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "format_long_name": "QuickTime / MOV",
                "start_time": "0.000000",
                "duration": "7.531000",
                "size": "5164288",
                "bit_rate": "5485898",
                "probe_score": 100,
                "tags": {
                    "major_brand": "isom",
                    "minor_version": "512",
                    "compatible_brands": "isomiso2avc1mp41",
                    "title": "nice title",
                    "album": "52.3005585,4.67532055295702,hoofddorp,the netherlands",
                    "encoder": "Lavf58.17.101",
                    "comment": "some comment",
                    "copyright": "2017-01-29 21:29:29",
                    "grouping": "tag1 tag2",
                    "description": "some description"
                }
            }
        }
        """
        ffprobe = FFprobe(self.ffprobe,
                          global_options=['-v', 'quiet', '-print_format', 'json',
                                          '-show_format', '-show_private_data'],
                          inputs={self.path: None})
        logging.debug('Running FFprobe command "%s".' % ffprobe.cmd)
        stdout = ffprobe.run(stdout=subprocess.PIPE)[0]
        return json.loads(stdout)

    def convert_to_mp4(self, options=' -y -vcodec h264 -acodec aac -strict -2 -b:a 384k '):
        """
        Convert a video file into MP4 (tested on .3gp, .mov, mpg, .avi). Do nothing for .mp4.
        Before conversion, a temporary file is created and after operation it is removed.
        If successful, the source file is also removed.

        :Example of equivalent of FFMPEG command:

        > ffmpeg.exe -y -i video.mov.tmp  -vcodec h264 -acodec aac -strict -2 -b:a 384k  video.mp4
        """
        if self.path.lower().endswith('.mp4'):
            logging.debug('Conversion of "%s" is skipped: already in MP4 format.' % self.path)
            return ''
        tmp_path = '%s.tmp' % self.path
        new_path = self.path[:self.path.rfind('.')] + '.MP4'
        # Create a temporary file:
        try:
            shutil.copy(self.path, tmp_path)
        except IOError as err:
            logging.error('Cannot create a temporary copy "%s" due to %s.' % (tmp_path, err))
            return ''
        try:
            ffmpeg = FFmpeg(self.ffmpeg,
                            inputs={tmp_path: None},
                            outputs={new_path: options or ''})
            logging.info('Running FFmpeg command: %s.' % ffmpeg.cmd)
            stderr, stdout = ffmpeg.run(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logging.info('Converted "%s" into "%s".' % (tmp_path, new_path))
        except (FFRuntimeError, FFExecutableNotFoundError) as err:
            logging.error('Cannot convert "%s" -> "%s" due to %s.' % (tmp_path, new_path, err))
            return ''
        finally:
            # Remove the temporary file
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)
                logging.info('Removed temporary file "%s".' % tmp_path)
        # Remove non-MP4 source file if any
        if self.path.lower() != new_path.lower() and os.path.isfile(self.path):
            os.remove(self.path)
            logging.info('Removed source file "%s".' % self.path)
        self.path = new_path
        return '\n'.join([stdout.decode('utf-8', 'ignore'), stderr.decode('utf-8', 'ignore')])

    def write_metadata(self, title, description, tags, comment, gps=None, datetime=None):
        """
        Write metadata inside a video file.
        Notes:
        1) since with FFMPEG it is not possible to write metadata into the same file at once,
           then for FFMPEG command we must provide:
              an input file name, metadata parameters and the output file name,
           and if both files have same name, the command will fail
           (video will be spoiled: only first frame will remain).
           So, before metadata update, a temporary copy of the video file is created.

        2) Metadata fields 'title', 'description', 'comment', 'copyright', 'grouping', 'album'
           are supported by MP4 format, and the other video formats have less supported fields.
           Conversion to MP4 is already done during importing/uploading into MetaPhotor.

        3) GPS metadata is given as 'latitude,longitude,city,country,code' (coords can be empty:
           e.g. ',,city,country,code'). If GPS metadata is not set at all, empty string is written.

        :Example of equivalent of FFprobe command:

        > fmpeg.exe -y -i video.mov.tmp -metadata title="my title" -metadata comment="my comment" \
           -metadata description="my description" -metadata grouping="tag1 tag2" \
           -metadata copyright="2015-01-29 21:29:29" \
           -metadata album="53.87303611111111,27.65790833333333,minsk,belarus,by" \
           -vcodec copy -acodec copy   video.mp4
        """
        gps = '%(latitude)s,%(longitude)s,%(city)s,%(country)s,%(code)s' % \
              {key: value or '' for key, value in gps.items()}
        metadata = {'title': title, 'description': description, 'comment': comment,
                    'grouping': tags, 'album': gps or '', 'copyright': datetime or self.year or ''}
        options = ' -metadata '.join(['%s="%s"' % (key, metadata[key]) for key in metadata.keys()])
        ffmpeg_output = self.convert_to_mp4(' -y -vcodec copy -acodec copy  -metadata ' + options)
        return ffmpeg_output

    def __get_metadata_value(self, item, default, from_tag=True):
        if from_tag:
            return self.metadata.get('format', {}).get('tags', {}).get(item, default).strip()
        return self.metadata.get('format', {}).get(item, default).strip()

    def _parse_metadata(self):
        """From all available metadata, collect only desired values and keep them as attributes."""
        self.duration = float(self.__get_metadata_value('duration', '-1', False))
        self.title = self.__get_metadata_value('title', '')
        self.description = self.__get_metadata_value('description', '')
        self.tags = self.__get_metadata_value('grouping', '')
        self.comment = self.__get_metadata_value('comment', '')
        self.created = self.__get_metadata_value('copyright', '') \
                       or format_timestamp(get_file_ctime(self.path), '%Y-%m-%d %H:%M:%S')
        self.year = self.year or self._get_year() or ''
        gps_info = self.__get_metadata_value('album', '')
        if gps_info:
            try:  # attempt to keep at least city+country if coords are not set
                latitude, longitude, city, country, code = gps_info.split(',')
                self.gps = {'city': city.strip(), 'country': country.strip(), 'code': code.strip(),
                            'latitude': float(latitude) if latitude else None,
                            'longitude': float(longitude) if longitude else None}
            except (ValueError, IndexError) as err:
                logging.warning('Failed to parse GPS info (stored in "album" tag) for %s due to %s.'
                                % (self.path, err))
                return False
        return True


class MultiMedia:
    """A factory class to create an instance of media file class of needed type - Photo/Video."""

    @staticmethod
    def detect(path, app_config, **kwargs):
        """
        Factory method to determine a media type from the given file path based on file extension.
        and return an object of a protocol class derived from Manifest() class.

        :param path: an absolute path to the file.

        :return: an instance of Photo or Video class. Return None if file extension is unexpected.
        """
        result_obj = None
        file_extension = path[path.rfind('.') + 1:].lower()
        if file_extension in ['jpg', 'jpeg']:
            result_obj = Photo(path)
        elif file_extension in app_config['ALLOWED_EXTENSIONS']:
            if not (os.path.isfile(kwargs.get('ffmpeg_path', ''))
                    and os.path.isfile(kwargs.get('ffprobe_path', ''))):
                logging.error('Cannot find FFMPEG/FFProbe executables. Check MetaPhotor settings.')
            else:
                result_obj = Video(path, kwargs['ffmpeg_path'], kwargs['ffprobe_path'])
        return result_obj
