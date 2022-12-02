#!/usr/bin/env python3

"""
This script takes a yaml formatted config file as input in which user
can specify a list of helm repositories, helm charts and docker registries.
The helm charts will be downloaded, parsed to find all the images mentioned
in the charts and the images can be re-tagged and pushed to the specified
docker registries
"""

import argparse
import json
import os
import shlex
import subprocess
import sys

import yaml

# Constants
DEBUG = False
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
SCRIPTS_KEY = "scripts"
REGISTRIES_KEY = "registries"
PUSH_KEY = "push"
RETAIN_KEY = "retain"
VALUES_KEY = "values"
SET_KEY = "set"
SET_STRING_KEY = "set_string"
DEBUG_HELP_MSG = "Use --debug option to see more information"


class Errors:
    """Standard errors"""

    @staticmethod
    def missing_required_key(key):
        return "missing required key " + key

    @staticmethod
    def invalid_value(key, value=""):
        return "invalid value {} for key {}".format(value, key)


class Chart:
    """Helm chart configuration"""

    def __init__(
        self, repo_name, chart_name, version, 
        local_dir, fetch_policy, values={}, push=[],
        scripts=[]
    ):
        self.repo_name = repo_name
        self.chart_name = chart_name
        self.version = version
        self.local_dir = local_dir
        self.fetch_policy = fetch_policy
        self.values = values
        self.combined_name = "{}/{}-{}".format(
            self.repo_name, self.chart_name, self.version
        )
        self.push_targets = push
        self.scripts = scripts

    def fetch(self):
        if self.fetch_policy:
            helm(
                "fetch --untar --untardir {}  --version {} {}/{}".format(
                    self.local_dir, self.version, self.repo_name, self.chart_name
                )
            )
        else:
            print(
                "Using local directory",
                self.local_dir,
                "as fetch is set to false for chart",
                self.combined_name,
            )
    
    def pull(self):
        print("Pulling chart {}".format(self.combined_name))
        os.makedirs(self.local_dir, exist_ok=True)
        helm("pull {}/{} --version {} --destination {} --devel".format(
            self.repo_name, self.chart_name, self.version, self.local_dir
        ))
        

    def push(self, target_repo):
        print("Pushing chart {} to {} repository".format(
            self.combined_name, target_repo.name))
        saved_chart_name = '{}-{}.tgz'.format(self.chart_name, self.version)
        saved_chart_path = os.path.join(self.local_dir, saved_chart_name)
        helm("push {} {}".format(saved_chart_path, target_repo.name))


    def get_flags(self):
        set_flag = self.values.get(SET_KEY)
        set_string_flag = self.values.get(SET_STRING_KEY)
        flags = ""
        if set_flag:
            flags = "{} --set {}".format(flags, set_flag)
        if set_string_flag:
            flags = "{} --set-string {}".format(flags, set_string_flag)
        return flags

    def get_template_cmd(self):
        flags = self.get_flags()
        return "template {} {}/{}".format(flags, self.local_dir, self.chart_name)

    def template(self):
        cmd = self.get_template_cmd()
        return helm(cmd)

    def images(self):
        print("Finding images in chart", self.combined_name)
        images = parse_images(self.template())
        if not images:
            print("No images found")
        else:
            print("Found images:", images)
        return images
    
    def run_scripts(self):
        print("Running scripts for chart", self.combined_name)
        return run_scripts(
            self.scripts, [self.repo_name, self.chart_name, self.version])

    def __eq__(self, other):
        return isinstance(other, self.__class__) and \
            self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


class Registry:
    """Docker registry configuration"""

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
            return [], [], [], []
        tag_failures = set()
        push_failures = set()
        cleanup_failures = set()
        succeeded = set()
        for image in images:
            image_name = image.split("/")[-1]
            if self.name == "hub.docker.com":
                # Default dockerhub domain doesn't need prefix
                target_name = image_name
            else:
                target_name = "{}/{}".format(self.name, image_name)
            try:
                docker("tag {} {}".format(image, target_name))
            except subprocess.CalledProcessError:
                tag_failures.add((image, target_name))
                continue
            try:
                docker("push {}".format(target_name))
            except subprocess.CalledProcessError:
                push_failures.add(target_name)
            else:
                succeeded.add(target_name)
            if not self.retain:
                try:
                    docker("rmi {}".format(target_name))
                except subprocess.CalledProcessError:
                    cleanup_failures.add(target_name)
        return succeeded, tag_failures, push_failures, cleanup_failures

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


class Repo:
    """Helm repository configuration"""

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
            add_cmd_with_credentials = credential_flags_template.format(
                add_cmd, self.username, password
            )
            return add_cmd_with_credentials
        return add_cmd

    def add(self):
        cmd = self.get_add_cmd(mask_pw=False)
        masked_cmd = self.get_add_cmd(mask_pw=True)
        debug("helm " + masked_cmd)
        helm(cmd, print_cmd=False)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

        

def debug(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


def load_config(file):
    """Loads given config file
    into memory

    :param file: path to config file
    :type file: str
    :return: loaded config
    :rtype: Dict
    """
    try:
        with open(file, "r") as f:
            config = yaml.safe_load(f)
    except IOError as e:
        print(e)
        return None
    return config


def execute(command, print_cmd=True, split=True):
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
        debug(command)
    if split:
        command = shlex.split(command)
    return subprocess.run(command, check=True, capture_output=True).stdout


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
        if isinstance(obj, list) or isinstance(obj, set):
            for value in obj:
                images.update(get_images(value))
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "image" and isinstance(value, str):
                    debug("Adding image", value)
                    images.add(value)
                images.update(get_images(value))
        return images

    docs = yaml.safe_load_all(documents)
    images = set()
    for doc in docs:
        debug(doc)
        images.update(get_images(doc))
    return images


def run_scripts(scripts, args=[]):
    """Executes given scripts

    :param init_scripts: path of scripts
        to be executed
    :type init_scripts: [str]
    """
    failures = {}
    for script in scripts:
        # if the script has hardcoded arguments, those are used instead
        # of the defaults
        script_tokens = script.split()
        script_path, user_args = script_tokens[0], script_tokens[1:]
        if not os.path.isfile(script_path):
            print(script_path, "not found!")
            failures[script_path] = "File not found"
            continue
        abspath = os.path.abspath(script_path)
        args = user_args or args
        print("Executing:", abspath, *args)
        try:
            subprocess.run([abspath, *args], check=True)
        except subprocess.CalledProcessError as exp:
            failures[script] = str(exp)
    return failures


def run_init_scripts(init_scripts):
    """Executes given initialization scripts

    :param init_scripts: path of scripts
        to be executed
    :type init_scripts: [str]
    """
    print("Executing initialization scripts")
    run_scripts(init_scripts)
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
    if isinstance(index, int):
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
    """Return Repo class instances instantiated from given
    repos configuration

    :param repos: List of helm repository configurations
    :type repos: [Dict]
    :param g_username: global username
    :type g_username: str
    :param g_password: global password
    :type g_password: str
    :param parents: list of parent keys in the configuration
        to be used for constructing appropriate error messages
        for configuration errors, defaults to []
    :type parents: list, optional
    :return: list of Repo objects
    :rtype: [Repo]
    """
    repo_objs = []
    for i, repo in enumerate(repos):
        is_err = False
        name = repo.get(NAME_KEY)
        if not name:
            err = get_error_type(NAME_KEY, name, repo)
            error(err, parents=parents, index=i)
            is_err = True
        remote = repo.get(REMOTE_KEY)
        if not remote:
            err = get_error_type(REMOTE_KEY, remote, repo)
            error(err, parents=parents, index=i)
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
    parents.append(REPOS_ADD_KEY)
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
        chart_values = chart.get(VALUES_KEY, {})
        chart_name = chart.get(NAME_KEY)
        repo_name = chart.get(REPO_KEY)
        chart_scripts = chart.get(SCRIPTS_KEY, [])
        chart_push_targets = chart.get(PUSH_KEY, [])
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
            local_dir = version.get(FETCH_DIR_KEY) or "/tmp/{}/{}/{}".format(
                repo_name, chart_name, version_i
            )
            version_values = version.get(VALUES_KEY, chart_values)
            version_push_targets = version.get(PUSH_KEY, chart_push_targets)
            chart_objs.append(
                Chart(
                    repo_name=repo_name,
                    chart_name=chart_name,
                    version=version_str,
                    local_dir=local_dir,
                    fetch_policy=version_fetch_policy,
                    values=version_values,
                    push=version_push_targets,
                    scripts=chart_scripts,
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
        chart.fetch()
        images.update(chart.images())
    return images


def get_error_type(key, value, obj):
    if key not in obj:
        return Errors.missing_required_key(key)
    return Errors.invalid_value(key, value)


def list_to_dict(lst, key):
    """Convert list of objects to a dictionary mapping
    given key in the object to object for faster queries

    :param lst: list of objects. object must contain given key as attribute
    :type lst: [Any]
    :param key: Name of the key attribute in the object
    :type key: str
    :return: Dictionary mapping the key attribute from each object to the object
    :rtype: Dict
    """    
    result = {}
    for obj in lst:
        result[getattr(obj, key)] = obj
    return result


def get_registries(registries, g_push, g_retain, parents=[]):
    """Get Registry objects instantiated from given registries
    configuration

    :param registries: list of destination registry configurations
    :type registries: [Dict]
    :param g_push: global push policy
    :type g_push: bool
    :param g_retain: global retain policy
    :type g_retain: bool
    :param parents: list of parent keys in the configuration
        to be used for constructing appropriate error messages
        for configuration errors
    :type parents: [str]
    :return: list of Registry objects
    :rtype: [Registry]
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


def pull_images(images):
    """Pull given images

    :param images: list of images
    :type images: [str]
    :return: images that could not be pulled
    :rtype: set(str)
    """
    failed_images = set()
    for image in images:
        try:
            docker("pull {}".format(image))
        except subprocess.CalledProcessError:
            print("Unable to pull image", image)
            failed_images.add(image)
    return failed_images


def push_images_to_registries(images, registries):
    """Pushes all given images to given registries

    :param images: list of images
    :type images: [str]
    :param registries: list of Regitries
    :type registries: [Registry]
    :return: dictionary containing success and failures information
        and boolean indicating if any failures have occurred
    :rtype: Dict, bool
    """
    failures = {}
    for registry in registries:
        pushed, tf, pf, cf = registry.tag_and_push(images)
        failures[registry.name] = {
            "Pushed": list(pushed),
            "Failed to tag": list(tf),
            "Failed to push": list(pf),
            "Failed to cleanup": list(cf),
        }
    return failures, tf or pf or cf


def reconcile_charts(charts, repos):
    """Pushes given charts to specified target helm repositories

    :param charts: list of charts
    :type charts: [Chart]
    :param repos: list of helm repositories configured globally
    :type repos: [Repo]
    """
    status = {}
    repo_map = list_to_dict(repos, "name")
    err = False
    for chart in charts:
        if not (chart.scripts or chart.push_targets):
            continue

        status[chart.combined_name] = {}
        stat = status[chart.combined_name]
        # Run chart scripts
        if chart.scripts:
            failed = chart.run_scripts()
            if failed:
                err = True
            stat["Failed scripts"] = failed
        
        # Push chart to other repositories if configured
        if not chart.push_targets:
            continue
        # Pull the chart
        try:
            chart.pull()
        except subprocess.CalledProcessError as exp:
            if DEBUG:
                msg = str(exp.stderr, 'utf-8')
            else:
                msg = "Unable to pull chart. {}".format(DEBUG_HELP_MSG)
            stat["pull"] = msg
            err = True
            continue
        else:
            stat["pull"] = "Pulled succesfully"
        
        # Push the chart to target repositories
        for repo_name in chart.push_targets:
            stat["push"] = {}
            if repo_name not in repo_map:
                stat["push"][repo_name] = (
                    "Repository is not configured under repos section. "
                    "Please configure it and retry."
                )
                continue
            try:
                chart.push(repo_map[repo_name])
            except subprocess.CalledProcessError as exp:
                err = True
                if DEBUG:
                    msg = str(exp.stderr, 'utf-8')
                else:
                    msg = "Unable to push chart. {}".format(DEBUG_HELP_MSG)
                stat["push"][repo_name] = msg
            else:
                stat["push"][repo_name] = "Pushed successfully"
    return status, err
    

def configure_repos(repos, update=True):
    """Configures given helm repositories

    :param repos: list of Repos
    :type repos: [Repo]
    :param update: `helm repo update` is run if True,
        defaults to True
    :type update: bool, optional
    """
    status = {}
    err = False
    for repo in repos:
        print("Configuring helm repository", repo.name)
        try:
            repo.add()
        except subprocess.CalledProcessError as e:
            status[repo.name] = f"Unable to add helm repository. Please check logs."
            err = True        
    if repos and update:
        print("Updating helm repositories")
        try:
            helm("repo update")
        except subprocess.CalledProcessError as e:
            print("helm repo update failed")
            err = True
    return status, err


def print_dict(failures):
    """Prints failres if any

    :param failures: Dictionary of failures
        mapping failure type and failed items
    :type failures: Dict
    """
    failures_copy = dict(failures)
    for msg, items in failures.items():
        if not items:
            del failures_copy[msg]
    print(json.dumps(failures_copy, indent=4))



def main(file):
    """Main function

    :param file: configuration file path
    :type file: str
    """
    err = False
    # Parse configuration
    config = load_config(file)
    if not config:
        return 1

    # Run initialization scripts
    init_scripts = config.get(INIT_SCRIPTS_KEY, [])
    run_init_scripts(init_scripts)

    # Configure repos
    repos_config = config.get(REPOS_KEY, {})
    repos = {}
    if repos_config: 
        repos = get_repos(repos_config, parents=[REPOS_KEY])
        repo_status, err = configure_repos(repos)
    if err:
        if repo_status:
            print("{:=^50}".format(" Helm repository Status "))
            print_dict(repo_status)
        return 1
    # fetch charts
    charts = config.get(CHARTS_KEY)
    if not charts:
        print("No charts specified in config")
        return
    global_fetch_policy = config.get(FETCH_KEY, True)
    charts = get_charts(charts, global_fetch_policy=global_fetch_policy)

    # Retag and push images
    registry_config = config.get(REGISTRIES_KEY, [])
    if registry_config:
        print("Retagging and pushing images to destinations")
        images = get_all_images(charts)
        g_retain = config.get(RETAIN_KEY, False)
        g_push = config.get(PUSH_KEY, True)
        registries = get_registries(
            registry_config, g_retain=g_retain, g_push=g_push, parents=[REGISTRIES_KEY]
        )
        failed_to_pull = pull_images(images)
        if failed_to_pull:
            err = True
        pulled_images = images - failed_to_pull
        failures, err = push_images_to_registries(pulled_images, registries)
        # Report status
        print("{:=^50}".format(" Image Status "))
    
        print_dict(
            {
                "All images": list(images),
                "Failed to pull": failed_to_pull,
                **failures,
            }
        )

    # push charts to target helm repositories
    chart_push_status, err = reconcile_charts(charts, repos)
    if repo_status:
        print("{:=^50}".format(" Helm repository Status "))
        print_dict(repo_status)
    if chart_push_status:
        print("{:=^50}".format(" Chart Status "))
        print_dict(chart_push_status)
    if registry_config or chart_push_status:
        print("{:=^50}".format(" Status "))
    if err:
        return 1
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", required=True, help="configuration file path")
    parser.add_argument("-d", "--debug", action="store_true", help="print debug logs")
    args = parser.parse_args()
    if args.debug:
        DEBUG = True
    sys.exit(main(args.config))
