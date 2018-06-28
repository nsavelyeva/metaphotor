# -*- coding: utf-8 -*-
import os
import platform
import datetime
import re
import json
import piexif
from abc import ABCMeta, abstractmethod
from PIL import Image
from . import geo_tools


EMPTY = bytes(''.encode('utf8'))


def get_file_ctime(path):
    """Get file creation timestamp."""
    if not os.path.isfile(path):
        return None
    if platform.system().lower() == 'windows':
        return os.path.getctime(path)
    else:
        stat = os.stat(path)
        try:
            return stat.st_birthtime
        except AttributeError:
            # We're probably on Linux. No easy way to get creation dates here,
            # so we'll settle for when its content was last modified.
            return stat.st_mtime


def format_timestamp(timestamp, fmt='%Y-%m-%d %H:%M:%S.%f'):
    return datetime.datetime.fromtimestamp(timestamp).strftime(fmt)


class Media(object):
    __metaclass__ = ABCMeta

    def __init__(self, path):
        self.path = path
        self.size = os.path.getsize(path) if os.path.isfile(path) else None
        self.media = self.load_media()
        self.metadata = self.read_metadata()
        self.duration = None
        self.title = ''
        self.description = ''
        self.tags = ''
        self.comment = ''
        self.year = ''
        self.created = ''
        self.gps = {'city': '', 'country': '',
                    'latitude': None, 'longitude': None}
        self._parse_metadata()

    @abstractmethod
    def load_media(self):
        """Load the media file using appropriate module."""
        pass

    @abstractmethod
    def read_metadata(self):
        """Obtain metadata of the media file."""
        pass

    @abstractmethod
    def write_metadata(self, title, description, tags, comment, timestamp):
        """Update metadata of the media file."""
        pass

    @abstractmethod
    def _parse_metadata(self):
        """From all available metadata, collect only desired values and keep them as attributes."""
        pass

    def _get_year(self):
        """Algorithm:
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
        gps = 'coords=(%s,%s)\tcountry=%s \tcity=%s' % \
              (self.gps.get('latitude'), self.gps.get('longitude'),
               self.gps.get('country').title(), self.gps.get('city').title())
        info = '''Photo: %s
	Content: %s
	Title: %s
	Description: %s
	Tags: %s
	Comment: %s
	Created: %s
	Year: %s
	GPS: %s
	Duration: %s
	Size: %s
	''' % (self.path, '<content>' if self.media else None,
           self.title, self.description, self.tags, self.comment,
           self.created, self.year, gps, self.duration, self.size)
        return info


class Photo(Media):

    def __init__(self, path):
        super(Photo, self).__init__(path)
        self.duration = 0  # All images have 0 duration

    def load_media(self):
        """Load the Photo JPEG-file using PIL.image()."""
        image = None
        try:
            image = Image.open(self.path)
        except IOError as err:
            print('ERROR - Could not read media: %s' % err)
        return image

    def read_metadata(self):
        """Obtain EXIF metadata of the Photo JPEG-file using piexif.load()."""
        metadata = None
        if self.media and self.media.info and 'exif' in self.media.info:
            metadata = piexif.load(self.media.info['exif'])
        return metadata

    def write_metadata(self, title, description, tags, comment, datetime=None):
        """Update EXIF metadata of the Photo JPEG-file using piexif.dump() and PIL.image.save()."""
        if not self.metadata:
            return False
        if datetime:  # e.g. '2015:01:29 21:29:29'
            self.metadata['0th'][piexif.ImageIFD.DateTime] = datetime
        self.metadata['0th'][piexif.ImageIFD.DocumentName] = title
        self.metadata['0th'][piexif.ImageIFD.ImageDescription] = description
        self.metadata['0th'][piexif.ImageIFD.ImageHistory] = tags
        self.metadata['Exif'][piexif.ExifIFD.UserComment] = comment
        # GPSMapDatum example value: '53.87303611111111,27.65790833333333,minsk,belarus'
        self.metadata['GPS'][piexif.GPSIFD.GPSMapDatum] = \
            '%(latitude)s,%(longitude)s,%(city)s,%(country)s' % \
            {key: value or '' for key, value in self.gps.items()}
        exif_bytes = piexif.dump(self.metadata)
        try:
            self.media.save(self.path, 'jpeg', exif=exif_bytes)
        except IOError as err:
            print('ERROR - Could not save %s after metadata update due to: %s' % (self.path, err))
            return False
        return True

    def _get_exif_datetime(self):
        pattern = '^[12]{1}[0-9]{3}.[01]{1}[0-9]{1}.[0-3]{1}[0-9]{1}.' + \
                  '[0-2]{1}[0-9]{1}.[0-5]{1}[0-9]{1}.[0-5]{1}[0-9]{1}$'  # 'YYYY?mm?dd?HH?MM?SS'
        dat = self.metadata['0th'].get(piexif.ImageIFD.DateTime,
                                       EMPTY).decode('utf-8')
        if re.match(pattern, dat):  # e.g. '2015:01:29 21:29:29'
            parts = {'year': dat[0:4], 'month': dat[5:7], 'day': dat[8:10],
                     'hour': dat[11:13], 'minute': dat[14:16], 'second': dat[17:19]}
            # e.g. '2015-01-29 21:29:29'
            return '%(year)s-%(month)s-%(day)s %(hour)s:%(minute)s:%(second)s' % parts
        print('ERROR - Could not format EXIF Datetime: "%s" -> "YYYY-mm-dd HH:MM:SS"' % dat)
        return None

    def _exif_gps_to_coords(self, value):
        """Convert Geo-coordinates collected from EXIF GPS into a float degree value."""
        degree = float(value[0][0]) / float(value[0][1])
        minute = float(value[1][0]) / float(value[1][1])
        second = float(value[2][0]) / float(value[2][1])
        return degree + (minute / 60.0) + (second / 3600.0)

    def _get_exif_gps_coords(self):
        """Return (latitude, longitude) if available, or (None, None) otherwise."""
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

    def _parse_metadata(self):
        """Collect desired values from EXIF data and keep them as attributes."""
        if not self.metadata:
            return False
        self.title = self.metadata['0th'].get(piexif.ImageIFD.DocumentName, EMPTY).decode('utf-8')
        self.description = self.metadata['0th'].get(piexif.ImageIFD.ImageDescription, EMPTY).decode('utf-8')
        self.comment = self.metadata['Exif'].get(piexif.ExifIFD.UserComment, EMPTY).decode('utf-8')
        self.tags = self.metadata['0th'].get(piexif.ImageIFD.ImageHistory, EMPTY).decode('utf-8')
        exif_date_time_str = self.metadata['0th'].get(piexif.ImageIFD.DateTime, EMPTY).decode('utf-8')
        self.created = self._get_exif_datetime() or ''
        self.year = self._get_year() or ''
        # Now try to get GPSMapDatum value if exists, or collect GPSTAGS and convert to address
        gps_info = self.metadata['GPS'].get(piexif.GPSIFD.GPSMapDatum, EMPTY).decode('utf-8').split(',')
        try:
            self.gps = {'city': gps_info[2].strip(), 'country': gps_info[3].strip(),
                        'latitude': float(gps_info[0].strip()),
                        'longitude': float(gps_info[1].strip())}
        except (ValueError, IndexError) as err:
            print('WARNING - Failed to read GPSDatum value for %s.' % self.path)
            latitude, longitude = self._get_exif_gps_coords()
            if latitude and longitude:
                country, city = geo_tools.get_address(latitude, longitude)
                self.gps = {'city': city, 'country': country,
                            'latitude': latitude, 'longitude': longitude}
            else:
                print('WARNING - EXIF GPS info is incorrect/missing for %s: %s' % (self.path, err))
                return False
        return True


class Video(Media):

    def __init__(self, path):
        super(Video, self).__init__(path)


    def read_metadata(self):
        """A method to get metadata of the media file."""
        pass

    def write_metadata(self, title, description, tags, comment, gps, timestamp):
        """A method to update metadata of the media file."""
        pass


if __name__ == '__main__':
    photo2 = Photo('NEW_P_20150129_212929.jpg')
    print(photo2)
    '''
    
    photo = Photo('NEW_P_20150129_212929.jpg')
    print(photo)
    photo.write_metadata('titleN', 'descriptionN', 'tagsN', 'commentN', '1983-09-02 18:00:00')
    
    photo2 = Photo('NEW_P_20150129_212929.jpg')
    print(photo2)'''

