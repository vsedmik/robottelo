"""Tests for RH Cloud - Inventory

:Requirement: RHCloud

:CaseAutomation: Automated

:CaseComponent: RHCloud

:Team: Phoenix-subscriptions

:CaseImportance: High

"""

from datetime import datetime

import pytest
from wait_for import wait_for

from robottelo.config import settings
from robottelo.constants import DEFAULT_LOC, DEFAULT_ORG, DNF_RECOMMENDATION, OPENSSH_RECOMMENDATION


def create_insights_vulnerability(insights_vm):
    """Function to create vulnerabilities that can be remediated."""

    # Add vulnerabilities for OPENSSH_RECOMMENDATION and DNS_RECOMMENDATION, then upload Insights data.
    insights_vm.run(
        'chmod 777 /etc/ssh/sshd_config;'
        'dnf update -y dnf;sed -i -e "/^best/d" /etc/dnf/dnf.conf;'
        'insights-client'
    )


def sync_recommendations(satellite, org_name=DEFAULT_ORG, loc_name=DEFAULT_LOC):
    with satellite.ui_session() as session:
        session.organization.select(org_name=org_name)
        session.location.select(loc_name=DEFAULT_LOC)

        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M')
        session.cloudinsights.sync_hits()

    wait_for(
        lambda: satellite.api.ForemanTask()
        .search(query={'search': f'Insights full sync and started_at >= "{timestamp}"'})[0]
        .result
        == 'success',
        timeout=400,
        delay=15,
        silent_failure=True,
        handle_exception=True,
    )


@pytest.mark.e2e
@pytest.mark.pit_server
@pytest.mark.pit_client
@pytest.mark.no_containers
@pytest.mark.rhel_ver_list(r'^[\d]+$')
@pytest.mark.parametrize(
    "module_target_sat_insights", [True, False], ids=["hosted", "local"], indirect=True
)
def test_rhcloud_insights_e2e(
    rhel_insights_vm,
    rhcloud_manifest_org,
    module_target_sat_insights,
):
    """Synchronize hits data from hosted or local Insights Advisor, verify results are displayed in Satellite, and run remediation.

    :id: d952e83c-3faf-4299-a048-2eb6ccb8c9c2

    :steps:
        1. Prepare misconfigured machine and upload its data to Insights.
        2. In Satellite UI, go to Insights > Recommendations.
        3. Run remediation for "OpenSSH config permissions" recommendation against host.
        4. Verify that the remediation job completed successfully.
        5. Refresh Insights recommendations (re-sync if using hosted Insights).
        6. Search for previously remediated issue.

    :expectedresults:
        1. Insights recommendation related to "OpenSSH config permissions" issue is listed
            for misconfigured machine.
        2. Remediation job finished successfully.
        3. Insights recommendation related to "OpenSSH config permissions" issue is not listed.

    :CaseImportance: Critical

    :BZ: 1965901, 1962048, 1976754

    :customerscenario: true

    :parametrized: yes

    :CaseAutomation: Automated
    """
    job_query = (
        f'Remote action: Insights remediations for selected issues on {rhel_insights_vm.hostname}'
    )
    org_name = rhcloud_manifest_org.name

    # Prepare misconfigured machine and upload data to Insights
    create_insights_vulnerability(rhel_insights_vm)

    # Sync the recommendations (hosted Insights only).
    local_advisor_enabled = module_target_sat_insights.local_advisor_enabled
    if not local_advisor_enabled:
        sync_recommendations(module_target_sat_insights, org_name=org_name, loc_name=DEFAULT_LOC)

    with module_target_sat_insights.ui_session() as session:
        session.organization.select(org_name=org_name)
        session.location.select(loc_name=DEFAULT_LOC)

        # Search for the recommendation.
        result = session.cloudinsights.search(
            f'hostname= "{rhel_insights_vm.hostname}" and title = "{OPENSSH_RECOMMENDATION}"'
        )[0]
        assert result['Hostname'] == rhel_insights_vm.hostname
        assert result['Recommendation'] == OPENSSH_RECOMMENDATION

        # Run the remediation.
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M')
        session.cloudinsights.remediate(OPENSSH_RECOMMENDATION)

    # Wait for the remediation task to complete.
    wait_for(
        lambda: module_target_sat_insights.api.ForemanTask()
        .search(query={'search': f'{job_query} and started_at >= "{timestamp}"'})[0]
        .result
        == 'success',
        timeout=400,
        delay=15,
        silent_failure=True,
        handle_exception=True,
    )

    # Re-sync the recommendations (hosted Insights only).
    if not local_advisor_enabled:
        sync_recommendations(module_target_sat_insights, org_name=org_name, loc_name=DEFAULT_LOC)

    with module_target_sat_insights.ui_session() as session:
        session.organization.select(org_name=org_name)
        session.location.select(loc_name=DEFAULT_LOC)

        # Verify that the recommendation is not listed anymore.
        assert not session.cloudinsights.search(
            f'hostname= "{rhel_insights_vm.hostname}" and title = "{OPENSSH_RECOMMENDATION}"'
        )


@pytest.mark.stubbed
def test_insights_reporting_status():
    """Verify that the Insights reporting status functionality works as expected.

    :id: 75629a08-b585-472b-a295-ce497075e519

    :steps:
        1. Register a satellite content host with insights.
        2. Change 48 hours of wait time to 4 minutes in insights_client_report_status.rb file.
            See foreman_rh_cloud PR#596.
        3. Unregister host from insights.
        4. Wait 4 minutes.
        5. Use ForemanTasks.sync_task(InsightsCloud::Async::InsightsClientStatusAging)
            execute task manually.

    :expectedresults:
        1. Insights status for host changed to "Not reporting".

    :CaseImportance: Medium

    :BZ: 1976853

    :CaseAutomation: ManualOnly
    """


@pytest.mark.stubbed
def test_recommendation_sync_for_satellite():
    """Verify that Insights recommendations are listed for satellite.

    :id: ee3feba3-c255-42f1-8293-b04d540dcca5

    :steps:
        1. Register Satellite with insights.(satellite-installer --register-with-insights)
        2. Add RH cloud token in settings.
        3. Go to Insights > Recommendations > Click on Sync recommendations button.
        4. Click on notification icon.
        5. Select recommendation and try remediating it.

    :expectedresults:
        1. Notification about insights recommendations for Satellite is shown.
        2. Insights recommendations are listed for satellite.
        3. Successfully remediated the insights recommendation for Satellite itself.

    :CaseImportance: High

    :BZ: 1978182

    :CaseAutomation: ManualOnly
    """


@pytest.mark.stubbed
def test_host_sorting_based_on_recommendation_count():
    """Verify that hosts can be sorted and filtered based on insights
        recommendation count.

    :id: b1725ec1-60db-422e-809d-f81d99ae156e

    :steps:
        1. Register few satellite content host with insights.
        2. Sync Insights recommendations.
        3. Go to Hosts > All Hosts.
        4. Click on "Recommendations" column.
        5. Use insights_recommendations_count keyword to filter hosts.

    :expectedresults:
        1. Hosts are sorted based on recommendations count.
        2. Hosts are filtered based on insights_recommendations_count.

    :CaseImportance: Low

    :BZ: 1889662

    :CaseAutomation: ManualOnly
    """


@pytest.mark.no_containers
@pytest.mark.rhel_ver_list([7, 8, 9])
@pytest.mark.parametrize(
    "module_target_sat_insights", [True, False], ids=["hosted", "local"], indirect=True
)
def test_host_details_page(
    rhel_insights_vm,
    rhcloud_manifest_org,
    module_target_sat_insights,
):
    """Test host details page for host having insights recommendations.

    :id: e079ed10-c9f5-4331-9cb3-70b224b1a584

    :customerscenario: true

    :steps:
        1. Prepare misconfigured machine and upload its data to Insights.
        2. Sync Insights recommendations (hosted Insights only).
        3. Sync Insights inventory status (hosted Insights only).
        4. Go to Hosts -> All Hosts
        5. Verify there is a "Recommendations" column containing Insights recommendation count.
        6. Check popover status of host.
        7. Verify that host properties shows "reporting" inventory upload status.
        8. Read the recommendations listed in Insights tab present on host details page.
        9. Click on "Recommendations" tab.
        10. Try to delete host.

    :expectedresults:
        1. There's Insights column with number of recommendations.
        2. Inventory upload status is displayed in popover status of host.
        3. Insights registration status is displayed in popover status of host.
        4. Inventory upload status is present in host properties table.
        5. Verify the contents of Insights tab.
        6. Clicking on "Recommendations" tab takes user to Insights page with
            recommendations selected for that host.
        7. Host having Insights recommendations is deleted from Satellite.

    :BZ: 1974578, 1860422, 1928652, 1865876, 1879448

    :parametrized: yes

    :CaseAutomation: Automated
    """
    org_name = rhcloud_manifest_org.name

    # Prepare misconfigured machine and upload data to Insights.
    create_insights_vulnerability(rhel_insights_vm)

    local_advisor_enabled = module_target_sat_insights.local_advisor_enabled
    if not local_advisor_enabled:
        # Sync insights recommendations.
        sync_recommendations(module_target_sat_insights, org_name=org_name, loc_name=DEFAULT_LOC)

    with module_target_sat_insights.ui_session() as session:
        session.organization.select(org_name=org_name)
        session.location.select(loc_name=DEFAULT_LOC)

        # Verify Insights status of host.
        result = session.host_new.get_host_statuses(rhel_insights_vm.hostname)
        assert result['Insights']['Status'] == 'Reporting'
        assert (
            result['Inventory']['Status'] == 'Successfully uploaded to your RH cloud inventory'
            if not local_advisor_enabled
            else 'N/A'
        )

        # Verify recommendations exist for host.
        result = session.host_new.search(rhel_insights_vm.hostname)[0]
        assert result['Name'] == rhel_insights_vm.hostname
        assert int(result['Recommendations']) > 0

        # Read the recommendations in Insights tab on host details page.
        insights_recommendations = session.host_new.get_insights(rhel_insights_vm.hostname)[
            'recommendations_table'
        ]

        # Verify
        for recommendation in insights_recommendations:
            if recommendation['Recommendation'] == DNF_RECOMMENDATION:
                assert recommendation['Total risk'] == 'Moderate'
                assert DNF_RECOMMENDATION in recommendation['Recommendation']
                assert len(insights_recommendations) == int(result['Recommendations'])

        # Test Recommendation button present on host details page
        recommendations = session.host_new.get_insights(rhel_insights_vm.hostname)[
            'recommendations_table'
        ]
        assert len(recommendations), 'No recommendations were found'
        assert int(result['Recommendations']) == len(recommendations)

    # Delete host
    rhel_insights_vm.nailgun_host.delete()
    assert not rhel_insights_vm.nailgun_host


@pytest.mark.e2e
@pytest.mark.pit_client
@pytest.mark.no_containers
@pytest.mark.rhel_ver_list(r'^[\d]+$')
def test_insights_registration_with_capsule(
    rhcloud_capsule,
    rhcloud_activation_key,
    rhcloud_manifest_org,
    module_target_sat_insights,
    rhel_contenthost,
    default_os,
):
    """Registering host with insights having traffic going through
        external capsule and also test rh_cloud_insights:clean_statuses rake command.

    :id: 9db1d307-664c-4d4a-89de-da986224f071

    :customerscenario: true

    :steps:
        1. Integrate a capsule with satellite.
        2. open the global registration form and select the same capsule.
        3. Override Insights and Rex parameters.
        4. check host is registered successfully with selected capsule.
        5. Test insights client connection & reporting status.
        6. Run rh_cloud_insights:clean_statuses rake command
        7. Verify that host properties doesn't contain insights status.

    :expectedresults:
        1. Host is successfully registered with capsule host,
            having remote execution and insights.
        2. rake command deletes insights reporting status of host.

    :BZ: 2110222, 2112386, 1962930

    :parametrized: yes
    """
    org = rhcloud_manifest_org
    ak = rhcloud_activation_key
    # Enable rhel repos and install insights-client
    rhelver = rhel_contenthost.os_version.major
    if rhelver > 7:
        rhel_contenthost.create_custom_repos(**settings.repos[f'rhel{rhelver}_os'])
    else:
        rhel_contenthost.create_custom_repos(
            **{f'rhel{rhelver}_os': settings.repos[f'rhel{rhelver}_os']}
        )
    with module_target_sat_insights.ui_session() as session:
        session.organization.select(org_name=org.name)
        session.location.select(loc_name=DEFAULT_LOC)
        # Generate host registration command
        cmd = session.host_new.get_register_command(
            {
                'general.operating_system': default_os.title,
                'general.organization': org.name,
                'general.capsule': rhcloud_capsule.hostname,
                'general.activation_keys': ak.name,
                'general.insecure': True,
                'advanced.setup_insights': 'Yes (override)',
                'advanced.setup_rex': 'Yes (override)',
            }
        )
        # Register host with Satellite and Insights.
        rhel_contenthost.execute(cmd)
        assert rhel_contenthost.subscribed
        assert rhel_contenthost.execute('insights-client --test-connection').status == 0
        values = session.host_new.get_host_statuses(rhel_contenthost.hostname)
        assert values['Insights']['Status'] == 'Reporting'
        # Clean insights status
        result = module_target_sat_insights.run(
            f'foreman-rake rh_cloud_insights:clean_statuses SEARCH="{rhel_contenthost.hostname}"'
        )
        assert 'Deleted 1 insights statuses' in result.stdout
        assert result.status == 0
        # Workaround for not reading old data.
        session.browser.refresh()
        # Verify that Insights status is cleared.
        values = session.host_new.get_host_statuses(rhel_contenthost.hostname)
        assert values['Insights']['Status'] == 'N/A'
        result = rhel_contenthost.run('insights-client')
        assert result.status == 0
        # Workaround for not reading old data.
        session.browser.refresh()
        # Verify that Insights status again.
        values = session.host_new.get_host_statuses(rhel_contenthost.hostname)
        assert values['Insights']['Status'] == 'Reporting'
