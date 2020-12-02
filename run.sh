VERSION=`git describe --tags --always`
docker run -it --rm -v $PWD:/workdir $VERSION