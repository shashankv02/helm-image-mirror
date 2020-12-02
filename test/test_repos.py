#!/usr/bin/python3

import os
import re
import sys
import pytest

import yaml

base_path = re.search("^(.*)/test/", os.path.abspath(__file__))
sys.path.append(os.path.join(base_path.group(1), "src"))

from helm_image_mirror import Repo, get_repo_objs, REPOS_KEY, REPOS_ADD_KEY

config = """
repos:
  add:
  - name: stable
    remote: https://kubernetes-charts.storage.googleapis.com
    username:
    password:
  - name: prod
    remote: https://aws.com
  - name: staging
    remote: https://gcr.io
    username: "user"
    password: "pass"
  - name: staging
    remote: https://gcr.io
    username: "user"
    password:
  - name: staging
    remote: https://gcr.io
    username: "user"
"""


@pytest.mark.parametrize(
    "g_username,g_password",
    [
        ("abc", "xyz"),
    ],
)
def test_get_repo_objs(g_username, g_password):
    repos_config = yaml.safe_load(config)[REPOS_KEY][REPOS_ADD_KEY]
    charts = get_repo_objs(repos_config, g_username, g_password)
    expected = [
        Repo("stable", "https://kubernetes-charts.storage.googleapis.com", None, None),
        Repo("prod", "https://aws.com", g_username, g_password),
        Repo("staging", "https://gcr.io", "user", "pass"),
        Repo("staging", "https://gcr.io", "user", None),
        Repo("staging", "https://gcr.io", "user", g_password),
    ]
    assert charts == expected


@pytest.mark.parametrize(
    "repo,expected",
    [
        (
            Repo("staging", "https://gcr.io", "user", "pass"),
            "repo add staging https://gcr.io --username user --password pass",
        ),
        (Repo("prod", "https://k8s.io", "user", None), "repo add prod https://k8s.io"),
        (Repo("prod", "https://k8s.io", None, "pass"), "repo add prod https://k8s.io"),
        (
            Repo("staging", "https://gcr.io", None, None),
            "repo add staging https://gcr.io",
        ),
    ],
)
def test_get_add_cmd(repo, expected):
    assert repo.get_add_cmd() == expected
