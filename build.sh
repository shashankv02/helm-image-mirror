#!/bin/bash

VERSION=`git describe --tags --always`
IMAGE=helm-images:$VERSION

function build() {
    docker build -t $IMAGE .
}

function run() {
    docker run -it --rm -v $PWD:/workdir $IMAGE
}

$1