
"""Mal's Joiner-Mover-Leaver (JML) security automation.

Real integrations: Okta, Google Workspace, optional Slack webhook.
Mock integrations: 1Password membership and MDM enrollment.
Default mode is safe mock mode.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(message)s")
LOG = logging.getLogger("jml")


def timestamp():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Action:
    name: str
    status: str
    details: dict = field(default_factory=dict)


@dataclass
class Report:
    operation: str
    user: str
    started_at: str = field(default_factory=timestamp)
    actions: list = field(default_factory=list)

    def run(self, name, function):
        try:
            result = function()
            self.actions.append(
                Action(name, "success", result or {})
            )
        except Exception as exc:
            LOG.error("%s failed: %s", name, exc)
            self.actions.append(
                Action(name, "failed", {"error": str(exc)})
            )

    def failures(self):
        return [a for a in self.actions if a.status == "failed"]

    def as_dict(self):
        return {
            "operation": self.operation,
            "user": self.user,
            "timestamp": self.started_at,
            "actions": [asdict(a) for a in self.actions],
            "failure_count": len(self.failures()),
        }


class Okta:
    def __init__(self):
        self.base = os.environ["OKTA_DOMAIN"].rstrip("/")
        self.headers = {
            "Authorization": f"SSWS {os.environ['OKTA_API_TOKEN']}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def request(self, method, path, **kwargs):
        response = requests.request(
            method, self.base + path,
            headers=self.headers, timeout=20, **kwargs
        )
        if not response.ok:
            raise RuntimeError(
                f"Okta HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )
        return response.json() if response.content else {}

    def create_user(self, email, first, last):
        return self.request(
            "POST", "/api/v1/users",
            params={"activate": "true"},
            json={"profile": {
                "login": email, "email": email,
                "firstName": first, "lastName": last,
            }},
        )

    def assign_group(self, group_id, user_id):
        return self.request(
            "PUT", f"/api/v1/groups/{group_id}/users/{user_id}"
        )

    def deactivate(self, user_id):
        return self.request(
            "POST", f"/api/v1/users/{user_id}/lifecycle/deactivate"
        )


class GoogleWorkspace:
    def __init__(self):
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = (
            service_account.Credentials.from_service_account_file(
                os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"],
                scopes=[
                    "https://www.googleapis.com/auth/admin.directory.user",
                    "https://www.googleapis.com/auth/admin.directory.user.security",
                ],
            ).with_subject(os.environ["GOOGLE_ADMIN_EMAIL"])
        )
        self.api = build(
            "admin", "directory_v1",
            credentials=credentials, cache_discovery=False,
        )

    def create_user(self, email, first, last):
        return self.api.users().insert(body={
            "primaryEmail": email,
            "name": {"givenName": first, "familyName": last},
            "password": os.environ["INITIAL_USER_PASSWORD"],
            "changePasswordAtNextLogin": True,
        }).execute()

    def revoke_tokens(self, email):
        tokens = self.api.tokens().list(userKey=email).execute()
        items = tokens.get("items", [])
        for token in items:
            self.api.tokens().delete(
                userKey=email, clientId=token["clientId"]
            ).execute()
        return {"tokens_found": len(items), "tokens_revoked": len(items)}


class OnePasswordMock:
    def assign_group(self, email):
        return {
            "mode": "mock", "email": email,
            "group": os.getenv("ONEPASSWORD_GROUP", "engineering"),
        }

    def remove_shared_vaults(self, email):
        # Fixture only; does not change real 1Password access.
        vaults = ["Engineering", "Shared Operations"]
        return {
            "mode": "mock", "email": email,
            "vaults_processed": vaults,
            "memberships_removed": len(vaults),
        }


class MDMMock:
    def invite(self, email):
        payload = {
            "mode": "mock",
            "platform": os.getenv("MDM_PLATFORM", "jamf"),
            "event": "device_enrollment_invitation",
            "recipient": email,
            "sent_at": timestamp(),
            "delivery": "simulated",
        }
        LOG.info("MDM MOCK: %s", json.dumps(payload))
        return payload


def notify_slack(report):
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    payload = report.as_dict()
    if not webhook:
        LOG.info("SLACK MOCK: %s", json.dumps(payload))
        return {"mode": "mock", "delivered": True}

    response = requests.post(
        webhook,
        json={"text": "JML offboarding report\n" + json.dumps(payload)},
        timeout=15,
    )
    if not response.ok:
        raise RuntimeError(f"Slack HTTP {response.status_code}")
    return {"mode": "real", "http_status": response.status_code}


def onboard(email, first, last):
    report = Report("onboard", email)

    if os.getenv("OKTA_MODE", "mock") == "real":
        okta = Okta()
        created = {}

        def create_okta():
            user = okta.create_user(email, first, last)
            created["id"] = user["id"]
            return {"user_id": user["id"]}

        report.run("okta_create_user", create_okta)

        def group_okta():
            if "id" not in created:
                raise RuntimeError("Skipped: Okta user creation failed")
            return okta.assign_group(
                os.environ["OKTA_GROUP_ID"], created["id"]
            )

        report.run("okta_assign_engineering_group", group_okta)
    else:
        report.run("okta_mock", lambda: {
            "mode": "mock", "email": email,
            "group": os.getenv("OKTA_GROUP_NAME", "engineering"),
        })

    if os.getenv("GOOGLE_MODE", "mock") == "real":
        google = GoogleWorkspace()
        report.run(
            "google_create_user",
            lambda: google.create_user(email, first, last),
        )
    else:
        report.run("google_create_user_mock", lambda: {
            "mode": "mock", "email": email,
        })

    vaults = OnePasswordMock()
    report.run(
        "onepassword_assign_group",
        lambda: vaults.assign_group(email),
    )
    report.run(
        "mdm_enrollment_invitation",
        lambda: MDMMock().invite(email),
    )
    LOG.info(json.dumps(report.as_dict(), indent=2))
    return report


def offboard(email, okta_user_id=None):
    report = Report("offboard", email)

    if os.getenv("OKTA_MODE", "mock") == "real":
        def deactivate():
            if not okta_user_id:
                raise ValueError(
                    "Supply an existing --okta-user-id in real mode"
                )
            return Okta().deactivate(okta_user_id)

        report.run("okta_deactivate", deactivate)
    else:
        report.run("okta_deactivate_mock", lambda: {
            "mode": "mock", "email": email,
        })

    if os.getenv("GOOGLE_MODE", "mock") == "real":
        google = GoogleWorkspace()
        report.run(
            "google_revoke_oauth_tokens",
            lambda: google.revoke_tokens(email),
        )
    else:
        report.run("google_revoke_oauth_tokens_mock", lambda: {
            "mode": "mock", "email": email, "tokens_revoked": 3,
        })

    report.run(
        "onepassword_remove_shared_vault_access",
        lambda: OnePasswordMock().remove_shared_vaults(email),
    )

    # Attempt the alert even if an earlier step failed.
    report.run("slack_completion_alert", lambda: notify_slack(report))
    LOG.info(json.dumps(report.as_dict(), indent=2))
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Mal's JML automation")
    commands = parser.add_subparsers(dest="command", required=True)

    new = commands.add_parser("onboard")
    new.add_argument("--email", required=True)
    new.add_argument("--first", required=True)
    new.add_argument("--last", required=True)

    leaving = commands.add_parser("offboard")
    leaving.add_argument("--email", required=True)
    leaving.add_argument("--okta-user-id")

    args = parser.parse_args()
    result = (
        onboard(args.email, args.first, args.last)
        if args.command == "onboard"
        else offboard(args.email, args.okta_user_id)
    )
    raise SystemExit(1 if result.failures() else 0)
