# coding: utf-8
"""Configurations for py.test runner"""
import datetime
import logging

import pytest

try:
    from pytest_reportportal import RPLogger, RPLogHandler
except ImportError:
    pass
from robottelo.config import settings
from robottelo.decorators import setting_is_set


def log(message, level="DEBUG"):
    """Pytest has a limitation to use logging.logger from conftest.py
    so we need to emulate the logger by stdouting the output
    """
    now = datetime.datetime.utcnow()
    full_message = "{date} - conftest - {level} - {message}".format(
        date=now.strftime("%Y-%m-%d %H:%M:%S"), level=level, message=message
    )
    print(full_message)  # noqa
    with open('robottelo.log', 'a') as log_file:
        log_file.write(full_message)


def pytest_report_header(config):
    """Called when pytest session starts"""
    messages = []

    shared_function_enabled = 'OFF'
    scope = ''
    storage = 'file'
    if setting_is_set('shared_function'):
        if settings.shared_function.enabled:
            shared_function_enabled = 'ON'
        scope = settings.shared_function.scope
        if not scope:
            scope = ''
        storage = settings.shared_function.storage
    messages.append(
        'shared_function enabled - {0} - scope: {1} - storage: {2}'.format(
            shared_function_enabled, scope, storage
        )
    )

    return messages


@pytest.fixture(scope="session")
def worker_id(request):
    """Gets the worker ID when running in multi-threading with xdist
    """
    if hasattr(request.config, 'slaveinput'):
        # return gw+(0..n)
        return request.config.slaveinput['slaveid']
    else:
        return 'master'


@pytest.fixture(scope="session")
def configured_settings():
    if not settings.configured:
        settings.configure()
    return settings


@pytest.fixture(autouse=True, scope='module')
def robottelo_logger(request, worker_id):
    """Set up a separate logger for each pytest-xdist worker
    if worker_id != 'master' then xdist is running in multi-threading so
    a logfile named 'robottelo_gw{worker_id}.log' will be created.
    """
    logger = logging.getLogger('robottelo')
    if (
        hasattr(request.session.config, '_reportportal_configured')
        and request.session.config._reportportal_configured
    ):
        logging.setLoggerClass(RPLogger)
    if '{0}'.format(worker_id) not in [h.get_name() for h in logger.handlers]:
        if worker_id != 'master':
            formatter = logging.Formatter(
                fmt='%(asctime)s - {0} - %(name)s - %(levelname)s -'
                ' %(message)s'.format(worker_id),
                datefmt='%Y-%m-%d %H:%M:%S',
            )
            handler = logging.FileHandler('robottelo_{0}.log'.format(worker_id))
            handler.set_name('{0}'.format(worker_id))
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            # Nailgun HTTP logs should also be included in gw* logs
            logging.getLogger('nailgun').addHandler(handler)
            if (
                hasattr(request.session.config, '_reportportal_configured')
                and request.session.config._reportportal_configured
            ):
                rp_handler = RPLogHandler(request.node.config.py_test_service)
                rp_handler.set_name('{0}'.format(worker_id))
                rp_handler.setFormatter(formatter)
                logger.addHandler(rp_handler)
                logging.getLogger('nailgun').addHandler(rp_handler)
    return logger


@pytest.fixture(autouse=True)
def log_test_execution(robottelo_logger, request):
    test_name = request.node.name
    parent_name = request.node.parent.name
    test_full_name = '{}/{}'.format(parent_name, test_name)
    robottelo_logger.debug('Started Test: {}'.format(test_full_name))
    yield None
    robottelo_logger.debug('Finished Test: {}'.format(test_full_name))


def pytest_collection_modifyitems(session, items, config):
    """Called after collection has been performed, may filter or re-order
    the items in-place.
    """

    log("Collected %s test cases" % len(items))

    # Modify items based on collected issue_data
    deselected_items = []

    for item in items:
        # 1. Deselect tests marked with @pytest.mark.deselect
        # WONTFIX BZs makes test to be dynamically marked as deselect.
        deselect = item.get_closest_marker('deselect')
        if deselect:
            deselected_items.append(item)
            reason = deselect.kwargs.get('reason', deselect.args)
            log(f"Deselected test '{item.name}' reason: {reason}")
            # Do nothing more with deselected tests
            continue

    config.hook.pytest_deselected(items=deselected_items)
    items[:] = [item for item in items if item not in deselected_items]


@pytest.fixture(autouse=True, scope="session")
def record_testsuite_timestamp_xml(record_testsuite_property):
    now = datetime.datetime.utcnow()
    record_testsuite_property("start_time", now.strftime("%Y-%m-%dT%H:%M:%S"))


@pytest.fixture(autouse=True, scope="function")
def record_test_timestamp_xml(record_property):
    now = datetime.datetime.utcnow()
    record_property("start_time", now.strftime("%Y-%m-%dT%H:%M:%S"))
