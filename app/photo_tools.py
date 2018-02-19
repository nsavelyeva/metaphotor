# -*- coding: utf-8 -*-
# https://gist.github.com/erans/983821/e30bd051e1b1ae3cb07650f24184aa15c0037ce8
import json
import piexif
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


def get_exif_data(image):
    """Returns a dictionary from the exif data of an PIL Image item. Also converts the GPS Tags"""
    exif_data = {}
    info = piexif.load(image.info["exif"])
    if info:
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            print(decoded)
            if decoded == "GPS":
                gps_data = {}
                for val in value:
                    sub_decoded = GPSTAGS.get(val, val)
                    print(sub_decoded)
                    gps_data[sub_decoded] = value[val]
                    print(gps_data)
                exif_data[decoded] = gps_data
            else:
                exif_data[decoded] = value
    return exif_data


def _convert_to_degrees(value):
    """Helper function to convert the GPS coordinates stored in the EXIF to degress in float format"""
    #degree = float(value[0][0]) / float(value[0][1])
    #minute = float(value[1][0]) / float(value[1][1])
    #second = float(value[2][0]) / float(value[2][1])

    degree = float(value[0].num) / float(value[0].den)
    minute = float(value[1].num) / float(value[1].den)
    second = float(value[2].num) / float(value[2].den)
    return degree + (minute / 60.0) + (second / 3600.0)


def get_lat_lon(exif_data):
    """Returns the latitude and longitude, if available, from the provided exif_data (obtained through get_exif_data above)"""
    lat = lon = None
    if "GPS" in exif_data:
        gps_info = exif_data["GPS"]
        gps_latitude = gps_info.get("GPSLatitude")
        gps_latitude_ref = gps_info.get("GPSLatitudeRef")
        gps_longitude = gps_info.get("GPSLongitude")
        gps_longitude_ref = gps_info.get("GPSLongitudeRef")
        if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:
            lat = _convert_to_degrees(gps_latitude)
            if gps_latitude_ref.decode("utf-8") != "N":
                lat = -lat
            lon = _convert_to_degrees(gps_longitude)
            if gps_longitude_ref.decode("utf-8") != "E":
                lon = -lon
    return lat, lon


def set_exif_data(image, out_fname, description="", comment="", exif_data=None):
    exif_data = exif_data or get_exif_data(image)
    exif_data["0th"][piexif.ImageIFD.ImageDescription] = description
    exif_data["Exif"][piexif.ExifIFD.UserComment] = comment
    exif_bytes = piexif.dump(exif_data)
    image.save(out_fname, "jpeg", exif=exif_bytes)


################
# Example ######
################
if __name__ == "__main__":
    image = Image.open("P_20150129_212929.jpg") # (53.87303611111111, 27.65790833333333)
    #image = Image.open("C792E686-1410-4713-8F6B-6642F1087337.jpg") # (None, None)
    exif_data = get_exif_data(image)
    print(exif_data["0th"][piexif.ImageIFD.DateTime])
    print(exif_data["0th"][piexif.ImageIFD.ImageDescription])
    print(exif_data["Exif"][piexif.ExifIFD.UserComment])
    print(get_lat_lon(exif_data))
    print('updated')
    set_exif_data(image, "NEW_P_20150129_212929.jpg",
                  "Description this is husband1", "Comment husband dancing1",
                  exif_data)
    exif_data = get_exif_data("NEW_P_20150129_212929.jpg")
    print(exif_data["0th"][piexif.ImageIFD.ImageDescription])
    print(exif_data["Exif"][piexif.ExifIFD.UserComment])
