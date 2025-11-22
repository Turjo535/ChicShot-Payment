from django.contrib import admin

# Register your models here.
from .models import PaymentModel
@admin.register(PaymentModel)
class PaymentModelAdmin(admin.ModelAdmin):
    list_display = ('fb_id', 'package', 'amount', 'payment_date', 'payment_method', 'payment_status')
    search_fields = ('fb_id', 'package', 'stripe_payment_intent_id', 'stripe_customer_id')
    list_filter = ('payment_status', 'payment_method', 'currency', 'manychat_payment')
    ordering = ('-payment_date',)