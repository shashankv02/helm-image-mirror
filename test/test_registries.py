#!/usr/bin/python3

import os
import re
import sys
import pytest

import yaml

base_path = re.search("^(.*)/test/", os.path.abspath(__file__))
sys.path.append(os.path.join(base_path.group(1), "src"))

from helm_images import Registry, get_registries


config = """
registries:
  - name: hub.docker.com
    retain: false
    push: true
  - name: k8s.io
    retain: false
    push: false
  - name: gcr.io
    retain: true
  - name: ecr.aws
"""


@pytest.mark.parametrize(
    "g_push,g_retain",
    [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ],
)
def test_get_registries(g_push, g_retain):
    registries_config = yaml.safe_load(config)["registries"]
    charts = get_registries(registries_config, g_push, g_retain)
    expected = [
        Registry("hub.docker.com", True, False),
        Registry("k8s.io", False, False),
        Registry("gcr.io", g_push, True),
        Registry("ecr.aws", g_push, g_retain),
    ]
    assert charts == expected