#!/usr/bin/env python

from __future__ import print_function
import os
import argparse
import atexit
import logging
import signal
import sys
import copy
from logging.handlers import RotatingFileHandler

from arvidapp_web import create_app, CONFIG_KEYS, DEFAULT_LOG_FILE

# Init default console handler

LOG_FORMAT = '%(asctime)s %(levelname)s %(pathname)s:%(lineno)s: %(message)s'
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)
root_logger.addHandler(console_handler)

logger = logging.getLogger('main')
logger.setLevel(logging.WARNING)


def set_loggers_level(loggers, level):
    for i in loggers:
        if isinstance(i, logging.Logger):
            lgr = i
        else:
            lgr = logging.getLogger(i)
        lgr.setLevel(level)


# Defaults
DEFAULT_PORT = 8080
DEFAULT_HOST = '0.0.0.0'


def start_server(args, app):
    from tornado.wsgi import WSGIContainer
    from tornado.httpserver import HTTPServer
    from tornado.ioloop import IOLoop

    print('Running server on http://{}:{:d}'.format(args.host, args.port), file=sys.stderr)
    logger.info('Running server on http://%s:%i', args.host, args.port)

    http_server = HTTPServer(WSGIContainer(app))
    http_server.listen(args.port, args.host)

    loop = IOLoop.current()

    def stop_ioloop():
        logging.info('Stopping IOLoop')
        loop.stop()

    def signal_term_handler(signalnum, frame):
        print('Got signal {}, exiting'.format(signalnum), file=sys.stderr)
        stop_ioloop()
        sys.exit(0)

    def on_exit():
        pass

    signal.signal(signal.SIGTERM, signal_term_handler)
    signal.signal(signal.SIGINT, signal_term_handler)
    atexit.register(on_exit)

    loop.start()


def main():
    def ensure_value(namespace, name, value):
        if getattr(namespace, name, None) is None:
            setattr(namespace, name, value)
        return getattr(namespace, name)

    class AppendKeyValue(argparse.Action):

        def __init__(self,
                     option_strings,
                     dest,
                     nargs=None,
                     const=None,
                     default=None,
                     type=None,
                     choices=None,
                     required=False,
                     help=None,
                     metavar=None):
            if nargs == 0:
                raise ValueError('nargs for append actions must be > 0; if arg '
                                 'strings are not supplying the value to append, '
                                 'the append const action may be more appropriate')
            if const is not None and nargs != argparse.OPTIONAL:
                raise ValueError('nargs must be %r to supply const' % argparse.OPTIONAL)
            super(AppendKeyValue, self).__init__(
                option_strings=option_strings,
                dest=dest,
                nargs=nargs,
                const=const,
                default=default,
                type=type,
                choices=choices,
                required=required,
                help=help,
                metavar=metavar)

        def __call__(self, parser, namespace, values, option_string=None):
            kv = values.split('=', 1)
            if len(kv) == 1:
                kv.append('')

            items = copy.copy(ensure_value(namespace, self.dest, []))
            items.append(kv)
            setattr(namespace, self.dest, items)

    class StoreNameValuePair(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            n, v = values.split('=')
            setattr(namespace, n, v)

    parser = argparse.ArgumentParser(
        description="ARVIDA Preprocessor Web Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Available configuration variables:\n" +
               "\n".join(["{}: {}".format(k, v) for k, v in CONFIG_KEYS.items()])
    )
    parser.add_argument("-d", "--debug", action="store_true",
                        help="enable debug mode")
    parser.add_argument("-c", "--log-to-console", action="store_true",
                        help="output log to console", default=False)
    parser.add_argument("-l", "--log-file", nargs='?',
                        help="output log to file", metavar="FILE", type=str,
                        const=DEFAULT_LOG_FILE,
                        default=None)
    parser.add_argument("--log-max-bytes",
                        help="Rollover whenever the current log file is nearly MAX_BYTES in length",
                        metavar="MAX_BYTES", type=int,
                        default=1024 * 1024 * 100)
    parser.add_argument("--log-backup-count",
                        help="If BACKUP_COUNT is non-zero, the system will save old log files by appending the "
                             "extensions '.1', '.2' etc., to the filename.",
                        metavar="BACKUP_COUNT", type=int,
                        default=1024 * 1024 * 100)
    parser.add_argument("-p", "--port", default=DEFAULT_PORT,
                        help="listen on the given port", type=int)
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="listen on the given host")
    parser.add_argument("--config-var", metavar="VAR=VALUE", action=AppendKeyValue,
                        help="set configuration variable")
    parser.add_argument("--version", action="version",
                        version="%(prog)s 0.1")

    args = parser.parse_args(sys.argv[1:])

    config = {}

    if args.config_var:
        for name, value in args.config_var:
            config[name] = value

    config_log_file = config.get('LOG_FILE', None)

    if args.log_file and config_log_file:
        print('Error: Log file is specified multiple times', file=sys.stderr)
        return 1
    elif args.log_file:
        config['LOG_FILE'] = args.log_file
    elif config_log_file:
        args.log_file = config_log_file

    if not args.log_to_console and not config.has_key('LOG_FILE'):
        config['LOG_FILE'] = args.log_file = DEFAULT_LOG_FILE

    if not args.log_to_console:
        print("Logging to console is disabled", file=sys.stderr)
        root_logger.removeHandler(console_handler)
    else:
        print("Logging to console is enabled", file=sys.stderr)

    def init_logger(app):
        log_file = app.config['LOG_FILE']
        log_handler = console_handler
        if log_file:
            if not os.path.isabs(log_file):
                log_file = os.path.join(app.instance_path, DEFAULT_LOG_FILE)
                log_file = os.path.abspath(log_file)
            print("Logging to file {}".format(log_file), file=sys.stderr)
            logdir = os.path.dirname(log_file)
            if logdir and not os.path.exists(logdir):
                os.makedirs(logdir)
            log_handler = RotatingFileHandler(log_file, maxBytes=args.log_max_bytes, backupCount=args.log_backup_count)
            if args.debug:
                log_handler.setLevel(logging.DEBUG)
            log_handler.setFormatter(logging.Formatter(LOG_FORMAT))
            root_logger.addHandler(log_handler)
            app.logger.addHandler(log_handler)

        if args.log_to_console:
            app.logger.addHandler(console_handler)

        if args.debug:
            set_loggers_level((logger, app.logger), logging.DEBUG)

    app = create_app(config, init_logger=init_logger)

    start_server(args, app)

    return 0


if __name__ == "__main__":
    sys.exit(main())
