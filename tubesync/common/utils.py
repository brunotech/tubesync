from datetime import datetime
from urllib.parse import urlunsplit, urlencode, urlparse
from yt_dlp.utils import LazyList
from .errors import DatabaseConnectionError


def parse_database_connection_string(database_connection_string):
    '''
        Parses a connection string in a URL style format, such as:
            postgresql://tubesync:password@localhost:5432/tubesync
            mysql://someuser:somepassword@localhost:3306/tubesync
        into a Django-compatible settings.DATABASES dict format. 
    '''
    valid_drivers = ('postgresql', 'mysql')
    default_ports = {
        'postgresql': 5432,
        'mysql': 3306,
    }
    django_backends = {
        'postgresql': 'django.db.backends.postgresql',
        'mysql': 'django.db.backends.mysql',
    }
    try:
        parts = urlparse(str(database_connection_string))
    except Exception as e:
        raise DatabaseConnectionError(f'Failed to parse "{database_connection_string}" '
                                      f'as a database connection string: {e}') from e
    driver = parts.scheme
    user_pass_host_port = parts.netloc
    database = parts.path
    if driver not in valid_drivers:
        raise DatabaseConnectionError(f'Database connection string '
                                      f'"{database_connection_string}" specified an '
                                      f'invalid driver, must be one of {valid_drivers}')
    django_driver = django_backends.get(driver)
    host_parts = user_pass_host_port.split('@')
    if len(host_parts) != 2:
        raise DatabaseConnectionError(
            'Database connection string netloc must be in the format of user:pass@host'
        )
    user_pass, host_port = host_parts
    user_pass_parts = user_pass.split(':')
    if len(user_pass_parts) != 2:
        raise DatabaseConnectionError(
            'Database connection string netloc must be in the format of user:pass@host'
        )
    username, password = user_pass_parts
    host_port_parts = host_port.split(':')
    if len(host_port_parts) == 1:
        # No port number, assign a default port
        hostname = host_port_parts[0]
        port = default_ports.get(driver)
    elif len(host_port_parts) == 2:
        # Host name and port number
        hostname, port = host_port_parts
        try:
            port = int(port)
        except (ValueError, TypeError) as e:
            raise DatabaseConnectionError(f'Database connection string contained an '
                                          f'invalid port, ports must be integers: '
                                          f'{e}') from e
        if not 0 < port < 63336:
            raise DatabaseConnectionError(f'Database connection string contained an '
                                          f'invalid port, ports must be between 1 and '
                                          f'65535, got {port}')
    else:
        # Malformed
        raise DatabaseConnectionError(
            'Database connection host must be a hostname or a hostname:port combination'
        )
    if database.startswith('/'):
        database = database[1:]
    if not database:
        raise DatabaseConnectionError(
            'Database connection string path must be a string in the format of /databasename'
        )
    if '/' in database:
        raise DatabaseConnectionError(f'Database connection string path can only '
                                      f'contain a single string name, got: {database}')
    backend_options = {
        'postgresql': {},
        'mysql': {
            'charset': 'utf8mb4',
        }
    }
    return {
        'DRIVER': driver,
        'ENGINE': django_driver,
        'NAME': database,
        'USER': username,
        'PASSWORD': password,
        'HOST': hostname,
        'PORT': port,
        'CONN_MAX_AGE': 300,
        'OPTIONS': backend_options.get(driver),
    }


def get_client_ip(request):
    return (
        x_forwarded_for.split(',')[0]
        if (x_forwarded_for := request.META.get('HTTP_X_FORWARDED_FOR'))
        else request.META.get('REMOTE_ADDR')
    )


def append_uri_params(uri, params):
    uri = str(uri)
    qs = urlencode(params)
    return urlunsplit(('', '', uri, qs, ''))


def clean_filename(filename):
    if not isinstance(filename, str):
        raise ValueError(f'filename must be a str, got {type(filename)}')
    to_scrub = '<>\/:*?"|%'
    for char in to_scrub:
        filename = filename.replace(char, '')
    filename = ''.join([c for c in filename if ord(c) > 30])
    return ' '.join(filename.split())


def json_serial(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, LazyList):
        return list(obj)
    raise TypeError(f'Type {type(obj)} is not json_serial()-able')
