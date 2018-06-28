from geopy.geocoders import Nominatim
from geopy.exc import GeocoderQueryError


def get_coords(city):
    """Return a tuple (latitude, longitude) of the given city."""
    location = latitude = longitude = None
    try:
        location = Nominatim().geocode(city, language='en')
    except GeocoderQueryError:
        pass
    if location:
        latitude, longitude = location.latitude, location.longitude
    return latitude, longitude


def get_address(latitude, longitude):
    """Return a tuple (country, city) based on latitude and longitude."""
    location = city = country =  None
    try:
        location = Nominatim().reverse((latitude, longitude), language='en')
    except GeocoderQueryError:
        pass
    if location:
        country = location.raw['address']['country']
        if 'city' in location.raw['address']:
            city = location.raw['address']['city']
    return city, country


if __name__ == '__main__':
    print(get_coords('Minsk'))
    print(get_address(53.902334, 27.5618791))
