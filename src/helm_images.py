#!/usr/bin/env python3

"""
This script takes a yaml formatted config file as input in which user
can specify a list of helm repositories, helm charts and docker registries.
The helm charts will be downloaded, parsed to find all the images mentioned
in the charts and the images can be re-tagged and pushed to the specified
docker registries
"""

import argparse
import os
import shlex
import subprocess
import sys
import pprint

import yaml

# Constants
REPOS_KEY = "repos"
REPO_KEY = "repo"
REPOS_ADD_KEY = "add"
REMOTE_KEY = "remote"
UPDATE_KEY = "update"
CHARTS_KEY = "charts"
FETCH_KEY = "fetch"
FETCH_DIR_KEY = "local_dir"
VERSIONS_KEY = "versions"
VERION_KEY = "version"
NAME_KEY = "name"
USERNAME_KEY = "username"
PASSWORD_KEY = "password"
INIT_SCRIPTS_KEY = "init_scripts"
REGISTRIES_KEY = "registries"
PUSH_KEY = "push"
RETAIN_KEY = "retain"


class Errors:
    """Standard errors
    """
    @staticmethod
    def missing_required_key(key):
        return "missing required key " + key

    @staticmethod
    def invalid_value(key, value=""):
        return "invalid value {} for key {}".format(value, key)


class Chart:
    def __init__(self, repo_name, chart_name, version, local_dir, fetch_policy):
        self.repo_name = repo_name
        self.chart_name = chart_name
        self.version = version
        self.local_dir = local_dir
        self.fetch_policy = fetch_policy

    def fetch(self):
        if self.fetch_policy:
            helm(
                "fetch --untar --untardir {}  --version {} {}/{}".format(
                    self.local_dir, self.version, self.repo_name, self.chart_name
                )
            )

    def template(self):
        return helm("template {}/{}".format(self.local_dir, self.chart_name))


    def images(self):
        return parse_images(self.template())

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)



class Registry:
    def __init__(self, name, push, retain):
        self.name = name
        self.push = push
        self.retain = retain

    def tag_and_push(self, images):
        if not self.push:
            print(
                "Not pushing images to registry",
                self.name,
                "as push is set to false",
            )
        for image in images:
            image_name = image.split("/")[-1]
            target_name = "{}/{}".format(self.name, image_name)
            docker("tag {} {}".format(image, target_name))
            docker("push {}".format(target_name))
            if not self.retain:
                docker("rmi {}".format(target_name))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


class Repo:
    def __init__(self, name, remote, username, password):
        self.name = name
        self.remote = remote
        self.username = username
        self.password = password

    def get_add_cmd(self, mask_pw=False):
        add_cmd = "repo add {name} {remote}".format(name=self.name, remote=self.remote)
        if self.username and self.password:
            password = self.password
            if mask_pw:
                password = "<snipped>"
            credential_flags_template = "{} --username {} --password {}"
            add_cmd_with_credentials = credential_flags_template.format(add_cmd, self.username, password)
            return add_cmd_with_credentials
        return add_cmd

    def add(self):
        cmd = self.get_add_cmd()
        masked_cmd = self.get_add_cmd(mask_pw=True)
        print(masked_cmd)
        helm(cmd, print_cmd=False)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


def load_config(file):
    """Loads given config file
    into memory

    :param file: path to config file
    :type file: str
    :return: loaded config
    :rtype: Dict
    """
    with open(file, "r") as f:
        config = yaml.load(f)
    return config


def execute(command, print_cmd=True):
    """Executes given command in a subprocess

    :param command: command to execute
    :type command: str
    :param print_cmd: prints command being executed if True,
        defaults to True
    :type print_cmd: bool, optional
    :return: output from command
    :rtype: str

    :raises: subprocess.CalledProcessError
    """
    if print_cmd:
        print(command)
    cmd = shlex.split(command)
    return subprocess.run(cmd, check=True, capture_output=True).stdout


def helm(command, run=True, print_cmd=True):
    """Runs helm cli command

    :param command: sub command
    :type command: str
    :return: output from command
    :rtype: str
    """
    cmd = "helm " + command
    try:
        return execute(cmd, print_cmd=print_cmd)
    except subprocess.CalledProcessError as e:
        print(e.output, e.stderr)
        raise


def docker(command):
    """Runs docker cli command

    :param command: sub command
    :type command: str
    :return: output from command
    :rtype: str
    """
    cmd = "docker " + command
    try:
        return execute(cmd)
    except subprocess.CalledProcessError as e:
        print(e.output, e.stderr)
        raise


def parse_images(documents):
    """Get all images in given yaml
    documents

    :param documents: yaml documents
    :type documents: str
    :return: list of images
    :rtype: [str]
    """
    def get_images(obj):
        images = set()
        if not isinstance(obj, dict):
            return images
        for key, value in obj.items():
            if key == "image" and isinstance(value, str):
                images.add(value)
            if isinstance(value, dict):
                images.update(get_images(value))
        return images

    images = set()
    docs = yaml.safe_load_all(documents)
    images = set()
    for doc in docs:
        images.update(get_images(doc))
    return images


def run_init_scripts(init_scripts):
    """Executes given scripts

    :param init_scripts: path of scripts
        to be executed
    :type init_scripts: [str]
    """
    print("Executing initialization scripts")
    for script in init_scripts:
        if not os.path.isfile(script):
            print(script, "not found!")
            continue
        abspath = os.path.abspath(script)
        print("Executing", abspath)
        execute(abspath)
    print("Finished executing initialization scripts")


def error(error, parents=[], index=None):
    """Constructs configuration related error messages

    :param error: error messages
    :type error: str
    :param parents: list of parent keys of
        the field that has error, defaults to []
    :type parents: [str], optional
    :param index: optional index in a list if the
        error is in a list item, defaults to None
    :type index: int, optional
    """
    msg = "Error: {}".format(error)
    if parents:
        # join parents - ["repos", "add"] -> "repos.add"
        if isinstance(parents, list):
            parents = ".".join(parents)
        msg = "{} in section {}".format(msg, parents)
    if index:
        msg = "{} at index {}".format(msg, index)
    print(msg)


def get_repo_username_password(repo, g_username, g_password):
    """Returns username password configured for given helm repository

    If username or password keys are specified in repo configuration,
    return them else fallback to g_username, g_password

    :param repo: Repository configuration
    :type repo: Dict
    :param g_username: fallback username
    :type g_username: str
    :param g_password: fallback password
    :type g_password: str
    :return: (username, password)
    :rtype: (str, str)
    """
    if USERNAME_KEY not in repo:
        username = g_username
    else:
        username = repo.get(USERNAME_KEY)
    if PASSWORD_KEY not in repo:
        password = g_password
    else:
        password = repo.get(PASSWORD_KEY)
    return username, password


def get_repo_objs(repos, g_username, g_password, parents=[]):
    repo_objs = []
    for i, repo in enumerate(repos):
        is_err = False
        name = repo.get(NAME_KEY)
        if not name:
            error(Errors.missing_required_key(NAME_KEY), parents=parents, index=i)
            is_err = True
        remote = repo.get(REMOTE_KEY)
        if not remote:
            error(Errors.missing_required_key(NAME_KEY), parents=parents, index=i)
            is_err = True
        if is_err:
            continue
        username, password = get_repo_username_password(repo, g_username, g_password)
        repo_objs.append(
            Repo(
                name=name,
                remote=remote,
                username=username,
                password=password,
            )
        )
    return repo_objs


def get_repos(repos, parents):
    """Configures helm repositories

    :param repos: repos configuration
    :type repos: Dict
    :param parents: list of parent keys in the configuration
        to be used for constructing appropriate error messages
        for configuration errors
    :type parents: [str]
    """
    g_username, g_password = repos[USERNAME_KEY], repos[PASSWORD_KEY]
    parents += REPOS_ADD_KEY
    repos_to_add = repos.get(REPOS_ADD_KEY, [])
    return get_repo_objs(repos_to_add, g_username, g_password, parents=parents)


def get_charts(charts, global_fetch_policy):
    """Get all Chart objects loaded from charts configuration

    :param charts: charts section in configuration
    :type charts: Dict
    :param global_fetch_policy: global chart fetch policy
        to be used if the chart local fetch policy
        is not specified
    :type global_fetch_policy: bool
    :return: list of Charts
    :rtype: [Chart]
    """
    chart_objs = []
    for chart_i, chart in enumerate(charts):
        chart_fetch_policy = chart.get(FETCH_KEY, global_fetch_policy)
        chart_name = chart.get(NAME_KEY)
        repo_name = chart.get(REPO_KEY)
        if not chart_name:
            err = get_error_type(NAME_KEY, chart_name, chart)
            error(err, parents=[CHARTS_KEY], index=chart_i)
            continue
        if not repo_name:
            err = get_error_type(REPO_KEY, repo_name, chart)
            error(err, parents=[CHARTS_KEY], index=chart_i)
            continue
        for version_i, version in enumerate(chart[VERSIONS_KEY]):
            version_fetch_policy = version.get(FETCH_KEY, chart_fetch_policy)
            version_str = version.get(VERION_KEY)
            if not version_str:
                err = get_error_type(VERION_KEY, version_str, version)
                error(err, parents=[CHARTS_KEY, VERSIONS_KEY], index=version_i)
                continue
            local_dir = version.get(FETCH_DIR_KEY) or "/tmp/{}/{}/{}".format(repo_name, chart_name, version_i)
            chart_objs.append(
                Chart(
                    repo_name=repo_name,
                    chart_name=chart_name,
                    version=version_str,
                    local_dir=local_dir,
                    fetch_policy=version_fetch_policy,
                )
            )
    return chart_objs


def get_all_images(charts):
    """Get all images from the charts

    :param charts: List of Chart objects
    :type charts: [Chart]
    :return: list of images
    :rtype: [str]
    """
    images = set()
    for chart in charts:
        images.update(chart.images())
    return images


def get_error_type(key, value, obj):
    if key not in obj:
        return Errors.missing_required_key(key)
    return Errors.invalid_value(value, key)


def get_registries(registries, g_push, g_retain, parents=[]):
    """Pushes given images to given registries

    :param images: list of images
    :type images: [str]
    :param registries: list of destination registries
    :type registries: [str]
    :param g_push: global push policy
    :type g_push: bool
    :param g_retain: global retain policy
    :type g_retain: bool
    :param parents: list of parent keys in the configuration
        to be used for constructing appropriate error messages
        for configuration errors
    :type parents: [str]
    """
    registry_objs = []
    for i, registry in enumerate(registries):
        registry_name = registry.get(NAME_KEY)
        if not registry_name:
            err = get_error_type(NAME_KEY, registry_name, registry)
            error(err, parents=parents, index=i)
            continue
        push = registry.get(PUSH_KEY, g_push)
        retain = registry.get(RETAIN_KEY, g_retain)
        registry_objs.append(
            Registry(
                name=registry_name,
                push=push,
                retain=retain,
            )
        )
    return registry_objs


def push_images_to_registries(images, registries):
    for registry in registries:
        registry.tag_and_push(images)


def configure_repos(repos, update=True):
    for repo in repos:
        repo.add()
    if update:
        helm("repo update")


def main(file):
    """Main function

    :param file: configuration file path
    :type file: str
    """
    # Parse configuration
    config = load_config(file)

    # Run initialization scripts
    init_scripts = config.get(INIT_SCRIPTS_KEY, [])
    run_init_scripts(init_scripts)

    # Configure repos
    repos_config = config[REPOS_KEY]
    repos = get_repos(repos_config, parents=[REPOS_KEY])
    configure_repos(repos)

    # fetch charts
    charts = config.get(CHARTS_KEY)
    if not charts:
        print("No charts specified in config")
        return
    global_fetch_policy = config.get(FETCH_KEY, True)
    charts = get_charts(charts, global_fetch_policy=global_fetch_policy)
    images = get_all_images(charts)

    print("Found images")
    pprint.pprint(images)

    # Retag and push images
    print("Retagging and pushing images to destinations")
    registries = config.get(REGISTRIES_KEY)
    g_retain = config.get(RETAIN_KEY, False)
    g_push = config.get(PUSH_KEY, True)
    registries = get_registries(
        registries, g_retain=g_retain, g_push=g_push, parents=[REGISTRIES_KEY]
    )
    push_images_to_registries(images, registries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    sys.exit(main(args.config))