# CHAMA

A platform for running chamas (savings groups, investment clubs and merry-go-rounds). One account can create and join many chamas, and each chama keeps its own members, roles, rules, ledger and statements. Members contribute by M-Pesa STK Push or in cash, and every shilling is posted to a double-entry ledger.

Built with Django REST Framework, PostgreSQL and React. This is the first release from the [requirements specification](#scope): the twelve acceptance criteria in its section 13.

![The overview of a chama, showing the member's savings and the group's books](docs/screenshots/05-overview-treasurer.png)

**Screenshots:** every page, from both a treasurer's and a chairperson's side, are in [docs/SCREENSHOTS.md](docs/SCREENSHOTS.md) (also as a [Word document](docs/CHAMA_Screenshots.docx)).

## Try it locally

You need Python 3.12, Node.js 20+ and PostgreSQL.

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate      # macOS or Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_DEBUG=1 DATABASE_URL=postgresql://postgres:postgres@localhost:5432/chama
python manage.py migrate
python manage.py seed_demo                            # optional sample data
python manage.py runserver
```

```bash
cd frontend
npm install
npm run dev                                           # http://localhost:5173
```

With the sample data, log in as `tabitha@demo.chama` or `musa@demo.chama` with password `Chama-Demo-2026`. Musa belongs to two chamas with different rules. With no Daraja key set, M-Pesa is simulated: the app shows the prompt a phone would, and the answer goes through the real callback code.

## Acceptance criteria

| Section 13 criterion | How it is met | Tests |
|---|---|---|
| 1. Register and authenticate | Email or phone login, JWT with refresh rotation, revocable logout, email verification, password reset | `test_accounts.py` |
| 2. Create more than one chama | Each chama gets its own roles, rules, accounts and ledger | `test_chamas.py` |
| 3. Join several chamas | Invitations bound to the invitee, and join requests for open chamas. A chama switcher in the app | `test_chamas.py` |
| 4. Independent rules | Rules are versioned per chama and category | `test_rules.py` |
| 5. Different minimums and frequencies | Set in the creation wizard, for example weekly KES 500 next to monthly KES 2,500 | `test_rules.py` |
| 6. Contribution schedules | Generated per member from the rule in force on each due date | `test_finance.py` |
| 7. Recorded and reconciled | Cash and M-Pesa contributions. Reconciliation asks Daraja about payments whose callback never arrived | `test_finance.py`, `test_payments.py` |
| 8. Financial statements | Member and group statements in PDF and Excel, built from the ledger | `test_reports.py` |
| 9. Membership and permissions | Chama roles with permissions, custom roles, approval, suspension and removal | `test_chamas.py` |
| 10. No access to another chama | One membership check behind every chama endpoint. Another chama looks like it does not exist | `test_chamas.py` |
| 11. Auditable | Append-only audit log of every important action, visible to officers | all suites |
| 12. Rule history preserved | Approved versions cannot be edited. Each change has an effective date, a proposer and an approver | `test_rules.py`, `test_finance.py` |

The backend has 129 tests, all run against a real PostgreSQL. I also went through the main journeys in the browser: registering, creating two chamas with different rules, inviting a member who already belonged to two other chamas, paying through the simulated M-Pesa prompt, approving a rule change, recording cash and downloading statements.

## How it works

```mermaid
flowchart LR
    W[React web app] --> A[Django REST API]
    A --> X{Membership check}
    X --> C[Chamas and roles]
    X --> R[Rules engine]
    X --> F[Ledger, schedules, contributions]
    X --> S[Statements]
    F --> P[Payments]
    P <--> M[M-Pesa Daraja]
    C & R & F & P & S --> D[(PostgreSQL)]
```

| Folder | Responsibility |
|---|---|
| `backend/accounts` | Users, login, verification and password reset |
| `backend/chamas` | Chamas, memberships, roles, invitations and the access check |
| `backend/rules` | Versioned rules with proposals, approval and effective dates |
| `backend/finance` | Ledger, schedules and contributions |
| `backend/payments` | M-Pesa STK Push, callbacks and reconciliation |
| `backend/reports` | PDF and Excel statements |
| `backend/audit` | The append-only audit log |
| `frontend` | The React web app |

## Design decisions

**Tenant isolation.** Every chama endpoint starts by fetching the caller's active membership of that chama. Without one, the answer is 404, so nobody can probe which chamas exist. Platform staff get no access to chama data by default.

**Rules never rewrite the past (BR-06, BR-11).** A rule change is a new version with an effective date, proposed by one officer and approved by another. Each schedule entry records the version that set its amount, so if a chama raises its contribution from March, January and February stay as they were.

**The books always balance.** Every contribution is a journal entry that must balance before anything is written. The database also refuses a line that is both a debit and a credit, and schedule rows that are overpaid. Journal entries, contributions and audit entries cannot be edited or deleted. Mistakes are corrected with a new entry.

**A payment request is not a payment (FR-08).** Starting an STK Push records a pending payment and credits nothing. Money is credited only when a callback or a status query confirms it. The callback:

- lives at a secret URL, because Daraja does not sign callbacks
- locks the payment row and only moves a pending payment
- checks the amount and receipt, and refuses a receipt that was already used
- stores every delivery with a hash of its body, so a repeat is recorded as a duplicate and changes nothing

If a callback never arrives, reconciliation asks Daraja for the result, and a payment with no answer after a day expires.

**Failures leave a trace.** Every request runs in one database transaction, so an exception would roll back the record of a failed M-Pesa attempt. The code returns the failure as a response instead, and the test suite caught this.

**Safe files.** Text in Excel statements is always stored as text, so a member called `=HYPERLINK(...)` cannot run a formula on the treasurer's computer.

**Low bandwidth.** The web app uses system fonts and no images, to suit slow connections (section 4.5).

## Scope

This release covers phases 1 to 3 of the specification, as far as section 13 needs them. Not built yet:

- **Loans, interest and repayment schedules** (FR-06, FR-07), which is phase 4
- **Voting, meetings and documents** (FR-09), which is phase 5. Rule approval is one officer approving another's proposal, not a vote
- **Celery and Redis.** Statements are generated during the request, which is fine at this size
- **The React Native app**, other contribution types, notifications by SMS or email, investments, the platform administrator dashboard and multi-factor authentication

## Limitations

- **Real M-Pesa has not been called.** No Daraja credentials were available, so the client is tested against a mock server that checks each request, and the app was used with simulated payments. Try it on the Daraja sandbox before relying on it.
- **A query result has no receipt.** When reconciliation confirms a payment by status query, Daraja gives no receipt number, so the checkout ID stands in for it.
- **Late penalties are shown, not charged.** Each schedule entry knows its penalty and when it becomes overdue, but no penalty is posted to the ledger yet.
- **Tokens are kept in session storage.** That is simpler than cookies but readable by any script on the page, so the app must never load untrusted scripts.
- **Platform suspension is not built.** There is no screen for platform administrators yet.
- **Not legal or financial advice.** Section 4.6 of the specification applies: holding members' money or lending needs legal and regulatory review before launch.
- **Windows note for contributors:** the embedded PostgreSQL used by the tests may lack time zone files on Windows. Set `TEST_DATABASE_URL` to a full PostgreSQL if the tests report an invalid `TimeZone`.
