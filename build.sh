VERSION=`git describe --tags`
docker build -t helm-images:$VERSION .