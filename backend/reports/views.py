from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from audit.log import record
from chamas import permissions
from chamas.access import membership_for
from chamas.models import ChamaMembership
from reports import statements

FORMATS = {
    "pdf": ("application/pdf", statements.to_pdf),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             statements.to_xlsx),
}


def download(request, report, name):
    file_format = request.query_params.get("format", "pdf")
    if file_format not in FORMATS:
        raise ValidationError({"format": "Choose pdf or xlsx"})
    content_type, render = FORMATS[file_format]
    response = HttpResponse(render(report), content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{slugify(name)}.{file_format}"'
    return response


class MyStatementView(APIView):
    def get(self, request, chama_id):
        membership = membership_for(request.user, chama_id)
        return download(request, statements.member_statement(membership),
                        f"{membership.chama.name} statement")


class MemberStatementView(APIView):
    def get(self, request, chama_id, membership_id):
        officer = membership_for(request.user, chama_id, permissions.VIEW_FINANCES)
        member = get_object_or_404(ChamaMembership, pk=membership_id, chama=officer.chama)
        record(request.user, "report.member_statement", member, chama=officer.chama)
        return download(request, statements.member_statement(member),
                        f"{member.user.full_name} statement")


class GroupStatementView(APIView):
    def get(self, request, chama_id):
        officer = membership_for(request.user, chama_id, permissions.VIEW_FINANCES)
        record(request.user, "report.financial_statement", officer.chama, chama=officer.chama)
        return download(request, statements.group_statement(officer.chama),
                        f"{officer.chama.name} financial statement")
