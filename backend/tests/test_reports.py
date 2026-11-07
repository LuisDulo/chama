import io
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from finance.contributions import record_contribution
from reports import statements
from tests.conftest import client_for, make_user
from tests.factories import add_member, chama_for


@pytest.fixture
def setup(user):
    chama = chama_for(user)
    member = add_member(chama, make_user("Wanjiru"))
    record_contribution(member, Decimal("1000"), "cash", "CASH-1", user)
    record_contribution(member, Decimal("2500"), "mpesa", "SGH999", user)
    return chama, member


def workbook(response):
    return load_workbook(io.BytesIO(response.content))


def test_member_statement_runs_a_balance_from_the_ledger(setup):
    _, member = setup
    report = statements.member_statement(member)
    savings = report.tables[0]
    assert [row[2] for row in savings.rows] == ["CASH-1", "SGH999"]
    assert [row[5] for row in savings.rows] == [Decimal("1000"), Decimal("3500")]


def test_a_member_downloads_their_statement_as_pdf_and_excel(setup):
    chama, member = setup
    api = client_for(member.user)
    pdf = api.get(f"/api/chamas/{chama.id}/reports/my-statement/")
    assert pdf.status_code == 200
    assert pdf["Content-Type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")

    xlsx = api.get(f"/api/chamas/{chama.id}/reports/my-statement/?format=xlsx")
    sheet = workbook(xlsx)["Savings"]
    assert sheet.cell(5, 3).value == "CASH-1"
    assert sheet.cell(6, 6).value == 3500


def test_group_statement_balances(setup, user):
    chama, _ = setup
    xlsx = client_for(user).get(f"/api/chamas/{chama.id}/reports/financial-statements/"
                                "?format=xlsx")
    sheet = workbook(xlsx)["Accounts"]
    rows = [[c.value for c in row] for row in sheet.iter_rows(min_row=5)]
    assert sum(r[2] for r in rows) == sum(r[3] for r in rows) == 3500


def test_only_finance_officers_get_group_or_other_members_statements(setup):
    chama, member = setup
    api = client_for(member.user)
    assert api.get(f"/api/chamas/{chama.id}/reports/financial-statements/").status_code == 403
    other = add_member(chama)
    assert api.get(f"/api/chamas/{chama.id}/reports/members/{other.id}/statement/"
                   ).status_code == 403


def test_an_outsider_gets_nothing(setup):
    chama, _ = setup
    outsider = client_for(make_user("Outsider"))
    assert outsider.get(f"/api/chamas/{chama.id}/reports/my-statement/").status_code == 404


def test_an_unknown_format_is_refused(setup):
    chama, member = setup
    response = client_for(member.user).get(f"/api/chamas/{chama.id}/reports/my-statement/"
                                           "?format=docx")
    assert response.status_code == 400


def test_names_cannot_become_spreadsheet_formulas(user):
    chama = chama_for(user)
    attacker = add_member(chama, make_user('=HYPERLINK("http://evil.test","x")'))
    record_contribution(attacker, Decimal("1000"), "cash", "=1+1", user)
    xlsx = client_for(user).get(f"/api/chamas/{chama.id}/reports/financial-statements/"
                                "?format=xlsx")
    cell = workbook(xlsx)["Members"].cell(5, 1)
    assert cell.data_type == "s"
    assert cell.value.startswith("=HYPERLINK")
