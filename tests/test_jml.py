
import jml


def test_report_records_success_and_failure():
    report = jml.Report("test", "person@example.com")

    report.run("success", lambda: {"ok": True})
    report.run(
        "failure",
        lambda: (_ for _ in ()).throw(RuntimeError("test error")),
    )

    assert report.actions[0].status == "success"
    assert report.actions[1].status == "failed"
    assert len(report.failures()) == 1


def test_mock_onboarding(monkeypatch):
    monkeypatch.setenv("OKTA_MODE", "mock")
    monkeypatch.setenv("GOOGLE_MODE", "mock")
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    report = jml.onboard(
        "newhire@example.com", "Test", "Employee"
    )

    assert report.operation == "onboard"
    assert report.failures() == []
    names = [action.name for action in report.actions]
    assert "mdm_enrollment_invitation" in names
    assert "onepassword_assign_group" in names


def test_mock_offboarding(monkeypatch):
    monkeypatch.setenv("OKTA_MODE", "mock")
    monkeypatch.setenv("GOOGLE_MODE", "mock")
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    report = jml.offboard("leaver@example.com")

    assert report.operation == "offboard"
    assert report.failures() == []
    names = [action.name for action in report.actions]
    assert "okta_deactivate_mock" in names
    assert "google_revoke_oauth_tokens_mock" in names
    assert "onepassword_remove_shared_vault_access" in names
    assert "slack_completion_alert" in names


def test_onepassword_membership_mock():
    adapter = jml.OnePasswordMock()

    result = adapter.remove_shared_vaults("leaver@example.com")

    assert result["mode"] == "mock"
    assert result["memberships_removed"] == 2


def test_mdm_invitation_mock():
    result = jml.MDMMock().invite("newhire@example.com")

    assert result["mode"] == "mock"
    assert result["recipient"] == "newhire@example.com"
    assert result["delivery"] == "simulated"


def test_slack_notification_mock(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    report = jml.Report("offboard", "leaver@example.com")

    result = jml.notify_slack(report)

    assert result == {"mode": "mock", "delivered": True}
