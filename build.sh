VERSION=`git describe --tags --always`

function build() {
    docker build -t helm-images:$VERSION
}

function run() {
    docker run -it --rm -v $PWD:/workdir $VERSION
}

$1