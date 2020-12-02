#!/usr/bin/python3

import os
import re
import sys

import yaml

base_path = re.search('^(.*)/test/', os.path.abspath(__file__))
sys.path.append(os.path.join(base_path.group(1), 'src'))

from helm_images import Chart, get_charts

config ='''
# global fetch policy, chart fetch policy, version fetch policy, expected version policy
# true, true, true, true
# true, true, false, false
# true, false, true, true
# true, false, false, false
# false, true, true, true
# false, true, false, false
# false, false, true, true
# false, false, false, false
# none, none, none, none
# none, true, none, none
# none, false, none, none
# none, none, false, false
# true, none, none, none
# false, none, none, none
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
'''
'''
  # chart specific unspecified
  - repo: prod
    name: mongo
    versions:
    - fetch: true
      local_dir:
      version: 3.0.0
    - fetch: false
      local_dir: /tmp/redis/2.0.0
      version: 2.0.0
    - local_dir: unspecified
      version: 1.0.0
'''

def test_get_charts():
    charts_config = yaml.safe_load(config)["charts"]
    charts = get_charts(charts_config, True)
    expected = [
      Chart("stable", "redis", "1.0.0", "tc1", True),
      Chart("stable", "redis", "2.0.0", "tc2", False),
      Chart("stable", "redis", "3.0.0", "tc3", True),
      Chart("prod", "mongo", "4.0.0", "tc4", True),
      Chart("prod", "mongo", "5.0.0", "tc5", False),
      Chart("prod", "mongo", "6.0.0", "/tmp/mongo/2", False),
    ]
    assert charts == expected


