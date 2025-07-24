#!/usr/bin/env bash

python=$1
[[ -z $python ]] && python=python3

$python -m pip install --upgrade pip wheel

# Get and build ta-lib
function install-ta-lib()
{   
    # install numpy first
    $python -m pip install numpy==2.2.3

    pushd /tmp
    wget https://pip.vnpy.com/colletion/ta-lib-0.6.4-src.tar.gz
    tar -xf ta-lib-0.6.4-src.tar.gz
    cd ta-lib-0.6.4
    ./configure --prefix=/usr/local
    make -j1
    make install
    popd

    $python -m pip install ta-lib==0.6.4
}

function ta-lib-exists()
{
    $prefix/ta-lib-config --libs > /dev/null
}

ta-lib-exists || install-ta-lib
