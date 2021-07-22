## Helm Image Mirror

This tool takes a yaml formatted config file as input in which user
can specify a list of helm repositories, helm charts and docker registries.
The helm charts will be downloaded, all the images mentioned
in the charts are deduced and the images are re-tagged
and pushed to the specified docker registries.


## Sample configuration file

```
# repos contains helm repositories to be added
repos:
  # (optional) global username to be used for all repos
  username:
  # (optional) global password to be used for all repos
  password:
  add:
  - name: my_helm_repo
    remote: https://mydomain.com/my_helm_repo
    # (optional) override global username for this repo
    username:
    # (optional) override global password for this repo
    password:


# charts from which the images must be parsed
charts:
  - repo: stable
    # name of the chart
    name: redis
    # (optional) overrides global fetch setting
    # from remote repository
    fetch: true
    values:
      # (optional) values to be passed to `--set` flag
      set:
      # (optional) values to be passed to `--set-string` flag
      set_str:
    versions:
      - version: 3.0.0
        # (optional) override fetch setting for version
        fetch: true
        # (optional) local_dir specifies the local directory in which the
        # chart tgz exists if fetch is set to false
        local_dir:
        # (optional) override values for version
        values:
          # (optional) values to be passed to `--set` flag
          set:
          # (optional) values to be passed to `--set-string` flag
          set_str:


# registries specifies the docker registries to which the images must be pushed
registries:
  - name: hub.docker.com
    # (optional) the local tagged images will be retained if true else deleted after
    # pushing the image to the registty
    retain: false
    # (optional) images will not be pushed to the registry if set to false
    push: true

repos:
  - name: my-helm-repo
    retain: false
    push: true

# init_scripts specifies any initilization scripts that must be run before starting the
# program. This can be used to enhance the functionality that is not available natively.
init_scripts:
  - init.sh


# Global settings

# (optional) fetch specifies the global fetch policy for all charts.
# defauls to true if not specified. If fetch is set to false, local_dir
# setting must be set to specify the local directory in which the charts exists
fetch: true

# (optional) push specifies the global push policy for all regitries.
# defaults to true if not specified. If push is set to false, images
# will not be pushed to specified registries
push: true

# (optional) retain specifies the global retain policy for all images
# defaults to false if not specified. if retain is set to false, images
# that are downloaded and retagged are deleted after pushing them
# to the specified registries
retain: false
```

## Installation

Following script can be fetched and executed to install helm_image_mirror. It is a simple two-liner which executes
the docker image shashankv/helm_image_mirror:v1.0.0-beta. Feel free to edit the script
as required.

```
# Download the script
$ curl -fsSL -o helm_image_mirror.sh https://raw.githubusercontent.com/shashankv02/helm-image-mirror/main/helm_image_mirror.sh

# Add execute permissions
$ chmod +x helm_image_mirror.sh

# Copy the script to location in your $PATH
$ mv helm_image_mirror.sh /usr/local/bin/helm_image_mirror
```

## How to use

### Step 1:

Create the configuration file. See [sample-config.yaml](sample-config.yaml)

### Step 2:

`helm_image_mirror -c config.yaml` (Replace config.yaml with your config file)

## How to build

`make build` will trigger the build and generate the docker image

## How to contribute

1. Fork this repo

2. Make changes in the forked copy

3. Submit a pull request


## Debugging

Run with `-d` option for debug logs

