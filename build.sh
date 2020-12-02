VERSION=`git describe --tags --always`
docker build -t helm-images:$VERSION .