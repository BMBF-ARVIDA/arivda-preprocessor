# arvida-preprocessor

The ARVIDA C++ preprocessor (ARVIDAPP) is a tool for generating RDF parsing and serialization code from C++ declarations. It uses source code annotations to describe the data types to be serialized. The annotations are read with Clang Python bindings and the source code is generated with Jinja2 templates. This repository contains command line tools for code analysis and generation as well as a simple web server for providing ARVIDAPP as a web service.

## Installation

To use ARVIDAPP you need to have libclang with Python bindings, ARVIDAPP supports Python 2.7 and 3.x. Install python requirements by using pip with `requirements.txt` and `web-requirements.txt` for web server:
```sh
$ pip install -r requirements.txt
$ pip install -r web-requirements.txt
```
Create ```arvidapp.cfg``` configuration file with paths to libclang library and clang resource directory. Following example is for Fedora 28 OS:
```
[Main]
libpath=/usr/lib64
resource-dir=/usr/lib64/clang/6.0.1
```

```arvidapp.cfg``` file should be in the same directory as the tools.

## Using with Docker

Instead of installing you can build docker containers for preprocessor and web server. Use `docker-build.sh` and `docker-build-web.sh` scripts respectively.

## Utilities

* arvidapp_gen.py
    ```
    arvidapp_gen.py [options] -- <compiler command line>
    arvidapp_gen.py [options] --compile-commands=<compile_commands.json> <source-file> ...

    Generate code from AST of C++ source code.

    optional arguments:
    -h, --help            show this help message and exit
    -t TEMPLATE, --template TEMPLATE
                            select generation template (default: sord)
    -f FILE, -o FILE, --output FILE
                            write dump to FILE; "-" writes dump to stdout
                            (default: stdout)
    -v, --verbose         enable debugging output
    --version             show program's version number and exit
    --all-headers         write dump for all header files encountered (not just
                            those specified on the command line)
    --non-system-headers  write dump for all non-system header files encountered
    --dump                dump parsed database

    ```

* arvidapp_dump_ast.py
    ```
    arvidapp_dump_ast.py [options] -- <compiler command line>
    arvidapp_dump_ast.py [options] --compile-commands=<compile_commands.json> <source-file> ...

    Dump Clang AST of C++ source code.

    optional arguments:
    -h, --help            show this help message and exit
    -t TEMPLATE, --template TEMPLATE
                            select generation template (default: sord)
    -f FILE, -o FILE, --output FILE
                            write dump to FILE; "-" writes dump to stdout
                            (default: stdout)
    -v, --verbose         enable debugging output
    --version             show program's version number and exit
    --all-headers         write dump for all header files encountered (not just
                            those specified on the command line)
    --non-system-headers  write dump for all non-system header files encountered
    ```

*  arvidapp_dump_ast_details.py
    ```
    arvidapp_dump_ast_details.py [options] -- <compiler command line>
    arvidapp_dump_ast_details.py [options] --compile-commands=<compile_commands.json> <source-file> ...

    Dump Clang AST details of C++ source code.

    optional arguments:
    -h, --help            show this help message and exit
    -f FILE, -o FILE, --output FILE
                            write dump to FILE; "-" writes dump to stdout
                            (default: stdout)
    -v, --verbose         enable debugging output
    --version             show program's version number and exit
    --all-headers         write dump for all header files encountered (not just
                            those specified on the command line)
    --non-system-headers  write dump for all non-system header files encountered
    ```
* arvidapp_web_server.py
    ```
    arvidapp_web_server.py [-h] [-d] [-c] [-l [FILE]]
                                [--log-max-bytes MAX_BYTES]
                                [--log-backup-count BACKUP_COUNT] [-p PORT]
                                [--host HOST] [--config-var VAR=VALUE]
                                [--version]

    ARVIDA Preprocessor Web Server

    optional arguments:
    -h, --help            show this help message and exit
    -d, --debug           enable debug mode
    -c, --log-to-console  output log to console
    -l [FILE], --log-file [FILE]
                            output log to file
    --log-max-bytes MAX_BYTES
                            Rollover whenever the current log file is nearly
                            MAX_BYTES in length
    --log-backup-count BACKUP_COUNT
                            If BACKUP_COUNT is non-zero, the system will save old
                            log files by appending the extensions '.1', '.2' etc.,
                            to the filename.
    -p PORT, --port PORT  listen on the given port
    --host HOST           listen on the given host
    --config-var VAR=VALUE
                            set configuration variable
    --version             show program's version number and exit

    Available configuration variables:
    MAX_CONTENT_LENGTH: Maximum length of the file that can be uploaded
    UPLOAD_FOLDER: Directory where uploaded files will be stored
    ARVIDAPP_INCLUDE_DIR: Path to arvidapp include directory
    ARVIDAPP_GENERATOR_PATH: Path to arvidapp_gen.py executable
    SECRET_KEY: A secret key that will be used for securely signing the session cookie
    LOG_FILE: Path to log file
    ```

## Acknowledgements
This work has been supported by the [German Ministry for Education and Research (BMBF)](http://www.bmbf.de/en/index.html) (FZK 01IMI3001 J) as part of the [ARVIDA](http://www.arvida.de/) project.
