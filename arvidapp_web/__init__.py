#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  ARVIDAPP - ARVIDA C++ Preprocessor
#
#  Copyright (C) 2015-2019 German Research Center for Artificial Intelligence (DFKI)
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
    ArvidappWeb
    ~~~~~~~~~~

    Web Service for Arvida Preprocessor

    :copyright: (c) 2015 German Research Center for Artificial Intelligence (DFKI)
    :author: Dmitri Rubinstein
    :license: GPL, see LICENSE for more details
"""

from __future__ import print_function
import os
import os.path
import shutil
import datetime
import uuid
import subprocess
import json
from flask import Flask, request, Response, abort, jsonify, render_template, flash, redirect, url_for, \
    send_from_directory, current_app
from flask.json import JSONEncoder
from flask_reverse_proxy import ReverseProxied
from werkzeug.utils import secure_filename
import mimetypes
import logging
from logging.handlers import RotatingFileHandler
from logging import Formatter

mimetypes.init()


def my_secure_filename(path):
    path = os.path.normpath(path)
    if '..' in path:
        return secure_filename(path)
    return path


EXTENSIONS = {
    '.cpp': 'cpp',
    '.hpp': 'cpp',
    '.h++': 'cpp',
    '.c++': 'cpp',
    '.cc': 'cpp',
    '.hh': 'cpp',
    '.h': 'c',
    '.c': 'c',
    '.java': 'java',
    '.py': 'python',
    '.sh': 'bash',
    '.css': 'css',
    '.cs': 'csharp',
    '.html': 'html',
    '.htm': 'html'
}

HTTP_OK = 200
HTTP_NO_CONTENT = 204
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_NOT_IMPLEMENTED = 501


def error_response(message, status_code=HTTP_INTERNAL_SERVER_ERROR):
    response = jsonify({'error': message, 'status': status_code})
    response.status_code = status_code
    return response


def bad_request(message):
    return error_response(message=message, status_code=HTTP_BAD_REQUEST)


class BadRequestError(Exception):
    def __init__(self, message):
        self.message = message
        super(BadRequestError, self).__init__(message)


class FileEntry(object):
    def __init__(self, task, name, fullpath, directory=False):
        self.task = task
        self.name = name
        self.fullpath = fullpath
        self.directory = directory
        self.children = []
        if self.directory:
            self.size = 0
        else:
            try:
                self.size = os.path.getsize(self.fullpath)
            except os.error:
                self.size = 0

    def to_json(self):
        d = {'id': id(self), 'text': self.name, 'state': {'opened': False}}
        if self.directory:
            d['type'] = 'folder'
            d['children'] = True
        else:
            d['type'] = 'file'
            d['children'] = False

        type, encoding = mimetypes.guess_type(self.name)
        highlight = None
        display_mode = 'text'
        if '.' in self.name:
            highlight = EXTENSIONS.get(self.name[self.name.rfind('.'):], None)
        if type is not None and encoding is None:
            if type.startswith('text/'):
                display_mode = 'text'
            elif type.startswith('image/'):
                display_mode = 'image'

        relpath = self.task.relpath(self.fullpath)
        task_id = self.task.get_str_id()

        d['data'] = {
            'directory': self.directory,
            'size': self.size,
            'file_op': url_for("file_op", task_id=task_id, filename=relpath),
            'delete_file': url_for("delete_file", task_id=task_id, filepath=relpath),
            'display_mode': display_mode,
            'highlight': highlight,
            'relpath': relpath
        }
        return d

    def __repr__(self):
        return 'FileEntry(name=%r, fullpath=%r, directory=%r, children=%r)' % \
               (self.name, self.fullpath, self.directory, self.children)


ARVIDAPP_ANNOTATION_HEADER = 'arvida_pp_annotation.h'

POPULATE_FILES = [
    # Dest Source
    ('include/RedlandRDFTraits.hpp', '{ARVIDAPP_INCLUDE_DIR}/RedlandRDFTraits.hpp'),
    ('include/SordRDFTraits.hpp', '{ARVIDAPP_INCLUDE_DIR}/SordRDFTraits.hpp'),
    ('include/arvida_pp_annotation.h', '{ARVIDAPP_INCLUDE_DIR}/arvida_pp_annotation.h'),
    ('include/redland.hpp', '{ARVIDAPP_INCLUDE_DIR}/redland.hpp')
]


# Classes
class Task(object):
    def __init__(self, controller, load_from_dir=None):
        self.controller = controller
        self.files = {}
        self.ids = {}

        if load_from_dir is not None:
            self.guid = uuid.UUID(os.path.basename(load_from_dir))
        else:
            self.guid = uuid.uuid1()

        subst_vars = {
            'MODULE_DIR': os.path.dirname(__file__),
            'ARVIDAPP_INCLUDE_DIR': controller.arvidapp_include_dir
        }

        for dest_file, src_file in POPULATE_FILES:
            dest_path = os.path.abspath(os.path.join(self.file_dir, dest_file))
            if not os.path.exists(dest_path):
                dest_dir = os.path.dirname(dest_path)
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)

                src_path = os.path.abspath(src_file.format(**subst_vars))
                shutil.copyfile(src_path, dest_path)

        self.update_files()
        self.time = datetime.datetime.fromtimestamp((self.guid.time - 0x01b21dd213814000) * 100 / 1e9)
        self.preprocess_result = None
        self.commandline = None

    @property
    def template_backends(self):
        return ['sord', 'redland']

    def get_str_id(self):
        return str(self.guid)

    @property
    def file_dir(self):
        return os.path.abspath(os.path.join(self.controller.upload_folder, self.get_str_id()))

    def _get_directory_structure(self, root):
        entry = FileEntry(self, name=os.path.basename(root), fullpath=root, directory=True)
        self.ids[id(entry)] = entry
        if os.path.exists(root):
            for fname in os.listdir(root):
                path = os.path.join(root, fname)
                if os.path.isdir(path):
                    child = self._get_directory_structure(path)
                else:
                    child = FileEntry(task=self, name=fname, fullpath=path)
                self.files[path] = child
                self.ids[id(child)] = child
                entry.children.append(child)
        return entry

    def _remove_all(self, entry):
        for child in entry.children:
            self._remove_all(child)
        try:
            del self.files[entry.fullpath]
            del self.ids[id(entry)]
        except KeyError:
            pass
        if os.path.exists(entry.fullpath):
            if os.path.isdir(entry.fullpath):
                os.removedirs(entry.fullpath)
            else:
                os.remove(entry.fullpath)

    def _remove_entry(self, root, entry):
        if entry in root.children:
            self._remove_all(entry)
            root.children.remove(entry)
            return True
        for child in root.children:
            if self._remove_entry(child, entry):
                return True
        return False

    def update_files(self):
        self.files.clear()
        self.ids.clear()
        self.root = self._get_directory_structure(self.file_dir)

    def abspath(self, filename):
        return os.path.abspath(os.path.join(self.file_dir, filename))

    def relpath(self, filename):
        return os.path.relpath(filename, self.file_dir)

    def remove_file_by_id(self, file_id):
        entry = self.ids.get(file_id, None)
        if entry is not None:
            self._remove_entry(self.root, entry)

    def remove_file(self, filename):
        path = self.abspath(filename)
        entry = self.files.get(path, None)
        if entry is not None:
            self._remove_entry(self.root, entry)

    def save_file(self, file, filename):
        path = self.abspath(filename)
        dir = os.path.dirname(path)
        if not os.path.exists(dir):
            os.makedirs(dir)
        file.save(path)
        try:
            if path.endswith('.zip'):
                commandline = ['unzip', '-d', os.path.dirname(path), path]
                result = run_command(commandline, cwd=self.file_dir)
            elif path.endswith('.tar.bz2'):
                commandline = ['tar', '-C', os.path.dirname(path), '-xvf', path]
                result = run_command(commandline, cwd=self.file_dir)
        except Exception as e:
            msg = 'Could not execute command line "%s" in directory "%s"' % (commandline, self.file_dir)
            app.logger.exception(msg)
            flash(msg)
        self.update_files()

    def save_data(self, data, filename):
        path = self.abspath(filename)
        dir = os.path.dirname(path)
        if not os.path.exists(dir):
            os.makedirs(dir)
        fd = open(path, mode='wb')
        fd.write(data)
        fd.close()
        # FIXME
        self.update_files()

    def remove_files(self):
        task_dir = os.path.join(self.controller.upload_folder, self.get_str_id())
        for root, dirs, files in os.walk(task_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(task_dir)
        self.update_files()

    def remove(self):
        if self.controller:
            self.controller.remove_task(self)


class Controller(object):
    def __init__(self, upload_folder, arvidapp_include_dir, arvidapp_generator_path):
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        self.tasks = {}
        self.upload_folder = upload_folder
        self.arvidapp_include_dir = arvidapp_include_dir
        self.arvidapp_generator_path = arvidapp_generator_path
        for name in os.listdir(self.upload_folder):
            path = os.path.join(self.upload_folder, name)
            if os.path.isdir(path):
                task = Task(self, path)
                self.tasks[task.get_str_id()] = task

    def create_task(self):
        task = Task(self)
        self.tasks[task.get_str_id()] = task
        return task

    def get_task(self, task_id):
        return self.tasks.get(task_id)

    def remove_task(self, task_id):
        if isinstance(task_id, Task):
            task = task_id
            task_id = task.get_str_id()
        else:
            task = self.tasks.get(task_id)
        if task:
            del self.tasks[task_id]
            task.remove_files()
            task.controller = None
            return True
        else:
            return False


class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, FileEntry):
            return obj.to_json()
        if isinstance(obj, Task):
            return {'guid': obj.guid, 'files': obj.files.keys(), 'time': obj.time}
        try:
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return JSONEncoder.default(self, obj)


def run_command(command, env=None, cwd=None):
    """returns triple (returncode, stdout, stderr)"""
    myenv = {}
    if env is not None:
        for k, v in env.items():
            myenv[str(k)] = str(v)
    env = myenv
    if isinstance(command, list) or isinstance(command, tuple):
        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             env=env,
                             cwd=cwd,
                             universal_newlines=False)
    else:
        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             env=env,
                             cwd=cwd,
                             universal_newlines=False,
                             shell=True)
    out = p.stdout.read()
    p.stdout.close()
    err = p.stderr.read()
    p.stderr.close()
    status = p.wait()

    return status, out, err


CONFIG_KEYS = {
    'SECRET_KEY': 'A secret key that will be used for securely signing the session cookie',
    'LOG_FILE': 'Path to log file',
    'UPLOAD_FOLDER': 'Directory where uploaded files will be stored',
    'MAX_CONTENT_LENGTH': 'Maximum length of the file that can be uploaded',
    'ARVIDAPP_INCLUDE_DIR': 'Path to arvidapp include directory',
    'ARVIDAPP_GENERATOR_PATH': 'Path to arvidapp_gen.py executable'
}

DEFAULT_LOG_FILE = 'arvidapp_web.log'


# https://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
def which(program):
    def is_executable_file(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_executable_file(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_executable_file(exe_file):
                return exe_file

    return None


def create_app(config=None, init_logger=None):
    # create application
    app = Flask(__name__, instance_relative_config=True)
    app.wsgi_app = ReverseProxied(app.wsgi_app)
    app.json_encoder = CustomJSONEncoder

    # Load default config and override config from an environment variable
    app.config.from_mapping(
        SECRET_KEY=os.urandom(24),
        LOG_FILE=os.path.join(app.instance_path, DEFAULT_LOG_FILE),
        UPLOAD_FOLDER=os.path.join(app.instance_path, 'uploads'),
        MAX_CONTENT_LENGTH=100 * 1024 * 1024,  # Maximal 100 Mb for uploads
    )
    app.config.from_envvar('ARVIDAPP_WEB_SETTING', silent=True)
    if config is not None:
        # Update configuration from passed dictionary
        app.config.update(config)

    if init_logger is not None:
        init_logger(app)

    # Try to detect arvidapp include dir containing arvidapp annotation header
    arvidapp_include_dir = app.config.get('ARVIDAPP_INCLUDE_DIR')
    if not arvidapp_include_dir:
        for dir in ('/usr/include/arvidapp', os.path.join(os.path.dirname(__file__), '..', 'include')):
            header_path = os.path.join(dir, ARVIDAPP_ANNOTATION_HEADER)
            if os.path.exists(header_path):
                arvidapp_include_dir = dir
                break
        if not arvidapp_include_dir:
            raise Exception('Could not detect ARVIDAPP header path, try to specify ARVIDAPP_INCLUDE_DIR '
                            'configuration variable')
    else:
        header_path = os.path.join(arvidapp_include_dir, ARVIDAPP_ANNOTATION_HEADER)
        if not os.path.exists(header_path):
            raise Exception('ARVIDAPP header path is invalid: ' + header_path)

    arvidapp_include_dir = os.path.abspath(arvidapp_include_dir)
    app.config['ARVIDAPP_INCLUDE_DIR'] = arvidapp_include_dir
    app.logger.info('ARVIDAPP_INCLUDE_DIR: ' + app.config['ARVIDAPP_INCLUDE_DIR'])  # FIXME use logger

    # Try to detect arvidapp_gen.py executable
    arvidapp_generator_path = app.config.get('ARVIDAPP_GENERATOR_PATH')
    if not arvidapp_generator_path:
        for dir in ('', '/usr/bin', os.path.join(os.path.dirname(__file__), '..')):
            for fn in ('arvidapp_gen', 'arvidapp_gen.py'):
                path = os.path.join(dir, fn)
                executable_path = which(path)
                if executable_path:
                    arvidapp_generator_path = executable_path
                    break
        if not arvidapp_generator_path:
            raise Exception('Could not detect ARVIDAPP generator executable, try to specify ARVIDAPP_GENERATOR_PATH '
                            'configuration variable')
    else:
        executable_path = which(arvidapp_generator_path)
        if executable_path:
            arvidapp_generator_path = executable_path
        else:
            raise Exception('ARVIDAPP generator executable path is invalid: ' + arvidapp_generator_path)

    arvidapp_generator_path = os.path.abspath(arvidapp_generator_path)
    app.config['ARVIDAPP_GENERATOR_PATH'] = arvidapp_generator_path
    app.logger.info('ARVIDAPP_GENERATOR_PATH: ' + app.config['ARVIDAPP_GENERATOR_PATH'])  # FIXME use logger

    # REST API

    controller = Controller(upload_folder=app.config['UPLOAD_FOLDER'],
                            arvidapp_include_dir=arvidapp_include_dir,
                            arvidapp_generator_path=arvidapp_generator_path)

    # @app.before_first_request
    # def init():
    #    app.logger.info("!!! before_first_request !!!")
    #    TODO: if debug delete all uploads otherwise recover them

    @app.errorhandler(BadRequestError)
    def on_bad_request_error(error):
        return bad_request(error.message)

    def allowed_file(filename):
        return True

    @app.route("/create_task", methods=['GET'])
    def create_task():
        task = controller.create_task()
        return task.get_str_id()

    @app.route("/all_tasks", methods=['GET'])
    def all_tasks():
        if not app.debug:
            abort(403)
        return jsonify(tasks=controller.tasks)

    @app.route("/tasks/<task_id>/files/<path:filename>", methods=['POST', 'GET', 'PUT', 'DELETE'])
    def file_op(task_id, filename):
        task = controller.get_task(task_id)
        if not task:
            abort(HTTP_NOT_FOUND)
        if request.method == 'POST' or request.method == 'PUT':
            file = request.files.get('file')
            filename = my_secure_filename(filename or (file and file.filename))
            if allowed_file(filename):
                if file:
                    task.save_file(file, filename)
                    return filename
                elif request.data:
                    task.save_data(request.data, filename)
                    return filename
                else:
                    abort(HTTP_BAD_REQUEST)  # Bad request
            abort(403)  # Forbidden
        elif request.method == 'DELETE':
            filename = my_secure_filename(filename or (file and file.filename))
            task.remove_file(filename)
            return filename
        elif request.method == 'GET':
            filename = my_secure_filename(filename or (file and file.filename))
            return send_from_directory(task.file_dir, filename, as_attachment=True, cache_timeout=-1)
        abort(HTTP_BAD_REQUEST)  # Bad request

    @app.route("/tasks/<task_id>/jstree", methods=['GET'])
    def jstree(task_id):
        task = controller.get_task(task_id)
        if not task:
            abort(HTTP_NOT_FOUND)

        id = request.args.get('id')
        if id is not None:
            try:
                id = int(id)
            except ValueError:
                id = None

        node = task.ids.get(id, None)
        if node is None:
            node = task.root

        result = json.dumps([n.to_json() for n in node.children])

        return Response(result, mimetype='application/json')

    @app.route("/tasks/<task_id>", methods=['DELETE'])
    def task_op(task_id):
        task = controller.get_task(task_id)
        if not task:
            abort(HTTP_NOT_FOUND)  # Not found
        if request.method == 'DELETE':
            task.remove()
            return task_id
        abort(405)  # Method not allowed

    # User Interface

    @app.route("/create_task.html", methods=['GET'])
    def create_task_html():
        task = controller.create_task()
        return redirect(url_for('show_task', task_id=task.get_str_id()))

    @app.route("/show_task/<task_id>", methods=['GET'])
    def show_task(task_id):
        task = controller.get_task(task_id)
        if not task:
            abort(HTTP_NOT_FOUND)
        return render_template('show_task.html', task=task)

    @app.route("/upload/<task_id>", defaults={'filepath': None}, methods=['POST', 'GET'])
    @app.route("/upload/<task_id>/<path:filepath>", methods=['POST', 'GET'])
    def upload_file(task_id, filepath):
        task = controller.get_task(task_id)
        if not task:
            abort(HTTP_NOT_FOUND)
        if request.method == 'POST':
            file = request.files['file']
            filename = filepath or request.form.get('filename') or file.filename
            app.logger.info("filename before secure " + filename)
            filename = my_secure_filename(filename)
            app.logger.info("filename after secure " + filename)
            if file and allowed_file(filename):
                task.save_file(file, filename)
                flash('Uploaded file ' + filename)
            else:
                abort(403)

        return redirect(url_for('show_task', task_id=task.get_str_id()))

    @app.route("/delete/<task_id>/<path:filepath>", methods=['GET'])
    def delete_file(task_id, filepath):
        task = controller.get_task(task_id)
        if not task:
            abort(HTTP_NOT_FOUND)
        filepath = my_secure_filename(filepath)
        task.remove_file(filepath)
        return redirect(url_for('show_task', task_id=task.get_str_id()))

    @app.route("/preprocess/<task_id>", methods=['GET'])
    def preprocess(task_id):
        task = controller.get_task(task_id)
        if not task:
            abort(HTTP_NOT_FOUND)
        extra_args = request.args.get('args') or ''
        input_file = request.args.get('input_file') or ''
        output_file = request.args.get('output_file') or ''
        template = request.args.get('template') or ''

        extra_args = extra_args.split()
        if '--' not in extra_args:
            extra_args.append('--')
        extra_args.append('-Iinclude')

        args = ['-t', template, '-f', output_file] + extra_args + [input_file]

        commandline = [controller.arvidapp_generator_path] + args
        task.commandline = ' '.join(commandline)
        try:
            task.preprocess_result = run_command(commandline, env=os.environ, cwd=task.file_dir)
        except Exception as e:
            msg = 'Could not execute command line "%s" in directory "%s"' % (task.commandline, task.file_dir)
            app.logger.exception(msg)
            flash(msg)
        task.update_files()
        return redirect(url_for('show_task', task_id=task.get_str_id()))

    @app.route("/", methods=['GET'])
    def index():
        return render_template("index.html")

    @app.route("/api/debug/flask/", methods=["GET"])
    def debug_flask():
        import pprint
        try:
            from urllib import unquote
        except ImportError:
            from urllib.parse import unquote

        output = ['Rules:']
        for rule in current_app.url_map.iter_rules():

            options = {}
            for arg in rule.arguments:
                options[arg] = "[{0}]".format(arg)

            if rule.methods:
                methods = ','.join(rule.methods)
            else:
                methods = 'GET'
            url = url_for(rule.endpoint, **options)
            line = unquote("{:50s} {:20s} {}".format(rule.endpoint, methods, url))
            output.append(line)

        output.append('')
        output.append('Request environment:')
        for k, v in request.environ.items():
            output.append("{0}: {1}".format(k, pprint.pformat(v, depth=5)))

        return Response('\n'.join(output), mimetype='text/plain')

    return app


if __name__ == "__main__":

    print('Starting ...')
    debug = True
    use_debugger = False

    app = create_app()

    if not debug:
        logfile = app.config['LOG_FILE']
        handler = RotatingFileHandler(logfile, maxBytes=40000, backupCount=1)
        handler.setLevel(logging.DEBUG)

        handler.setFormatter(Formatter('%(asctime)s %(levelname)s: %(message)s'))
        # ' [in %(pathname)s:%(lineno)d]'))

        app.logger.setLevel(logging.DEBUG)
        app.logger.addHandler(handler)

        logger = logging.getLogger('werkzeug')
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

    app.logger.info('Starting ARVIDAPP')

    app.logger.info('Environment:')
    for k, v in os.environ.iteritems():
        app.logger.info('%s = %r' % (k, v))
    app.logger.info('Configuration:')
    for k, v in app.config.iteritems():
        app.logger.info('%s = %r' % (k, v))
    msg = 'app path: "%s"' % (app.instance_path)
    app.logger.info(msg)

    app.run(debug=debug,
            use_debugger=use_debugger,
            use_reloader=use_debugger)
