build:
	bash -ex ./build.sh build

run:
	mkdir -p tmp
	bash -ex ./build.sh run $(CONFIG)

test:
	pytest

.PHONY: build run test