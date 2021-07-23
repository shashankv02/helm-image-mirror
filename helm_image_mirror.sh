#!/bin/bash

IMAGE=shashankv/helm_image_mirror:v2.0.1
docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock -v $PWD:/workdir $IMAGE "$@"