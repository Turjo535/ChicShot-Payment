from django.urls import path
from . import views

urlpatterns = [
    # Payment pages
    path('payment/', views.payment_page, name='payment_page'),
    path('payment-success.html', views.payment_success_page, name='payment_success'),
    
    # API endpoint
    path('api/create-payment-intent/', 
        views.CreatePaymentIntentView.as_view(), 
        name='create_payment_intent'),
    
    # Webhook (optional - only if you want logging)
    path('api/stripe-webhook/', 
        views.StripeWebhookView.as_view(), 
        name='stripe_webhook'),
    path('manychat-payment-check/<str:fb_id>/',views.ManyChatPaymentCheck.as_view(),name='manychat_payment_check'),
]