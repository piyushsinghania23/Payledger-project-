"""
Django management command to seed merchants with transaction history.
Usage: python manage.py seed_merchants
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from payto.payout.models import Merchant, LedgerEntry
import uuid


class Command(BaseCommand):
    help = 'Seed merchants with initial balance and transaction history'

    @transaction.atomic
    def handle(self, *args, **options):
        # Create merchants
        merchants_data = [
            {
                'name': 'Acme Digital Services',
                'email': 'accounting@acme-digital.in',
                'credits': [
                    (500000, 'Payment from TechCorp USA'),  # ₹5,000
                    (300000, 'Payment from StartupX'),       # ₹3,000
                    (150000, 'Payment from GlobalTech'),     # ₹1,500
                ]
            },
            {
                'name': 'Stellar Freelance Studio',
                'email': 'team@stellar-studio.in',
                'credits': [
                    (1000000, 'Design project from CloudCorp'),    # ₹10,000
                    (750000, 'Development contract from FinanceYes'), # ₹7,500
                    (500000, 'Consulting work'),                     # ₹5,000
                    (250000, 'Support retainer'),                    # ₹2,500
                ]
            },
            {
                'name': 'NextGen Analytics',
                'email': 'payments@nextgen-analytics.in',
                'credits': [
                    (2000000, 'Data engineering contract'),    # ₹20,000
                    (1500000, 'Analytics consultation'),        # ₹15,000
                    (800000, 'Dashboard development'),          # ₹8,000
                ]
            },
        ]

        created_count = 0
        for merchant_data in merchants_data:
            # Create merchant
            try:
                merchant = Merchant.objects.get(email=merchant_data['email'])
                self.stdout.write(
                    self.style.WARNING(f"Merchant {merchant.name} already exists, skipping")
                )
                continue
            except Merchant.DoesNotExist:
                merchant = Merchant.objects.create(
                    name=merchant_data['name'],
                    email=merchant_data['email'],
                    country_code='IN'
                )
                created_count += 1

            # Add credit entries (simulated customer payments)
            for amount_paise, description in merchant_data['credits']:
                LedgerEntry.objects.create(
                    merchant=merchant,
                    amount_paise=amount_paise,
                    entry_type='credit',
                    description=description,
                    external_id=f"payment_{uuid.uuid4().hex[:8]}"
                )

            balance_paise = merchant.balance_paise
            balance_rupees = balance_paise / 100
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ {merchant.name}: ₹{balance_rupees:.2f} ({balance_paise} paise)"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(f"\nSuccessfully seeded {created_count} merchants")
        )
