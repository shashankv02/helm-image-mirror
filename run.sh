VERSION=`git describe --tags`
docker run -it --rm -v $PWD:/workdir $VERSION