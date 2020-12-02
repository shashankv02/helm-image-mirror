#!/usr/bin/env python3

import shlex
import subprocess
import os
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
    @staticmethod
    def missing_required_key(key):
        return "missing required key " + key

    @staticmethod
    def invalid_value(key, value=""):
        return "invalid value {} for key {}".format(value, key)


def template():
    pass


def parse_input(file):
    with open(file, "r") as f:
        config = yaml.load(f)
    return config


def execute(command, print_cmd=True):
    if print_cmd:
        print(command)
    cmd = shlex.split(command)
    return subprocess.run(cmd, check=True, capture_output=True).stdout


def helm(command, run=True, print_cmd=True):
    cmd = "helm " + command
    try:
        return execute(cmd, print_cmd=print_cmd)
    except subprocess.CalledProcessError as e:
        print(e.output, e.stderr)
        raise


def docker(command):
    cmd = "docker " + command
    try:
        return execute(cmd)
    except subprocess.CalledProcessError as e:
        print(e.output, e.stderr)
        raise


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


def parse_images(manifests):
    images = set()
    docs = yaml.safe_load_all(manifests)
    images = set()
    for doc in docs:
        images.update(get_images(doc))
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
        username, password = get_repo_username_password(repo, g_username, g_password)
        base_cmd = "repo add {name} {remote}".format(name=name, remote=remote)
        if username and password:
            cmd_template = "{} --username {} --password {}"
            cmd = cmd_template.format(base_cmd, username, password)
            masked_cmd = cmd_template.format(base_cmd, username, "<snipped>")
            print("helm " + masked_cmd)
            helm(cmd, print_cmd=False)
        else:
            helm(base_cmd)
    print("Finished configuring repositories")


def get_all_images(charts, global_fetch_policy):
    images = set()
    for chart_i, chart in enumerate(charts):
        chart_fetch_policy = chart.get(FETCH_KEY, None)
        chart_name = chart.get(NAME_KEY)
        repo_name = chart.get(REPO_KEY)
        if not chart_name:
            if NAME_KEY not in chart:
                err = Errors.missing_required_key(NAME_KEY)
            else:
                err = Errors.invalid_value(chart_name, NAME_KEY)
            error(err, parents=[CHARTS_KEY], index=chart_i)
            continue
        if not repo_name:
            if REPO_KEY not in chart:
                err = Errors.missing_required_key(REPO_KEY)
            else:
                err = Errors.invalid_value(chart_name, REPO_KEY)
            error(err, parents=[CHARTS_KEY], index=chart_i)
            continue
        for version_i, version in enumerate(chart[VERSIONS_KEY]):
            version_fetch_policy = version.get(FETCH_KEY, None)
            version_str = version.get(VERION_KEY)
            if not version_str:
                if VERION_KEY not in version:
                    err = Errors.missing_required_key(VERION_KEY)
                else:
                    err = Errors.invalid_value(version_str, VERION_KEY)
                error(err, parents=[CHARTS_KEY, VERSIONS_KEY], index=version_i)
                continue
            local_dir = version.get(FETCH_DIR_KEY) or "/tmp/{}".format(version_i)
            if get_fetch_policy(
                global_fetch_policy, chart_fetch_policy, version_fetch_policy
            ):
                helm(
                    "fetch --untar --untardir {}  --version {} {}/{}".format(
                        local_dir, version_str, repo_name, chart_name
                    )
                )
            manifests = helm("template {}/{}".format(local_dir, chart_name))
            images.update(parse_images(manifests))
    return images


def get_error_type(key, value, obj):
    if key not in obj:
        return Errors.missing_required_key(key)
    return Errors.invalid_value(value, key)


def push_images(images, registries, g_push, g_retain, parents):
    for i, registry in enumerate(registries):
        registry_name = registry.get(NAME_KEY)
        if not registry_name:
            err = get_error_type(NAME_KEY, registry_name, registry)
            error(err, parents=parents, index=i)
            continue
        push = registry.get(PUSH_KEY, g_push)
        retain = registry.get(RETAIN_KEY, g_retain)
        if not push:
            print(
                "Not pushing images to registry", registry_name, "as push field is set to false"
            )
            continue
        for image in images:
            image_name = image.split("/")[-1]
            target_name = "{}/{}".format(registry_name, image_name)
            docker("pull {}".format(image))
            docker("tag {} {}".format(image, target_name))
            docker("push {}".format(target_name))
            if not retain:
                docker("rmi {}".format(target_name))


def run(file):
    # parse_input
    config = parse_input(file)
    charts, repos = config[CHARTS_KEY], config[REPOS_KEY]
    global_fetch_policy = config.get(FETCH_KEY, True)
    init_scripts = config[INIT_SCRIPTS_KEY]
    run_init_scripts(init_scripts)

    # Configure repos
    configure_repos(repos, parents=[REPOS_KEY])

    # Update repos
    helm("repo update")

    # fetch charts
    images = get_all_images(charts, global_fetch_policy=global_fetch_policy)

    print(images)

    # Retag and push images
    print("Retagging and pushing images to destinations")
    registries = config.get(REGISTRIES_KEY)
    g_retain = config.get(RETAIN_KEY, False)
    g_push = config.get(PUSH_KEY, True)
    push_images(
        images, registries, g_retain=g_retain, g_push=g_push, parents=[REGISTRIES_KEY]
    )


run("sample.yaml")
# render template out
# parse rendered template
# pull all images
# retag all images
# push all images
# clean
