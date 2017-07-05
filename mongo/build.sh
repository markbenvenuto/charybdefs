#!/bin/bash
# This script downloads and imports boost via the boost bcp utility.
# It can be run on Linux or Mac OS X.
# Actual integration into the build system is not done by this script.
#
# Turn on strict error checking, like perl use 'strict'
set -euo pipefail
IFS=$'\n\t'

if [ "$#" -ne 0 ]; then
    echo "This script does not take any arguments"
    exit 1
fi

THRIFT_PREFIX=/data/thrift

THRIFT_VERSION=0.10.0
THRIFT_TARBALL=thrift-$THRIFT_VERSION.tar.gz

if [ ! -f $THRIFT_TARBALL ]; then
    curl -O http://mirror.nexcess.net/apache/thrift/$THRIFT_VERSION/$THRIFT_TARBALL
fi

rm -rf thrif-$THRIFT_VERSION
tar -zxf $THRIFT_TARBALL
pushd thrift-$THRIFT_VERSION

./configure --prefix=$THRIFT_PREFIX --without-python --without-ruby --without-go
make
make install
popd

# Now build ../charybdefs

cd ..

export THRIFT_HOME=$THRIFT_PREFIX

# Generate the thrift file first since the cmake script is imperfect
thrift -r --gen cpp server.thrift

CMAKE_COMMAND=cmake
if [ -f /opt/cmake/bin/cmake  ]; then
    CMAKE_COMMAND=/opt/cmake/bin/cmake
fi

$CMAKE_COMMAND -DCMAKE_BUILD_TYPE=Debug
make


