import pytest

from robottelo.config import settings
from robottelo.hosts import Capsule


@pytest.fixture(scope="function")
def dependent_scenario_name(request):
    """
    This fixture is used to collect the depend test case name.
    """
    depend_test_name = [
        mark.kwargs['depend_on'].__name__
        for mark in request.node.own_markers
        if 'depend_on' in mark.kwargs
    ][0]
    yield depend_test_name


@pytest.fixture(scope='session', params=[True, False], ids=["satellite", "capsule"])
def upgrade_server(request, default_sat):
    """
    This fixture is used to return the upgrade Satellite and Capsule instances.
    """
    if request.param:
        return default_sat
    else:
        return Capsule(settings.upgrade.capsule_hostname)
