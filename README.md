
# Mal JML Security Automation

A Python-based Joiner-Mover-Leaver (JML) automation project demonstrating security workflows for employee onboarding and offboarding across identity, SaaS access, endpoint management, and security notifications.

## Project Overview

Employee onboarding and offboarding involve several systems. Missing one step can leave accounts active or grant a new employee access they do not need.

This project coordinates those actions through a single Python command-line application, records individual action results, and produces a structured workflow report.

## Features

### Onboarding
- Create an Okta user and assign the user to a configured group.
- Provision a Google Workspace account.
- Simulate assigning the new hire to a 1Password vault group.
- Simulate a Jamf device-enrollment invitation.
- Record successes and failures for individual actions.

### Offboarding
- Deactivate an existing Okta user.
- Revoke registered Google Workspace OAuth tokens.
- Simulate removing access to shared 1Password vaults.
- Send a completion summary to Slack or log a simulated alert.
- Preserve the results of individual actions, including failures.

## Technology Stack

- Python 3.11+
- Okta REST API
- Google Workspace Admin SDK
- Slack Incoming Webhooks
- pytest
- Ruff
- python-dotenv

## Integration Status

| Integration | Implementation |
|---|---|
| Okta user lifecycle | Real API integration available; mock mode is the default |
| Google Workspace provisioning and token revocation | Real API integration available; mock mode is the default |
| 1Password membership management | Mocked |
| Jamf enrollment invitation | Mocked |
| Slack notification | Real webhook when configured; otherwise mocked |

**Important:** Mock responses do not change access in real systems. The 1Password and MDM operations in this version are simulations.

## Repository Structure

```text
mal-jml-security-automation/
├── jml.py
├── tests/
│   └── test_jml.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Prerequisites

- Python 3.11 or newer
- GitHub account
- Optional sandbox tenant and credentials for real API integrations

## Local Installation

Clone the repository:

```bash
git clone https://github.com/RohitChangotra/mal-jml-security-automation.git
cd mal-jml-security-automation
```

Create and activate a virtual environment.

**Windows PowerShell:**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS or Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

Create a local environment file:

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

**macOS or Linux:**

```bash
cp .env.example .env
```

Keep `OKTA_MODE=mock` and `GOOGLE_MODE=mock` while testing locally.

## Run Onboarding

```bash
python jml.py onboard --email newhire@example.com --first Mal --last Example
```

The default mock configuration demonstrates the onboarding workflow without creating real accounts.

## Run Offboarding

```bash
python jml.py offboard --email departing@example.com
```

In real Okta mode, supply the existing user ID:

```bash
python jml.py offboard --email departing@example.com --okta-user-id EXISTING_OKTA_USER_ID
```

Replace the example values with appropriate test identities. Do not use real employee accounts while learning.

The process returns a nonzero exit code when one or more recorded actions fail.

## Run Tests

```bash
pytest -q
```

Run the linter:

```bash
ruff check jml.py tests/
```

These commands should be run in a local Python environment. Their results must be checked before claiming that the project passes.

## Configuring Real Integrations

### Okta

Set the following environment variables:

- `OKTA_MODE=real`
- `OKTA_DOMAIN`
- `OKTA_API_TOKEN`
- `OKTA_GROUP_ID`

Use a sandbox tenant and a least-privilege API token. Verify the necessary permissions before running lifecycle operations.

### Google Workspace

Set `GOOGLE_MODE=real` and configure:

- `GOOGLE_SERVICE_ACCOUNT_FILE`
- `GOOGLE_ADMIN_EMAIL`
- `INITIAL_USER_PASSWORD`

The service account must have appropriately authorized domain-wide delegation and the required Admin SDK scopes. Enable the Admin SDK in the associated Google Cloud project.

Test account creation and OAuth token revocation in a dedicated test tenant first.

### Slack

Set `SLACK_WEBHOOK_URL` to a valid incoming webhook URL to enable real notifications.

Treat the webhook URL as a secret. The webhook sends a workflow summary; it does not replace a durable audit log.

### 1Password and MDM

The current implementations are mocked. They do not remove real vault memberships, send actual enrollment invitations, or enroll devices. Replace them with supported, authorized integrations before production use.

## Security Considerations

- Never commit `.env`, API tokens, passwords, service-account keys, or private employee information.
- Keep real API modes disabled during initial testing.
- Use least-privilege credentials and isolated test tenants.
- Require explicit authorization before destructive offboarding actions.
- Verify user identity before disabling accounts.
- Review each action result; partial success does not mean all access has been revoked.
- Add durable audit storage, retries, and idempotency before production deployment.

## Limitations

This repository is a demonstration and learning project, not a production-certified deprovisioning system.

Real API behavior depends on tenant configuration, account permissions, and service-specific requirements. Mocked actions must not be interpreted as proof that real access has been removed.

## Author

Rohit Changotra

GitHub: https://github.com/RohitChangotra
