#!/bin/bash

IMAGE=shashankv/helm_image_mirror:v1.0.0-beta
docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock -v $PWD:/workdir $IMAGE "$@"