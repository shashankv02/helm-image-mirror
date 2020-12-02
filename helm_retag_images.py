#!/usr/bin/env python3

import shlex
import subprocess
import os
import yaml


def template():
    pass

def parse_input(file):
    with open(file, 'r') as f:
        config = yaml.load(f)
    return config

def execute(command):
    cmd = shlex.split(command)
    subprocess.run(cmd, check=True, capture_output=True).stdout


def helm(command):
    try:
        return execute("helm " + command)
    except subprocess.CalledProcessError as e:
        print(e)
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
    for script in init_scripts:
        if not os.path.isfile(script):
            print(script, "not found!")
            continue
        execute(script)


def run(file):
    # parse_input
    config = parse_input(file)
    charts, registries = config["charts"], config["registries"]
    global_fetch_policy = config.get("fetch", True)
    init_scripts = config["init_scripts"]
    run_init_scripts(init_scripts)

    # fetch charts
    images = set()
    for chart in charts:
        chart_fetch_policy = chart.get("fetch", None)
        for version in chart["versions"]:
            version_fetch_policy = version.get("fetch", None)
            if get_fetch_policy(global_fetch_policy, chart_fetch_policy, version_fetch_policy):
                helm('fetch --untar --untardir .  --version {} {}'.format(version, chart))
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

