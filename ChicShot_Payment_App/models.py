from django.db import models


class PaymentModel(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('card', 'Card'),
        ('google_pay', 'Google Pay'),
        ('apple_pay', 'Apple Pay'),
    ]
    
    fb_id = models.CharField(max_length=100)
    package = models.CharField(max_length=100)
    amount = models.FloatField()
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)
  
    stripe_payment_intent_id = models.CharField(max_length=255, unique=True, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    

    currency = models.CharField(max_length=3, default='usd')
    description = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    manychat_payment=models.BooleanField(default=False)
    class Meta:
        db_table = 'payments'
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"{self.fb_id} - {self.package} - ${self.amount} - {self.payment_status}"
