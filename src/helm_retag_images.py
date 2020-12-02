#!/usr/bin/env python3

import shlex
import subprocess
import os
import yaml

# Constants
REPOS_KEY = "repos"
REPOS_ADD_KEY = "add"
REMOTE_KEY = "remote"
CHARTS_KEY = "charts"
FETCH_KEY = "fetch"
VERSIONS_KEY = "versions"
VERION_KEY = "version"
NAME_KEY = "name"
USERNAME_KEY = "username"
PASSWORD_KEY = "password"
INIT_SCRIPTS_KEY = "init_scripts"
REGISTRIES_KEY = "registries"

class Errors:
    @staticmethod
    def missing_required_key(key):
        return "missing required key " + key

    @staticmethod
    def invalid_value(value=''):
        return "invalid value " + value


def template():
    pass

def parse_input(file):
    with open(file, 'r') as f:
        config = yaml.load(f)
    return config

def execute(command, print_cmd=True):
    if print_cmd:
        print(command)
    cmd = shlex.split(command)
    subprocess.run(cmd, check=True, capture_output=True).stdout


def helm(command, print_cmd=True):
    try:
        return execute("helm " + command, print_cmd=print_cmd)
    except subprocess.CalledProcessError as e:
        print(e.output)
        raise



def get_images(obj):
    images = set()
    if not isinstance(obj, dict):
        return images
    for key, value in obj:
        if key == "image" and isinstance(value, str):
            images.add(value)
        if isinstance(value, dict):
            images.add(get_images(value))
    return images



def parse_images(manifests):
    images = set()
    docs = yaml.safe_load(manifests)
    images = set()
    for doc in docs:
        images.add(get_images(doc))
    return images


def get_fetch_policy(global_policy, chart_policy, version_policy):
    if isinstance(version_policy, bool):
        return version_policy
    if isinstance(chart_policy, bool):
        return chart_policy
    return bool(global_policy)

def run_init_scripts(init_scripts):
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
    msg = "Error: {}".format(error)
    if parents:
        # join parents - ["repos", "add"] -> "repos.add"
        if isinstance(parents, list):
            parents = '.'.join(parents)
        msg = "{} in section {}".format(msg, parents)
    if index:
        msg = "{} at index {}".format(msg, index)
    print(msg)


def configure_repos(repos, parents=[]):
    print("Configuring repositories")
    g_username, g_password = repos[USERNAME_KEY], repos[PASSWORD_KEY]
    parents += REPOS_ADD_KEY
    for i, repo in enumerate(repos[REPOS_ADD_KEY]):
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
        username = repo.get(username) or g_username
        password = repo.get(password) or g_password
        cmd  = "repo add {name} {remote}".format(name=name, remote=remote)
        if username and password:
            cmd_template = "{} --username {} --password {}"
            cmd = cmd_template.format(cmd, username, password)
            masked_cmd = cmd_template.format(cmd, username, "<snipped>")
        print(masked_cmd)
        helm(cmd, print_cmd=False)
    print("Finished configuring repositories")


def run(file):
    # parse_input
    config = parse_input(file)
    charts, repos, registries = config[CHARTS_KEY], config[REPOS_KEY], config[REGISTRIES_KEY]
    global_fetch_policy = config.get(FETCH_KEY, True)
    init_scripts = config[INIT_SCRIPTS_KEY]
    run_init_scripts(init_scripts)

    # Configure repos
    configure_repos(repos, parents=[REPOS_KEY])

    # fetch charts
    images = set()
    for chart_i, chart in enumerate(charts):
        chart_fetch_policy = chart.get(FETCH_KEY, None)
        chart_name = chart.get(NAME_KEY)
        if not chart_name:
            print("No chart name specified for chart at index", chart_i)
            continue
        for version_i, version in enumerate(chart[VERSIONS_KEY]):
            version_fetch_policy = version.get(FETCH_KEY, None)
            version_str = version.get(VERION_KEY)
            if not version_str:
                print("No version string specified for chart", chart_name, "at index", version_i)
                continue
            if get_fetch_policy(global_fetch_policy, chart_fetch_policy, version_fetch_policy):
                helm('fetch --untar --untardir .  --version {} {}'.format(version_str, chart_name))
            manifests = helm('template ./config-manager')
            images.add(parse_images(manifests))
    print(images)

run('sample.yaml')
    # render template out
    # parse rendered template
    # pull all images
    # retag all images
    # push all images
    # clean

