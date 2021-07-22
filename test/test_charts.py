#!/usr/bin/python3

import os
import re
import sys
import pytest

import yaml

base_path = re.search("^(.*)/test/", os.path.abspath(__file__))
sys.path.append(os.path.join(base_path.group(1), "src"))

from helm_image_mirror import Chart, get_charts

config = """
charts:
  # chart specific true
  - fetch: true
    repo: stable
    name: redis
    values:
      set: abc.xyz=1
      set_str: pqr.xyz=true
    push:
      - target1
      - target2
    versions:
    - fetch: true
      local_dir: tc1
      version: 1.0.0
      values:
        set: abc.xyz=2
        set_str: qwe.rty=false
    - fetch: false
      local_dir: tc2
      version: 2.0.0
    - local_dir: tc3
      version: 3.0.0
      push:
        - target3
  # chart specific false
  - fetch: false
    repo: prod
    name: mongo
    versions:
    - fetch: true
      version: 4.0.0
      local_dir: tc4
    - fetch: false
      local_dir: tc5
      version: 5.0.0
    - version: 6.0.0
  # chart specific unspecified
  - repo: staging
    name: influx
    versions:
    - fetch: true
      local_dir: tc7
      version: 7.0.0
    - fetch: false
      local_dir: tc8
      version: 8.0.0
    - local_dir:
      version: 9.0.0
"""


@pytest.mark.parametrize("global_fetch_policy", [True, False])
def test_get_charts(global_fetch_policy):
    charts_config = yaml.safe_load(config)["charts"]
    charts = get_charts(charts_config, global_fetch_policy)
    group1_values = {"set": "abc.xyz=1", "set_str": "pqr.xyz=true"}
    expected = [
        Chart("stable", "redis", "1.0.0", "tc1", True, 
          {"set": "abc.xyz=2", "set_str": "qwe.rty=false"}, ['target1', 'target2']),
        Chart("stable", "redis", "2.0.0", "tc2", False, group1_values, ['target1', 'target2']),
        Chart("stable", "redis", "3.0.0", "tc3", True, group1_values, ['target3']),
        Chart("prod", "mongo", "4.0.0", "tc4", True),
        Chart("prod", "mongo", "5.0.0", "tc5", False),
        Chart("prod", "mongo", "6.0.0", "/tmp/prod/mongo/2", False),
        Chart("staging", "influx", "7.0.0", "tc7", True),
        Chart("staging", "influx", "8.0.0", "tc8", False),
        Chart(
            "staging", "influx", "9.0.0", "/tmp/staging/influx/2", global_fetch_policy
        ),
    ]
    assert charts == expected


@pytest.mark.parametrize(
    "chart,expected",
    [
        (
          Chart("stable", "redis", "1.0.0", "tc1", True, {"set": "abx.xyz=1,abc.pqr=2", "set_string": "abc.asd=True"}),
          "template  --set abx.xyz=1,abc.pqr=2 --set-string abc.asd=True tc1/redis"
        ),
        (
          Chart("stable", "redis", "1.0.0", "tc1", True, {"set": "abx.xyz=1,abc.pqr=2"}),
          "template  --set abx.xyz=1,abc.pqr=2 tc1/redis"
        ),
         (
          Chart("stable", "redis", "1.0.0", "tc1", True, {}),
          "template  tc1/redis"
        )
    ],
)
def test_get_add_cmd(chart, expected):
    assert chart.get_template_cmd() == expected