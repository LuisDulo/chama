from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from chamas import permissions
from chamas.access import membership_for
from rules import schemas, services
from rules.models import RuleVersion


class VersionSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="rule.category")
    proposed_by = serializers.CharField(source="proposed_by.full_name")
    decided_by = serializers.CharField(source="decided_by.full_name", default=None)

    class Meta:
        model = RuleVersion
        fields = ["id", "category", "version_number", "status", "configuration",
                  "previous_configuration", "effective_from", "reason", "proposed_by",
                  "decided_by", "decided_at", "created_at"]


class ProposalSerializer(serializers.Serializer):
    category = serializers.ChoiceField(list(schemas.CATEGORIES))
    configuration = serializers.DictField()
    effective_from = serializers.DateField()
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True)


class RulesView(APIView):
    """The rules in force today, and any change waiting for a decision."""

    def get(self, request, chama_id):
        chama = membership_for(request.user, chama_id).chama
        result = []
        for category in schemas.CATEGORIES:
            current = services.current_version(chama, category)
            pending = RuleVersion.objects.filter(rule__chama=chama, rule__category=category,
                                                 status=RuleVersion.Status.PROPOSED).first()
            upcoming = RuleVersion.objects.filter(
                rule__chama=chama, rule__category=category, status=RuleVersion.Status.APPROVED,
                effective_from__gt=current.effective_from if current else None,
            ).order_by("effective_from").first() if current else None
            result.append({
                "category": category,
                "current": VersionSerializer(current).data if current else None,
                "upcoming": VersionSerializer(upcoming).data if upcoming else None,
                "pending": VersionSerializer(pending).data if pending else None,
            })
        return Response(result)

    def post(self, request, chama_id):
        membership = membership_for(request.user, chama_id, permissions.PROPOSE_RULES)
        proposal = ProposalSerializer(data=request.data)
        proposal.is_valid(raise_exception=True)
        data = proposal.validated_data
        version = services.propose(request.user, membership.chama, data["category"],
                                   data["configuration"], data["effective_from"],
                                   data.get("reason", ""))
        return Response(VersionSerializer(version).data, status=status.HTTP_201_CREATED)


class RuleHistoryView(APIView):
    def get(self, request, chama_id):
        chama = membership_for(request.user, chama_id).chama
        versions = RuleVersion.objects.filter(rule__chama=chama).select_related(
            "rule", "proposed_by", "decided_by").order_by("rule__category", "-version_number")
        return Response(VersionSerializer(versions, many=True).data)


class RuleDecisionView(APIView):
    def post(self, request, chama_id, version_id, decision):
        membership = membership_for(request.user, chama_id, permissions.APPROVE_RULES)
        version = get_object_or_404(RuleVersion, pk=version_id, rule__chama=membership.chama)
        if decision not in ("approve", "reject"):
            return Response({"detail": "Use approve or reject"}, status=400)
        decided = services.decide(request.user, membership.chama, version, decision == "approve")
        return Response(VersionSerializer(decided).data)
