"""
DRF Serializers for Payout API endpoints.
"""
from rest_framework import serializers
from .models import Merchant, Payout, LedgerEntry, IdempotencyKey


class MerchantSerializer(serializers.ModelSerializer):
    balance_paise = serializers.SerializerMethodField()
    held_balance_paise = serializers.SerializerMethodField()
    available_balance_paise = serializers.SerializerMethodField()

    class Meta:
        model = Merchant
        fields = ['id', 'name', 'email', 'balance_paise', 'held_balance_paise', 'available_balance_paise', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_balance_paise(self, obj):
        return obj.get_balance_paise()

    def get_held_balance_paise(self, obj):
        return obj.held_balance_paise

    def get_available_balance_paise(self, obj):
        return obj.available_balance_paise


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ['id', 'amount_paise', 'entry_type', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


class PayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = [
            'id', 'merchant', 'amount_paise', 'bank_account_id',
            'status', 'attempt_count', 'error_message',
            'created_at', 'completed_at'
        ]
        read_only_fields = ['id', 'status', 'attempt_count', 'error_message', 'created_at', 'completed_at']

    def validate_amount_paise(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value


class PayoutCreateSerializer(serializers.Serializer):
    """Serializer for creating payouts with idempotency key."""
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.CharField(max_length=255)

    def validate_amount_paise(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value


class PayoutDetailSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source='merchant.name', read_only=True)

    class Meta:
        model = Payout
        fields = [
            'id', 'merchant', 'merchant_name', 'amount_paise',
            'bank_account_id', 'status', 'attempt_count',
            'last_attempt_at', 'error_message',
            'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = ('id', 'merchant', 'merchant_name', 'amount_paise', 'bank_account_id', 'status', 'attempt_count', 'last_attempt_at', 'error_message', 'created_at', 'updated_at', 'completed_at')
