#!/usr/bin/python3

import os
import re
import sys
import pytest

import yaml

base_path = re.search('^(.*)/test/', os.path.abspath(__file__))
sys.path.append(os.path.join(base_path.group(1), 'src'))

from helm_images import Chart, get_charts

config ='''
charts:
  # chart specific true
  - fetch: true
    repo: stable
    name: redis
    versions:
    - fetch: true
      local_dir: tc1
      version: 1.0.0
    - fetch: false
      local_dir: tc2
      version: 2.0.0
    - local_dir: tc3
      version: 3.0.0
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
'''

@pytest.mark.parametrize("global_fetch_policy", [True, False])
def test_get_charts(global_fetch_policy):
    charts_config = yaml.safe_load(config)["charts"]
    charts = get_charts(charts_config, global_fetch_policy)
    expected = [
      Chart("stable", "redis", "1.0.0", "tc1", True),
      Chart("stable", "redis", "2.0.0", "tc2", False),
      Chart("stable", "redis", "3.0.0", "tc3", True),
      Chart("prod", "mongo", "4.0.0", "tc4", True),
      Chart("prod", "mongo", "5.0.0", "tc5", False),
      Chart("prod", "mongo", "6.0.0", "/tmp/prod/mongo/2", False),
      Chart("staging", "influx", "7.0.0", "tc7", True),
      Chart("staging", "influx", "8.0.0", "tc8", False),
      Chart("staging", "influx", "9.0.0", "/tmp/staging/influx/2", global_fetch_policy),
    ]
    assert charts == expected


