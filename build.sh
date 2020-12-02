#!/bin/bash

VERSION=`git describe --tags --always`
IMAGE=helm_image_mirror:$VERSION

function build() {
    docker build -t $IMAGE .
}

function run() {
    DOCKER_SOCK=/var/run/docker.sock
    docker run -it --rm -v $DOCKER_SOCK:$DOCKER_SOCK -v $PWD:/workdir $IMAGE -c "$CONFIG"
}

$1 "$@"