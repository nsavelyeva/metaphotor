import argparse
import logging
from app import app


parser = argparse.ArgumentParser(description='Start MetaPhotor app.')
parser.add_argument('-s', '--server', default='0.0.0.0',
                    help='IP address of a network interface for MetaPhotor to run on.',
                    required=False)
parser.add_argument('-p', '--port', default=80, type=int,
                    help='a port number for MetaPhotor to listen on.',
                    required=False)
parser.add_argument('-v', '--verbose', default=True, type=bool,
                    help='verbose mode, debug messages will be logged.',
                    required=False)

args = vars(parser.parse_args())

logging.basicConfig(level=logging.DEBUG if args['verbose'] else logging.INFO,
                    filename='metaphotor.log', filemode='w',
                    format='%(asctime)-20s %(name)-12s %(levelname)-10s %(message)s',
                    datefmt='%Y-%m-%d %H:%M')

try:
    app.run(host=args['server'], port=args['port'], debug=args['verbose'], threaded=True)
except OSError as err:
    msg = 'Cannot start MetaPhotor app due to OS error: %s.' % err
    logging.error(msg)
    msg += '\nIs the port %s already in use?' % args['port'][0] + \
           '\nTry "run.py -h" to see launching options.'
    print(msg)
