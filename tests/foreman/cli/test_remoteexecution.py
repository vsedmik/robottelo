# -*- encoding: utf-8 -*-
"""Test class for Remote Execution Management UI

:Requirement: Remoteexecution

:CaseAutomation: Automated

:CaseLevel: Acceptance

:CaseComponent: RemoteExecution

:TestType: Functional

:CaseImportance: High

:Upstream: No
"""
from datetime import datetime
from datetime import timedelta
from time import sleep

import pytest
from fauxfactory import gen_string
from nailgun import entities
from wait_for import wait_for

from robottelo import ssh
from robottelo.cli.factory import make_job_invocation
from robottelo.cli.factory import make_job_template
from robottelo.cli.host import Host
from robottelo.cli.job_invocation import JobInvocation
from robottelo.cli.recurring_logic import RecurringLogic
from robottelo.cli.task import Task
from robottelo.config import settings
from robottelo.constants import DISTRO_DEFAULT
from robottelo.constants import DISTRO_RHEL7
from robottelo.constants import DISTRO_SLES11
from robottelo.constants import DISTRO_SLES12
from robottelo.constants.repos import FAKE_0_YUM_REPO
from robottelo.decorators import skip_if
from robottelo.decorators import skip_if_not_set
from robottelo.decorators import tier3
from robottelo.decorators import upgrade
from robottelo.helpers import add_remote_execution_ssh_key
from robottelo.test import CLITestCase
from robottelo.vm import VirtualMachine

TEMPLATE_FILE = 'template_file.txt'
TEMPLATE_FILE_EMPTY = 'template_file_empty.txt'
distros = [DISTRO_DEFAULT]


@pytest.fixture(scope="module")
def fixture_org():
    org = entities.Organization().create()
    ssh.command('''echo 'echo Enforcing' > {0}'''.format(TEMPLATE_FILE))
    # needed to work around BZ#1656480
    ssh.command('''sed -i '/ProxyCommand/s/^/#/g' /etc/ssh/ssh_config''')
    return org


@pytest.fixture(params=distros, scope="module")
def fixture_vmsetup(request, fixture_org):
    """Create Org, Lifecycle Environment, Content View, Activation key,
    VM, install katello-ca, register it, add remote execution key
    """
    # Create VM and register content host
    client = VirtualMachine(distro=request.param)
    try:
        client.create()
        if request.param in [DISTRO_SLES11, DISTRO_SLES12]:
            # SLES hostname in subscription-manager facts doesn't include domain
            client._hostname = client.hostname.split(".")[0]
        client.install_katello_ca()
        # Register content host
        client.register_contenthost(org=fixture_org.label, lce='Library')
        assert client.subscribed
        add_remote_execution_ssh_key(client.ip_addr)
        yield client
    finally:
        client._hostname = None
        client.destroy()


class TestRemoteExecution:
    """Implements job execution tests in CLI."""

    @pytest.mark.stubbed
    @tier3
    def test_positive_run_job_multiple_hosts_time_span(self):
        """Run job against multiple hosts with time span setting

        :id: 82d69069-0592-4083-8992-8969235cc8c9

        :expectedresults: Verify the jobs were successfully distributed
            across the specified time sequence
        """
        # currently it is not possible to get subtasks from
        # a task other than via UI

    @pytest.mark.stubbed
    @tier3
    @upgrade
    def test_positive_run_job_multiple_hosts_concurrency(self):
        """Run job against multiple hosts with concurrency-level

        :id: 15639753-fe50-4e33-848a-04fe464947a6

        :expectedresults: Verify the number of running jobs does comply
            with the concurrency-level setting
        """
        # currently it is not possible to get subtasks from
        # a task other than via UI

    @tier3
    def test_positive_run_default_job_template_by_ip(self, fixture_vmsetup, fixture_org):
        """Run default template on host connected by ip and list task

        :id: 811c7747-bec6-4a2d-8e5c-b5045d3fbc0d

        :expectedresults: Verify the job was successfully ran against the host
            and task can be listed by name and ID

        :BZ: 1647582

        :parametrized: yes
        """
        self.org = fixture_org
        self.client = fixture_vmsetup
        # set connecting to host via ip
        Host.set_parameter(
            {
                'host': self.client.hostname,
                'name': 'remote_execution_connect_by_ip',
                'value': 'True',
            }
        )
        command = "echo {0}".format(gen_string('alpha'))
        invocation_command = make_job_invocation(
            {
                'job-template': 'Run Command - SSH Default',
                'inputs': 'command={0}'.format(command),
                'search-query': "name ~ {0}".format(self.client.hostname),
            }
        )

        try:
            assert invocation_command['success'] == '1'
        except AssertionError:
            result = 'host output: {0}'.format(
                ' '.join(
                    JobInvocation.get_output(
                        {'id': invocation_command['id'], 'host': self.client.hostname}
                    )
                )
            )
            raise AssertionError(result)

        task = Task.list_tasks({"search": command})[0]
        search = Task.list_tasks({"search": 'id={0}'.format(task["id"])})
        assert search[0]["action"] == task["action"]

    @pytest.mark.skip_if_open('BZ:1804685')
    @tier3
    def test_positive_run_job_effective_user_by_ip(self, fixture_vmsetup, fixture_org):
        """Run default job template as effective user on a host by ip

        :id: 0cd75cab-f699-47e6-94d3-4477d2a94bb7

        :BZ: 1451675

        :expectedresults: Verify the job was successfully run under the
            effective user identity on host

        :parametrized: yes
        """
        self.org = fixture_org
        self.client = fixture_vmsetup
        # set connecting to host via ip
        Host.set_parameter(
            {
                'host': self.client.hostname,
                'name': 'remote_execution_connect_by_ip',
                'value': 'True',
            }
        )
        # create a user on client via remote job
        username = gen_string('alpha')
        filename = gen_string('alpha')
        make_user_job = make_job_invocation(
            {
                'job-template': 'Run Command - SSH Default',
                'inputs': "command='useradd -m {0}'".format(username),
                'search-query': "name ~ {0}".format(self.client.hostname),
            }
        )
        try:
            assert make_user_job['success'] == '1'
        except AssertionError:
            result = 'host output: {0}'.format(
                ' '.join(
                    JobInvocation.get_output(
                        {'id': make_user_job['id'], 'host': self.client.hostname}
                    )
                )
            )
            raise AssertionError(result)
        # create a file as new user
        invocation_command = make_job_invocation(
            {
                'job-template': 'Run Command - SSH Default',
                'inputs': "command='touch /home/{0}/{1}'".format(username, filename),
                'search-query': "name ~ {0}".format(self.client.hostname),
                'effective-user': '{0}'.format(username),
            }
        )
        try:
            assert invocation_command['success'] == '1'
        except AssertionError:
            result = 'host output: {0}'.format(
                ' '.join(
                    JobInvocation.get_output(
                        {'id': invocation_command['id'], 'host': self.client.hostname}
                    )
                )
            )
            raise AssertionError(result)
        # check the file owner
        result = ssh.command(
            '''stat -c '%U' /home/{0}/{1}'''.format(username, filename),
            hostname=self.client.ip_addr,
        )
        # assert the file is owned by the effective user
        assert username == result.stdout[0]

    @tier3
    def test_positive_run_custom_job_template_by_ip(self, fixture_vmsetup, fixture_org):
        """Run custom template on host connected by ip

        :id: 9740eb1d-59f5-42b2-b3ab-659ca0202c74

        :expectedresults: Verify the job was successfully ran against the host

        :parametrized: yes
        """
        self.org = fixture_org
        self.client = fixture_vmsetup
        # set connecting to host via ip
        Host.set_parameter(
            {
                'host': self.client.hostname,
                'name': 'remote_execution_connect_by_ip',
                'value': 'True',
            }
        )
        template_name = gen_string('alpha', 7)
        make_job_template(
            {'organizations': self.org.name, 'name': template_name, 'file': TEMPLATE_FILE}
        )
        invocation_command = make_job_invocation(
            {
                'job-template': template_name,
                'search-query': "name ~ {0}".format(self.client.hostname),
            }
        )
        try:
            assert invocation_command['success'] == '1'
        except AssertionError:
            result = 'host output: {0}'.format(
                ' '.join(
                    JobInvocation.get_output(
                        {'id': invocation_command['id'], 'host': self.client.hostname}
                    )
                )
            )
            raise AssertionError(result)

    @tier3
    @upgrade
    def test_positive_run_default_job_template_multiple_hosts_by_ip(
        self, fixture_vmsetup, fixture_org
    ):
        """Run default job template against multiple hosts by ip

        :id: 694a21d3-243b-4296-8bd0-4bad9663af15

        :expectedresults: Verify the job was successfully ran against all hosts

        :parametrized: yes
        """
        self.org = fixture_org
        self.client = fixture_vmsetup
        Host.set_parameter(
            {
                'host': self.client.hostname,
                'name': 'remote_execution_connect_by_ip',
                'value': 'True',
            }
        )
        with VirtualMachine(distro=DISTRO_RHEL7) as client2:
            client2.install_katello_ca()
            client2.register_contenthost(self.org.label, lce='Library')
            add_remote_execution_ssh_key(client2.ip_addr)
            Host.set_parameter(
                {
                    'host': client2.hostname,
                    'name': 'remote_execution_connect_by_ip',
                    'value': 'True',
                }
            )
            invocation_command = make_job_invocation(
                {
                    'job-template': 'Run Command - SSH Default',
                    'inputs': 'command="ls"',
                    'search-query': "name ~ {0} or name ~ {1}".format(
                        self.client.hostname, client2.hostname
                    ),
                }
            )
            # collect output messages from clients
            output_msgs = []
            for vm in self.client, client2:
                output_msgs.append(
                    'host output from {0}: {1}'.format(
                        vm.hostname,
                        ' '.join(
                            JobInvocation.get_output(
                                {'id': invocation_command['id'], 'host': vm.hostname}
                            )
                        ),
                    )
                )
            assert invocation_command['success'] == '2', output_msgs

    @tier3
    @skip_if(not settings.repos_hosting_url)
    def test_positive_install_multiple_packages_with_a_job_by_ip(
        self, fixture_vmsetup, fixture_org
    ):
        """Run job to install several packages on host by ip

        :id: 8b73033f-83c9-4024-83c3-5e442a79d320

        :expectedresults: Verify the packages were successfully installed
            on host

        :parametrized: yes
        """
        self.org = fixture_org
        self.client = fixture_vmsetup
        # set connecting to host by ip
        Host.set_parameter(
            {
                'host': self.client.hostname,
                'name': 'remote_execution_connect_by_ip',
                'value': 'True',
            }
        )
        packages = ["cow", "dog", "lion"]
        # Create a custom repo
        repo = entities.Repository(
            content_type='yum',
            product=entities.Product(organization=self.org).create(),
            url=FAKE_0_YUM_REPO,
        ).create()
        repo.sync()
        prod = repo.product.read()
        subs = entities.Subscription().search(query={'search': 'name={0}'.format(prod.name)})
        assert len(subs) > 0, 'No subscriptions matching the product returned'

        ak = entities.ActivationKey(
            organization=self.org,
            content_view=self.org.default_content_view,
            environment=self.org.library,
        ).create()
        ak.add_subscriptions(data={'subscriptions': [{'id': subs[0].id}]})
        self.client.register_contenthost(org=self.org.label, activation_key=ak.name)

        invocation_command = make_job_invocation(
            {
                'job-template': 'Install Package - Katello SSH Default',
                'inputs': 'package={0} {1} {2}'.format(*packages),
                'search-query': "name ~ {0}".format(self.client.hostname),
            }
        )
        try:
            assert invocation_command['success'] == '1'
        except AssertionError:
            result = 'host output: {0}'.format(
                ' '.join(
                    JobInvocation.get_output(
                        {'id': invocation_command['id'], 'host': self.client.hostname}
                    )
                )
            )
            raise AssertionError(result)
        result = ssh.command("rpm -q {0}".format(" ".join(packages)), hostname=self.client.ip_addr)
        assert result.return_code == 0

    @tier3
    def test_positive_run_recurring_job_with_max_iterations_by_ip(
        self, fixture_vmsetup, fixture_org
    ):
        """Run default job template multiple times with max iteration by ip

        :id: 0a3d1627-95d9-42ab-9478-a908f2a7c509

        :expectedresults: Verify the job was run not more than the specified
            number of times.

        :parametrized: yes
        """
        self.org = fixture_org
        self.client = fixture_vmsetup
        # set connecting to host by ip
        Host.set_parameter(
            {
                'host': self.client.hostname,
                'name': 'remote_execution_connect_by_ip',
                'value': 'True',
            }
        )
        invocation_command = make_job_invocation(
            {
                'job-template': 'Run Command - SSH Default',
                'inputs': 'command="ls"',
                'search-query': "name ~ {0}".format(self.client.hostname),
                'cron-line': '* * * * *',  # every minute
                'max-iteration': 2,  # just two runs
            }
        )

        JobInvocation.get_output({'id': invocation_command['id'], 'host': self.client.hostname})
        try:
            assert invocation_command['status'] == 'queued'
        except AssertionError:
            result = 'host output: {0}'.format(
                ' '.join(
                    JobInvocation.get_output(
                        {'id': invocation_command['id'], 'host': self.client.hostname}
                    )
                )
            )
            raise AssertionError(result)

        sleep(150)
        rec_logic = RecurringLogic.info({'id': invocation_command['recurring-logic-id']})
        assert rec_logic['state'] == 'finished'
        assert rec_logic['iteration'] == '2'

    @tier3
    def test_positive_run_scheduled_job_template_by_ip(self, fixture_vmsetup, fixture_org):
        """Schedule a job to be ran against a host

        :id: 0407e3de-ef59-4706-ae0d-b81172b81e5c

        :expectedresults: Verify the job was successfully ran after the
            designated time

        :parametrized: yes
        """
        self.org = fixture_org
        self.client = fixture_vmsetup
        system_current_time = ssh.command('date --utc +"%b %d %Y %I:%M%p"').stdout[0]
        current_time_object = datetime.strptime(system_current_time, '%b %d %Y %I:%M%p')
        plan_time = (current_time_object + timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M")
        Host.set_parameter(
            {
                'host': self.client.hostname,
                'name': 'remote_execution_connect_by_ip',
                'value': 'True',
            }
        )
        invocation_command = make_job_invocation(
            {
                'job-template': 'Run Command - SSH Default',
                'inputs': 'command="ls"',
                'start-at': plan_time,
                'search-query': "name ~ {0}".format(self.client.hostname),
            }
        )
        # Wait until the job runs
        pending_state = '1'
        while pending_state != '0':
            invocation_info = JobInvocation.info({'id': invocation_command['id']})
            pending_state = invocation_info['pending']
            sleep(30)
        invocation_info = JobInvocation.info({'id': invocation_command['id']})
        try:
            assert invocation_info['success'] == '1'
        except AssertionError:
            result = 'host output: {0}'.format(
                ' '.join(
                    JobInvocation.get_output(
                        {'id': invocation_command['id'], 'host': self.client.hostname}
                    )
                )
            )
            raise AssertionError(result)

    @tier3
    @upgrade
    def test_positive_run_receptor_installer(self):
        """Run Receptor installer ("Configure Cloud Connector")

        :CaseComponent: RHCloud-CloudConnector

        :id: 811c7747-bec6-1a2d-8e5c-b5045d3fbc0d

        :expectedresults: The job passes, installs Receptor that peers with c.r.c

        :BZ: 1818076
        """
        template_name = 'Configure Cloud Connector'
        invocation = make_job_invocation(
            {
                'async': True,
                'job-template': template_name,
                'inputs': 'satellite_user="{0}",satellite_password="{1}"'.format(
                    settings.server.admin_username, settings.server.admin_password
                ),
                'search-query': "name ~ {0}".format(settings.server.hostname),
            }
        )
        invocation_id = invocation['id']

        wait_for(
            lambda: entities.JobInvocation(id=invocation_id).read().status_label
            in ["succeeded", "failed"],
            timeout="1500s",
        )
        assert entities.JobInvocation(id=invocation_id).read().status == 0

        result = ' '.join(
            JobInvocation.get_output({'id': invocation_id, 'host': settings.server.hostname})
        )
        assert 'project-receptor.satellite_receptor_installer' in result
        assert 'Exit status: 0' in result
        # check that there is one receptor conf file and it's only readable
        # by the receptor user and root
        result = ssh.command('stat /etc/receptor/*/receptor.conf --format "%a:%U"')
        assert result.stdout[0] == '400:foreman-proxy'
        result = ssh.command('ls -l /etc/receptor/*/receptor.conf | wc -l')
        assert result.stdout[0] == '1'


class TestAnsibleREX:
    """Test class for remote execution via Ansible"""

    @tier3
    @upgrade
    def test_positive_run_effective_user_job(self, fixture_vmsetup, fixture_org):
        """Tests Ansible REX job having effective user runs successfully

        :id: a5fa20d8-c2bd-4bbf-a6dc-bf307b59dd8c

        :Steps:

            0. Create a VM and register to SAT and prepare for REX (ssh key)

            1. Run Ansible Command job for the host to create a user

            2. Run Ansible Command job using effective user

            3. Check the job result at the host is done under that user

        :expectedresults: multiple asserts along the code

        :CaseAutomation: automated

        :CaseLevel: System

        :parametrized: yes
        """
        self.org = fixture_org
        self.client = fixture_vmsetup
        # set connecting to host via ip
        Host.set_parameter(
            {
                'host': self.client.hostname,
                'name': 'remote_execution_connect_by_ip',
                'value': 'True',
            }
        )
        # create a user on client via remote job
        username = gen_string('alpha')
        filename = gen_string('alpha')
        make_user_job = make_job_invocation(
            {
                'job-template': 'Run Command - Ansible Default',
                'inputs': "command='useradd -m {0}'".format(username),
                'search-query': "name ~ {0}".format(self.client.hostname),
            }
        )
        try:
            assert make_user_job['success'] == '1'
        except AssertionError:
            result = 'host output: {0}'.format(
                ' '.join(
                    JobInvocation.get_output(
                        {'id': make_user_job['id'], 'host': self.client.hostname}
                    )
                )
            )
            raise AssertionError(result)
        # create a file as new user
        invocation_command = make_job_invocation(
            {
                'job-template': 'Run Command - Ansible Default',
                'inputs': "command='touch /home/{0}/{1}'".format(username, filename),
                'search-query': "name ~ {0}".format(self.client.hostname),
                'effective-user': '{0}'.format(username),
            }
        )
        try:
            assert invocation_command['success'] == '1'
        except AssertionError:
            result = 'host output: {0}'.format(
                ' '.join(
                    JobInvocation.get_output(
                        {'id': invocation_command['id'], 'host': self.client.hostname}
                    )
                )
            )
            raise AssertionError(result)
        # check the file owner
        result = ssh.command(
            '''stat -c '%U' /home/{0}/{1}'''.format(username, filename),
            hostname=self.client.ip_addr,
        )
        # assert the file is owned by the effective user
        assert username == result.stdout[0], "file ownership mismatch"

    @tier3
    @upgrade
    def test_positive_run_reccuring_job(self, fixture_vmsetup, fixture_org):
        """Tests Ansible REX reccuring job runs successfully multiple times

        :id: 49b0d31d-58f9-47f1-aa5d-561a1dcb0d66

        :Steps:

            0. Create a VM and register to SAT and prepare for REX (ssh key)

            1. Run recurring Ansible Command job for the host

            2. Check the multiple job results at the host

        :expectedresults: multiple asserts along the code

        :CaseAutomation: automated

        :CaseLevel: System

        :parametrized: yes
        """
        self.org = fixture_org
        self.client = fixture_vmsetup
        # set connecting to host by ip
        Host.set_parameter(
            {
                'host': self.client.hostname,
                'name': 'remote_execution_connect_by_ip',
                'value': 'True',
            }
        )
        invocation_command = make_job_invocation(
            {
                'job-template': 'Run Command - Ansible Default',
                'inputs': 'command="ls"',
                'search-query': "name ~ {0}".format(self.client.hostname),
                'cron-line': '* * * * *',  # every minute
                'max-iteration': 2,  # just two runs
            }
        )
        JobInvocation.get_output({'id': invocation_command['id'], 'host': self.client.hostname})
        try:
            assert invocation_command['status'] == 'queued'
        except AssertionError:
            result = 'host output: {0}'.format(
                ' '.join(
                    JobInvocation.get_output(
                        {'id': invocation_command['id'], 'host': self.client.hostname}
                    )
                )
            )
            raise AssertionError(result)
        sleep(150)
        rec_logic = RecurringLogic.info({'id': invocation_command['recurring-logic-id']})
        assert rec_logic['state'] == 'finished'
        assert rec_logic['iteration'] == '2'

    @tier3
    @upgrade
    @skip_if(not settings.repos_hosting_url)
    def test_positive_run_packages_and_services_job(self, fixture_vmsetup, fixture_org):
        """Tests Ansible REX job can install packages and start services

        :id: 47ed82fb-77ca-43d6-a52e-f62bae5d3a42

        :Steps:

            0. Create a VM and register to SAT and prepare for REX (ssh key)

            1. Run Ansible Package job for the host to install a package

            2. Check the package is present at the host

            3. Run Ansible Service job for the host to start a service

            4. Check the service is started on the host

        :expectedresults: multiple asserts along the code

        :CaseAutomation: automated

        :CaseLevel: System

        :parametrized: yes
        """
        self.org = fixture_org
        self.client = fixture_vmsetup
        # set connecting to host by ip
        Host.set_parameter(
            {
                'host': self.client.hostname,
                'name': 'remote_execution_connect_by_ip',
                'value': 'True',
            }
        )
        packages = ["cow"]
        # Create a custom repo
        repo = entities.Repository(
            content_type='yum',
            product=entities.Product(organization=self.org).create(),
            url=FAKE_0_YUM_REPO,
        ).create()
        repo.sync()
        prod = repo.product.read()
        subs = entities.Subscription().search(query={'search': 'name={0}'.format(prod.name)})
        assert len(subs) > 0, 'No subscriptions matching the product returned'
        ak = entities.ActivationKey(
            organization=self.org,
            content_view=self.org.default_content_view,
            environment=self.org.library,
        ).create()
        ak.add_subscriptions(data={'subscriptions': [{'id': subs[0].id}]})
        self.client.register_contenthost(org=self.org.label, activation_key=ak.name)

        # install package
        invocation_command = make_job_invocation(
            {
                'job-template': 'Package Action - Ansible Default',
                'inputs': 'state=latest, name={}'.format(*packages),
                'search-query': "name ~ {0}".format(self.client.hostname),
            }
        )
        try:
            assert invocation_command['success'] == '1'
        except AssertionError:
            result = 'host output: {0}'.format(
                ' '.join(
                    JobInvocation.get_output(
                        {'id': invocation_command['id'], 'host': self.client.hostname}
                    )
                )
            )
            raise AssertionError(result)
        result = ssh.command("rpm -q {0}".format(*packages), hostname=self.client.ip_addr)
        assert result.return_code == 0

        # start a service
        service = "postfix"
        ssh.command(
            "sed -i 's/^inet_protocols.*/inet_protocols = ipv4/' /etc/postfix/main.cf",
            hostname=self.client.ip_addr,
        )
        invocation_command = make_job_invocation(
            {
                'job-template': 'Service Action - Ansible Default',
                'inputs': 'state=started, name={}'.format(service),
                'search-query': "name ~ {0}".format(self.client.hostname),
            }
        )
        try:
            assert invocation_command['success'] == '1'
        except AssertionError:
            result = 'host output: {0}'.format(
                ' '.join(
                    JobInvocation.get_output(
                        {'id': invocation_command['id'], 'host': self.client.hostname}
                    )
                )
            )
            raise AssertionError(result)
        result = ssh.command("systemctl status {0}".format(service), hostname=self.client.ip_addr)
        assert result.return_code == 0

    @pytest.mark.stubbed
    @tier3
    @upgrade
    def test_positive_run_power_job(self):
        """Tests Ansible REX job can switch host power state successfully

        :id: f42c2834-8433-4965-a753-70651708c15b

        :Steps:

            0. Create a VM and register to SAT and prepare for REX (ssh key)

            1. Run Ansible Power job for the host to reboot it

            2. Check the host was rebooted (by uptime)

        :expectedresults: multiple asserts along the code

        :CaseAutomation: notautomated

        :CaseLevel: System
        """

    @pytest.mark.stubbed
    @tier3
    @upgrade
    def test_positive_run_puppet_job(self):
        """Tests Ansible REX job can trigger puppet run successfully

        :id: 7404991d-8832-422e-af66-9b21c7337a63

        :Steps:

            0. Create a VM and register to SAT and prepare for REX (ssh key)

            1. Setup puppet-agent on a host

            2. Run Ansible Puppet job for the host to trigger a new puppet run

            3. Check the new puppet run occurred (logs)

        :expectedresults: multiple asserts along the code

        :CaseAutomation: notautomated

        :CaseLevel: System
        """

    @pytest.mark.stubbed
    @tier3
    @upgrade
    def test_positive_run_roles_galaxy_install_job(self):
        """Tests Ansible REX job installs roles from Galaxy successfully

        :id: 20b09005-01e2-4c39-a9e9-3f418b28aa65

        :Steps:

            0. Prepare REX to be run against Internal Capsule (ssh key)

            1. Run Ansible Galaxy job for the proxy to install and import roles

            2. Check the roles are imported at the proxy

        :expectedresults: multiple asserts along the code

        :CaseAutomation: notautomated

        :CaseLevel: System
        """

    @pytest.mark.stubbed
    @tier3
    @upgrade
    def test_positive_run_roles_git_install_job(self):
        """Tests Ansible REX job installs roles from git successfully

        :id: 5c767edd-394b-4549-bfc6-242d5d124f5b

        :Steps:

            0. Prepare REX to be run against Internal Capsule (ssh key)

            1. Run Ansible Git job for the proxy to install and import roles

            2. Check the roles are imported at the proxy

        :expectedresults: multiple asserts along the code

        :CaseAutomation: notautomated

        :CaseLevel: System
        """


class AnsibleREXProvisionedTestCase(CLITestCase):
    """Test class for remote execution via Ansible"""

    @classmethod
    @skip_if_not_set('clients')
    def setUpClass(cls):
        super(AnsibleREXProvisionedTestCase, cls).setUpClass()
        cls.sat6_hostname = settings.server.hostname
        # provision host here and tests will share the host, step 0. in tests

    @pytest.mark.stubbed
    @tier3
    @upgrade
    def test_positive_run_job_for_provisioned_host(self):
        """Tests Ansible REX job runs successfully for a provisioned host

        :id: 36de179b-d41f-4278-92d3-b748c3bfcbbc

        :Steps:

            0. Provision a host

            1. Run job for the host

            2. Check the run at the host

        :expectedresults: multiple asserts along the code

        :CaseAutomation: notautomated

        :CaseLevel: System
        """

    @pytest.mark.stubbed
    @tier3
    @upgrade
    def test_positive_run_job_for_multiple_provisioned_hosts(self):
        """Tests Ansible REX job runs successfully for multiple provisioned hosts

        :id: 08ce6b2c-5385-48a4-8987-2815b3bd83b8

        :Steps:

            0. Provision two hosts

            1. Run job for both hosts

            2. Check the run at the hosts

        :expectedresults: multiple asserts along the code

        :CaseAutomation: notautomated

        :CaseLevel: System
        """
