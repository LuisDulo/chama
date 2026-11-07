"""What each rule category may contain. A chama chooses the values; the shape is fixed."""

from decimal import Decimal

from rest_framework import serializers

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class ContributionRule(serializers.Serializer):
    """How much members pay, how often, and what happens when they pay late."""

    amount_type = serializers.ChoiceField(["fixed", "flexible"])
    minimum_amount = serializers.DecimalField(max_digits=12, decimal_places=2,
                                              min_value=Decimal("1"))
    maximum_amount = serializers.DecimalField(max_digits=12, decimal_places=2,
                                              min_value=Decimal("1"))
    frequency = serializers.ChoiceField(["weekly", "monthly"])
    due_day = serializers.IntegerField(min_value=1, max_value=28, required=False)
    due_weekday = serializers.ChoiceField(WEEKDAYS, required=False)
    grace_period_days = serializers.IntegerField(min_value=0, max_value=60)
    late_penalty = serializers.DecimalField(max_digits=12, decimal_places=2,
                                            min_value=Decimal("0"))

    def validate(self, attrs):
        if attrs["maximum_amount"] < attrs["minimum_amount"]:
            raise serializers.ValidationError("The maximum cannot be below the minimum")
        if attrs["amount_type"] == "fixed" and attrs["maximum_amount"] != attrs["minimum_amount"]:
            raise serializers.ValidationError("A fixed contribution has one amount")
        if attrs["frequency"] == "monthly" and "due_day" not in attrs:
            raise serializers.ValidationError("Monthly contributions need a due_day (1 to 28)")
        if attrs["frequency"] == "weekly" and "due_weekday" not in attrs:
            raise serializers.ValidationError("Weekly contributions need a due_weekday")
        return attrs


class MembershipRule(serializers.Serializer):
    registration_fee = serializers.DecimalField(max_digits=12, decimal_places=2,
                                                min_value=Decimal("0"))
    minimum_members = serializers.IntegerField(min_value=2, max_value=1000)
    exit_notice_days = serializers.IntegerField(min_value=0, max_value=365)


class WithdrawalRule(serializers.Serializer):
    allowed = serializers.BooleanField()
    minimum_months_of_membership = serializers.IntegerField(min_value=0, max_value=120)
    maximum_percent_of_savings = serializers.IntegerField(min_value=0, max_value=100)


CATEGORIES = {
    "contributions": ContributionRule,
    "membership": MembershipRule,
    "withdrawals": WithdrawalRule,
}

DEFAULTS = {
    "contributions": {"amount_type": "fixed", "minimum_amount": "1000.00",
                      "maximum_amount": "1000.00", "frequency": "monthly", "due_day": 5,
                      "grace_period_days": 3, "late_penalty": "100.00"},
    "membership": {"registration_fee": "0.00", "minimum_members": 2, "exit_notice_days": 30},
    "withdrawals": {"allowed": False, "minimum_months_of_membership": 12,
                    "maximum_percent_of_savings": 0},
}


def clean(category, configuration):
    """Validate and normalise a configuration, storing decimals as strings for JSON."""
    if category not in CATEGORIES:
        raise serializers.ValidationError({"category": f"Unknown rule category {category!r}"})
    schema = CATEGORIES[category](data=configuration)
    schema.is_valid(raise_exception=True)
    return {key: str(value) if isinstance(value, Decimal) else value
            for key, value in schema.validated_data.items()}
