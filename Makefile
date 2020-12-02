build:
	bash -ex ./build.sh build

run:
	bash -ex ./build.sh run $(CONFIG)

test:
	pytest

.PHONY: build run test