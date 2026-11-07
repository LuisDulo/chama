"""Sample data for trying the app locally. The people and groups are made up."""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from chamas.models import ChamaMembership
from chamas.services import create_chama
from finance import schedules
from finance.contributions import record_contribution
from rules.models import RuleVersion

PASSWORD = "Chama-Demo-2026"

PEOPLE = [
    ("Tabitha", "Wambui", "tabitha@demo.chama", "254700000001"),
    ("Musa", "Otieno", "musa@demo.chama", "254700000002"),
    ("Asha", "Hassan", "asha@demo.chama", "254700000003"),
    ("Baraka", "Kiprono", "baraka@demo.chama", "254700000004"),
]

WEEKLY = {"amount_type": "flexible", "minimum_amount": "500", "maximum_amount": "10000",
          "frequency": "weekly", "due_weekday": "friday", "grace_period_days": 2,
          "late_penalty": "50"}


class Command(BaseCommand):
    help = "Create demo users, two chamas with different rules, and some contributions."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo data is only for local development (DJANGO_DEBUG=1)")
        if User.objects.filter(email="tabitha@demo.chama").exists():
            self.stdout.write("Demo data already exists.")
            return
        with transaction.atomic():
            self.seed()
        self.stdout.write(self.style.SUCCESS(
            f"Demo ready. Log in as tabitha@demo.chama or musa@demo.chama, password {PASSWORD}"))

    def seed(self):
        tabitha, musa, asha, baraka = [
            User.objects.create_user(email=email, phone_number=phone, password=PASSWORD,
                                     first_name=first, last_name=last, email_verified=True)
            for first, last, email, phone in PEOPLE
        ]
        started = timezone.now() - timedelta(days=120)

        umoja = create_chama(tabitha, {"name": "Umoja Savings Group",
                                       "description": "Monthly savings for Kibera traders.",
                                       "category": "savings", "location": "Nairobi"})
        tujenge = create_chama(musa, {"name": "Tujenge Investment Club",
                                      "description": "Weekly savings toward land.",
                                      "category": "investment", "location": "Kisumu",
                                      "visibility": "public", "membership_type": "open"},
                               rules={"contributions": WEEKLY})
        for chama in (umoja, tujenge):
            RuleVersion.objects.filter(rule__chama=chama).update(
                effective_from=started.date())
            chama.memberships.update(joined_at=started)

        self.join(umoja, musa, "Treasurer", started)
        self.join(umoja, asha, "Member", started)
        self.join(umoja, baraka, "Member", started + timedelta(days=60))
        self.join(tujenge, tabitha, "Member", started)
        self.join(tujenge, asha, "Secretary", started)

        for chama in (umoja, tujenge):
            schedules.generate(chama)
        self.pay(umoja, tabitha, ["4000"], musa)
        self.pay(umoja, musa, ["3000", "1000"], musa)
        self.pay(umoja, asha, ["2000"], musa)
        self.pay(tujenge, musa, ["6000", "2500"], musa)
        self.pay(tujenge, tabitha, ["4000"], musa)

    def join(self, chama, user, role_name, when):
        membership = ChamaMembership(chama=chama, user=user,
                                     role=chama.roles.get(role_name=role_name))
        membership.activate(chama.created_by)
        membership.save()
        ChamaMembership.objects.filter(pk=membership.pk).update(joined_at=when)

    def pay(self, chama, user, amounts, officer):
        membership = chama.memberships.get(user=user)
        for number, amount in enumerate(amounts, start=1):
            record_contribution(membership, Decimal(amount), "cash",
                                f"DEMO-{user.first_name.upper()}-{chama.name[:3].upper()}-{number}",
                                officer)
