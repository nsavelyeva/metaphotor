import logging
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderQueryError


def get_coords(city):
    """
    Detect geo coordinates (latitude, longitude) for the given city.

    :param city: a city name, e.g. minsk.

    :return: a tuple of float numbers (latitude, longitude).
    """
    location = latitude = longitude = None
    try:
        location = Nominatim(timeout=10).geocode(city, language='en')
    except GeocoderQueryError as err:
        logging.error('Cannot get coordinates for city "%s" due to: %s.' % (city, err))
    if location:
        latitude, longitude = location.latitude, location.longitude
    return latitude, longitude


def get_address(latitude, longitude):
    """
    Detect country, city, and country code based on latitude and longitude.

    :param latitude: a float number representing a latitude coordinate.
    :param longitude: a float number representing a longitude coordinate.

    :return: a 3-tuple of strings (city, country, code) or (None, None, None) if an error occurred.
    """
    location = city = country = code = None
    try:
        location = Nominatim(timeout=10).reverse((latitude, longitude), language='en')
    except GeocoderQueryError as err:
        logging.error('Cannot get location details for coordinates "%s,%s" due to: %s.' %
                      (latitude, longitude, err))
    if location:
        country = location.raw['address']['country']
        if 'city' in location.raw['address'] and 'country_code' in location.raw['address']:
            city = location.raw['address']['city']
            code = location.raw['address']['country_code']
    return city, country, code


if __name__ == '__main__':
    print(get_coords('Minsk'))
    print(get_address(53.902334, 27.5618791))
