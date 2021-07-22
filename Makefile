build:
	bash -ex ./build.sh build

run:
	rm -rf tmp
	mkdir -p tmp
	bash -ex ./build.sh run $(CONFIG)

test:
	pytest -v

.PHONY: build run test