import concurrent.futures
import contextlib
import json
import logging
import random
import threading
from collections import deque
from subprocess import check_output

import pytest
import requests
import retrying

from pkgpanda.build import load_json
from test_util.marathon import get_test_app, get_test_app_in_docker, get_test_app_in_ucr


log = logging.getLogger(__name__)
timeout = 500
maxthreads = 8


def lb_enabled():
    config = load_json('/opt/mesosphere/etc/expanded.config.json')
    return config['enable_lb'] == 'true'


@retrying.retry(wait_fixed=2000,
                stop_max_delay=timeout * 1000,
                retry_on_result=lambda ret: ret is False,
                retry_on_exception=lambda x: True)
def ensure_routable(cmd, service_points):
    proxy_uri = 'http://{}:{}/run_cmd'.format(service_points[0].host, service_points[0].port)
    log.info('Sending {} data: {}'.format(proxy_uri, cmd))
    r = requests.post(proxy_uri, data=cmd)
    log.info('Requests Response: %s', repr(r.json()))
    assert r.json()['status'] == 0
    return json.loads(r.json()['output'])


class VipTest:
    def __init__(self, num, container, vip, vipaddr, samehost, vipnet, proxynet):
        self.vip = vip.format(num, 7000 + num)
        self.container = container
        self.vipaddr = vipaddr.format(num, 7000 + num)
        self.samehost = samehost
        self.vipnet = vipnet
        self.proxynet = proxynet

    def __str__(self):
        return ("VipTest(container={}, vip={},vipaddr={},samehost={},"
                "vipnet={},proxynet={})").format(self.container, self.vip, self.vipaddr,
                                                 self.samehost, self.vipnet, self.proxynet)

    def log(self, s, lvl=logging.DEBUG):
        m = 'VIP_TEST {} {}'.format(s, self)
        log.log(lvl, m)


def docker_vip_app(network, host, vip):
    app, uuid = get_test_app_in_docker()
    app['container']['docker']['network'] = network

    app['mem'] = 16
    app['cpu'] = 0.01
    if network == 'USER':
        app['ipAddress'] = {'networkName': 'dcos'}
    if network == 'HOST':
        app['cmd'] = '/opt/mesosphere/bin/dcos-shell python '\
                     '/opt/mesosphere/active/dcos-integration-test/util/python_test_server.py $PORT0'
        app['container']['docker']['portMappings'][0]['hostPort'] = 0
        app['container']['docker']['portMappings'][0]['containerPort'] = 0
        app['container']['docker']['portMappings'][0]['labels'] = {}
        if vip is not None:
            app['portDefinitions'] = [{'labels': {'VIP_0': vip}}]
    elif vip is not None:
        app['container']['docker']['portMappings'][0]['labels'] = {'VIP_0': vip}

    app['constraints'] = [['hostname', 'CLUSTER', host]]
    return app, uuid


def ucr_vip_app(network, host, vip):
    app, uuid = get_test_app_in_ucr()
    app['mem'] = 16
    app['cpu'] = 0.01
    app["ipAddress"] = {
        "discovery": {
            "ports": [{
                "labels": {
                    "VIP_0": vip
                }
            }]
        }
    }
    assert network is not 'BRIDGE'
    if network == 'USER':
        app['ipAddress']['networkName'] = 'dcos'
    app['constraints'] = [['hostname', 'CLUSTER', host]]


def vip_app(container, network, host, vip):
    if container == 'UCR':
        return ucr_vip_app(network, host, vip)
    if container == 'DOCKER':
        return docker_vip_app(network, host, vip)
    assert False


def vip_test(dcos_api_session, r):
    r.log('START')
    agents = list(dcos_api_session.slaves)
    # make sure we can reproduce
    random.seed(r.vip)
    random.shuffle(agents)
    host1 = agents[0]
    host2 = agents[0]
    if not r.samehost:
        host2 = agents[1]
    log.debug('host1 is is: {}'.format(host1))
    log.debug('host2 is is: {}'.format(host2))

    origin_app, app_uuid = vip_app(r.container, r.vipnet, host1, r.vip)
    proxy_app, _ = vip_app(r.container, r.proxynet, host2, None)

    returned_uuid = None
    with contextlib.ExitStack() as stack:
        stack.enter_context(dcos_api_session.marathon.deploy_and_cleanup(origin_app, timeout=timeout))
        sp = stack.enter_context(dcos_api_session.marathon.deploy_and_cleanup(proxy_app, timeout=timeout))
        cmd = '/opt/mesosphere/bin/curl -s -f -m 5 http://{}/test_uuid'.format(r.vipaddr)
        returned_uuid = ensure_routable(cmd, sp)
        log.debug('returned_uuid is: {}'.format(returned_uuid))
    assert returned_uuid is not None
    assert returned_uuid['test_uuid'] == app_uuid
    r.log('PASSED')


@pytest.fixture
def reduce_logging():
    start_log_level = logging.getLogger('test_util.marathon').getEffectiveLevel()
    # gotta go up to warning to mute it as its currently at info
    logging.getLogger('test_util.marathon').setLevel(logging.WARNING)
    yield
    logging.getLogger('test_util.marathon').setLevel(start_log_level)


@pytest.mark.skipif(not lb_enabled(), reason='Load Balancer disabled')
def test_vip(dcos_api_session, reduce_logging):
    """Test every permutation of VIP
    """
    addrs = [['1.1.1.{}:{}', '1.1.1.{}:{}'],
             ['/namedvip{}:{}', 'namedvip{}.marathon.l4lb.thisdcos.directory:{}']]
    # tests
    # UCR doesn't support BRIDGE mode
    permutations = [[c, vi, va, sh, vn, pn]
                    for c in ['UCR', 'DOCKER']
                    for [vi, va] in addrs
                    for sh in [True, False]
                    for vn in ['USER', 'BRIDGE', 'HOST']
                    for pn in ['USER', 'BRIDGE', 'HOST']
                    if c is not 'UCR' or (vn is not 'BRIDGE' and pn is not 'BRIDGE')]
    tests = [VipTest(i, c, vi, va, sh, vn, pn) for i, [c, vi, va, sh, vn, pn] in enumerate(permutations)]
    executor = concurrent.futures.ThreadPoolExecutor(workers=maxthreads)
    # deque is thread safe
    failed_tests = deque(tests)
    passed_tests = deque()
    skipped_tests = deque()
    # skip tests there are not enough agents to run them
    for r in tests:
        if not r.samehost and len(dcos_api_session.slaves) == 1:
            failed_tests.remove(r)
            skipped_tests.append(r)

    def run(test):
        vip_test(dcos_api_session, test)
        failed_tests.remove(test)
        passed_tests.append(test)

    tasks = [executor.submit(run, t) for t in failed_tests]
    for t in concurrent.futures.as_completed(tasks):
        try:
            t.result()
        except Exception as exc:
            log.info('vip_test generated an exception: {}'.format(exc))
    [r.log('PASSED', lvl=logging.INFO) for r in passed_tests]
    [r.log('SKIPPED', lvl=logging.INFO) for r in skipped_tests]
    [r.log('FAILED', lvl=logging.INFO) for r in failed_tests]
    log.info('VIP_TEST num agents: {}'.format(len(dcos_api_session.slaves)))
    assert len(failed_tests) == 0


@retrying.retry(wait_fixed=2000,
                stop_max_delay=timeout * 1000,
                retry_on_exception=lambda x: True)
def test_if_overlay_ok(dcos_api_session):
    def _check_overlay(hostname, port):
        overlays = dcos_api_session.get('overlay-agent/overlay', host=hostname, port=port).json()['overlays']
        assert len(overlays) > 0
        for overlay in overlays:
            assert overlay['state']['status'] == 'STATUS_OK'

    for master in dcos_api_session.masters:
        _check_overlay(master, 5050)
    for slave in dcos_api_session.all_slaves:
        _check_overlay(slave, 5051)


@pytest.mark.skipif(lb_enabled(), reason='Load Balancer enabled')
def test_if_minuteman_disabled(dcos_api_session):
    """Test to make sure minuteman is disabled"""
    data = check_output(["/usr/bin/env", "ip", "rule"])
    # Minuteman creates this ip rule: `9999: from 9.0.0.0/8 lookup 42`
    # We check it doesn't exist
    assert str(data).find('9999') == -1


def test_ip_per_container(dcos_api_session):
    """Test if we are able to connect to a task with ip-per-container mode
    """
    # Launch the test_server in ip-per-container mode
    app_definition, test_uuid = get_test_app_in_docker(ip_per_container=True)

    assert len(dcos_api_session.slaves) >= 2, "IP Per Container tests require 2 private agents to work"

    app_definition['instances'] = 2
    app_definition['constraints'] = [['hostname', 'UNIQUE']]

    with dcos_api_session.marathon.deploy_and_cleanup(app_definition, check_health=True) as service_points:
        app_port = app_definition['container']['docker']['portMappings'][0]['containerPort']
        cmd = '/opt/mesosphere/bin/curl -s -f -m 5 http://{}:{}/ping'.format(service_points[1].ip, app_port)
        ensure_routable(cmd, service_points)


@retrying.retry(wait_fixed=2000,
                stop_max_delay=100 * 2000,
                retry_on_exception=lambda x: True)
def geturl(url):
    rs = requests.get(url)
    assert rs.status_code == 200
    r = rs.json()
    log.info('geturl {} -> {}'.format(url, r))
    return r


@pytest.mark.skipif(not lb_enabled(), reason='Load Balancer disabled')
def test_l4lb(dcos_api_session):
    """Test l4lb is load balancing between all the backends
       * create 5 apps using the same VIP
       * get uuid from the VIP in parallel from many threads
       * verify that 5 uuids have been returned
       * only testing if all 5 are hit at least once
    """
    numapps = 5
    numthreads = numapps * 4
    apps = []
    rvs = deque()
    with contextlib.ExitStack() as stack:
        for _ in range(numapps):
            origin_app, origin_uuid = get_test_app()
            # same vip for all the apps
            origin_app['portDefinitions'][0]['labels'] = {'VIP_0': '/l4lbtest:5000'}
            apps.append(origin_app)
            sp = stack.enter_context(dcos_api_session.marathon.deploy_and_cleanup(origin_app))
            # make sure that the service point responds
            geturl('http://{}:{}/ping'.format(sp[0].host, sp[0].port))
            # make sure that the VIP is responding too
            geturl('http://l4lbtest.marathon.l4lb.thisdcos.directory:5000/ping')

            # make sure L4LB is actually doing some load balancing by making
            # many requests in parallel.
        def thread_request():
            # deque is thread safe
            rvs.append(geturl('http://l4lbtest.marathon.l4lb.thisdcos.directory:5000/test_uuid'))

        threads = [threading.Thread(target=thread_request) for i in range(0, numthreads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    expected_uuids = [a['id'].split('-')[2] for a in apps]
    received_uuids = [r['test_uuid'] for r in rvs if r is not None]
    assert len(set(expected_uuids)) == numapps
    assert len(set(received_uuids)) == numapps
    assert set(expected_uuids) == set(received_uuids)
