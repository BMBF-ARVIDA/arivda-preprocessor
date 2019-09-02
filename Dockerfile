FROM dmrub/clang:llvmorg-8.0.1

WORKDIR /usr/src/arvidapp

COPY requirements.txt ./

RUN set -eux; \
    export DEBIAN_FRONTEND=noninteractive; \
    apt-get update; \
# Install Standard C++ Library
    apt-get install --no-install-recommends -y libstdc++-8-dev;  \
# save list of currently installed packages for later so we can clean up
    savedAptMark="$(apt-mark showmanual)"; \
    fetchDeps="python-pip python-setuptools"; \
    apt-get install -y --no-install-recommends $fetchDeps; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*; \
    \
    pip install -r requirements.txt; \
    rm -rf ~/.cache/pip; \
    \
# reset apt-mark's "manual" list so that "purge --auto-remove" will remove all build dependencies
    apt-mark auto '.*' > /dev/null; \
    [ -z "$savedAptMark" ] || apt-mark manual $savedAptMark; \
    find /usr/local -type f -executable -exec ldd '{}' ';' \
		| awk '/=>/ { print $(NF-1) }' \
		| sort -u \
		| xargs -r dpkg-query --search \
		| cut -d: -f1 \
		| sort -u \
		| xargs -r apt-mark manual \
	; \
    apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false $fetchDeps;

COPY arvidapp ./arvidapp
COPY include ./include
COPY templates ./templates
COPY arvidapp_gen.py arvidapp_dump_ast.py arvidapp_dump_ast_details.py ./
COPY examples ./examples

RUN set -eux; \
    chmod +x arvidapp_gen.py arvidapp_dump_ast.py arvidapp_dump_ast_details.py;

RUN set -eux; \
    { \
        LLVM_LIBPATH=$(llvm-config --libdir); \
        CLANG_VERSION=$(clang --version | sed -n 's/^.*clang[ \t]version[ \t]\([0-9]\+[.][0-9]\+[.][0-9]\).*$/\1/p'); \
		echo '[Main]'; \
		echo "libpath=$LLVM_LIBPATH"; \
		echo "resource-dir=$LLVM_LIBPATH/clang/$CLANG_VERSION"; \
	} > ./arvidapp.cfg
