"""
Django admin configuration for payout models.
"""
from django.contrib import admin
from .models import Merchant, Payout, LedgerEntry, IdempotencyKey


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'email', 'balance_display', 'created_at']
    search_fields = ['name', 'email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def balance_display(self, obj):
        return f"{obj.balance_paise} paise"
    balance_display.short_description = "Balance"


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ['id', 'merchant', 'amount_paise', 'entry_type', 'created_at']
    list_filter = ['entry_type', 'merchant', 'created_at']
    search_fields = ['merchant__name', 'merchant__email']
    readonly_fields = ['id', 'created_at']


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ['id', 'merchant', 'amount_paise', 'status', 'attempt_count', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['merchant__name', 'merchant__email']
    readonly_fields = ['id', 'created_at', 'updated_at', 'completed_at']
    
    fieldsets = (
        ('Payout Info', {
            'fields': ('id', 'merchant', 'amount_paise', 'bank_account_id')
        }),
        ('Status', {
            'fields': ('status', 'error_message', 'completed_at')
        }),
        ('Retry Info', {
            'fields': ('attempt_count', 'max_attempts', 'last_attempt_at')
        }),
        ('Idempotency', {
            'fields': ('idempotency_key',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ['id', 'merchant', 'key', 'payout', 'expires_at']
    list_filter = ['created_at', 'expires_at']
    search_fields = ['merchant__name', 'key', 'payout__id']
    readonly_fields = ['id', 'created_at']
