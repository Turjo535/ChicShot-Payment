import stripe
from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from decouple import config
from .models import PaymentModel

# Stripe configuration
stripe.api_key = config('STRIPE_SECRET_KEY', default='')


def payment_page(request):
    
    return render(request, 'payment.html')


def payment_success_page(request):
   
    return render(request, 'payment-success.html')


@method_decorator(csrf_exempt, name='dispatch')
class CreatePaymentIntentView(APIView):
    
    
    def post(self, request):
        try:
            fb_id = request.data.get('fb_id', '')
            amount = request.data.get('amount')
            package = request.data.get('package', 'Payment')
            currency = request.data.get('currency', 'eur')
            description = request.data.get('description', '')
            
            print(fb_id)
            
            if not amount:
                return Response(
                    {'error': 'Amount is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            amount_in_cents = int(float(amount) * 100)
            
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_in_cents,
                currency=currency,
                payment_method_types=['card'],
                description=f"{package} - {description}",
                metadata={
                    'fb_id': fb_id,
                    'package': package,
                    'description': description
                }
            )
            
            payment = PaymentModel.objects.create(
                fb_id=fb_id,
                package=package,
                amount=float(amount),
                currency=currency,
                description=description,
                stripe_payment_intent_id=payment_intent.id,
                payment_status='pending'
            )
            print(payment)
            
            
            return Response({
                'success': True,
                'client_secret': payment_intent.client_secret,
                'payment_intent_id': payment_intent.id,
                'payment_id': payment.id,
                'publishable_key': config('STRIPE_PUBLIC_KEY', default='')
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class PaymentSuccessView(APIView):
    
    
    def post(self, request):
        try:
            payment_intent_id = request.data.get('payment_intent_id')
            
            
            
            if not payment_intent_id:
                return Response(
                    {'error': 'payment_intent_id is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            
            payment_intent = stripe.PaymentIntent.retrieve(
                payment_intent_id,
                expand=['charges']  
            )
            
            payment = PaymentModel.objects.filter(
                stripe_payment_intent_id=payment_intent_id
            ).first()
            
            if not payment:
                
                return Response(
                    {'error': 'Payment not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            
            try:
                if hasattr(payment_intent, 'charges') and payment_intent.charges and len(payment_intent.charges.data) > 0:
                    charge = payment_intent.charges.data[0]
                    payment_method_details = getattr(charge, 'payment_method_details', None)
                    
                    if payment_method_details and payment_method_details.type == 'card':
                        card_details = getattr(payment_method_details, 'card', None)
                        if card_details:
                            wallet = getattr(card_details, 'wallet', None)
                            if wallet:
                                wallet_type = getattr(wallet, 'type', None)
                                if wallet_type == 'google_pay':
                                    payment.payment_method = 'google_pay'
                                elif wallet_type == 'apple_pay':
                                    payment.payment_method = 'apple_pay'
                                else:
                                    payment.payment_method = 'card'
                            else:
                                payment.payment_method = 'card'
                        else:
                            payment.payment_method = 'card'
                    else:
                        payment.payment_method = 'card'
                else:
                    payment.payment_method = 'card'
            except Exception as e:
                
                payment.payment_method = 'card'  
            
            
            if payment_intent.status == 'succeeded':
                payment.payment_status = 'completed'
                
            elif payment_intent.status == 'processing':
                payment.payment_status = 'pending'
                
            else:
                payment.payment_status = 'failed'
                
            
            payment.save()
            
            
            
            return Response({
                'success': True,
                'payment_status': payment.payment_status,
                'payment_method': payment.payment_method,
                'message': 'Payment confirmed successfully'
            }, status=status.HTTP_200_OK)
            
        except stripe.error.StripeError as e:
            
            return Response(
                {'error': f'Stripe error: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            
            import traceback
            traceback.print_exc()  
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



class ManyChatPaymentCheck(APIView):
    
    
    def get(self, request, fb_id):
        try:
            payment = PaymentModel.objects.filter(
                fb_id=fb_id,
                manychat_payment=False
            ).latest('updated_at')
            
            print(f"📋 Checking payment for fb_id={fb_id}: {payment}")
            
            # ✅ FIXED: Check if manychat_payment is FALSE (not TRUE)
            if not payment.manychat_payment:
                payment.manychat_payment = True
                payment.save()
                
                print(f"✅ ManyChat payment marked for fb_id={fb_id}, package={payment.package}")
                
                return Response({
                    'success': payment.package,
                    'payment_status': payment.payment_status,
                    'amount': payment.amount,
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'success': False, 'message': 'Payment already checked'}, 
                    status=status.HTTP_200_OK
                )
                
        except PaymentModel.DoesNotExist:
            print(f"❌ No payments found for fb_id={fb_id}")
            return Response(
                {'success': False, 'message': 'No payments found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"❌ Error in ManyChat check: {str(e)}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class EncryptDataView(APIView):
    """Encrypt data using Stripe's encryption"""
    
    def post(self, request):
        try:
            data_to_encrypt = request.data.get('data', '')
            
            if not data_to_encrypt:
                return Response(
                    {'error': 'Data to encrypt is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            encrypted_data = stripe.util.encrypt_data(data_to_encrypt)
            
            return Response({
                'success': True,
                'encrypted_data': encrypted_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
















































@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    """Handle Stripe webhook events"""
    
    def post(self, request):
        print("=" * 80)
        print("🔔 WEBHOOK ENDPOINT HIT!")
        print("=" * 80)
        
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        webhook_secret = config('STRIPE_WEBHOOK_SECRET', default='')
        
        print(f"Webhook Secret Configured: {bool(webhook_secret)}")
        print(f"Signature Header Present: {bool(sig_header)}")
        
        if not webhook_secret:
            print("⚠️ No webhook secret configured!")
            return HttpResponse(status=200)
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            print(f"✅ Event Type: {event['type']}")
        except ValueError as e:
            print(f"❌ ValueError: {e}")
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError as e:
            print(f"❌ Signature Verification Failed: {e}")
            return HttpResponse(status=400)
        
        # Handle the event
        if event['type'] == 'payment_intent.succeeded':
            print("💰 Processing payment_intent.succeeded")
            payment_intent = event['data']['object']
            self.handle_payment_success(payment_intent)
            
        elif event['type'] == 'payment_intent.payment_failed':
            print("❌ Processing payment_intent.payment_failed")
            payment_intent = event['data']['object']
            self.handle_payment_failed(payment_intent)
        
        print("=" * 80)
        return HttpResponse(status=200)
    
    def handle_payment_success(self, payment_intent):
        """Update payment status to completed"""
        payment = PaymentModel.objects.filter(
            stripe_payment_intent_id=payment_intent['id']
        ).first()
        
        if payment:
            payment.payment_status = 'completed'
            
            if payment_intent.get('customer'):
                payment.stripe_customer_id = payment_intent['customer']
            
            if payment_intent.get('charges', {}).get('data'):
                charge = payment_intent['charges']['data'][0]
                payment_method_details = charge.get('payment_method_details', {})
                
                if payment_method_details.get('type') == 'card':
                    wallet = payment_method_details.get('card', {}).get('wallet', {})
                    wallet_type = wallet.get('type')
                    
                    if wallet_type == 'google_pay':
                        payment.payment_method = 'google_pay'
                    elif wallet_type == 'apple_pay':
                        payment.payment_method = 'apple_pay'
                    else:
                        payment.payment_method = 'card'
            
            payment.save()
            print(f"✅ Payment {payment.id} marked as completed via webhook")
        else:
            print(f"⚠️ Payment not found for intent: {payment_intent['id']}")
    
    def handle_payment_failed(self, payment_intent):
        """Update payment status to failed"""
        payment = PaymentModel.objects.filter(
            stripe_payment_intent_id=payment_intent['id']
        ).first()
        
        if payment:
            payment.payment_status = 'failed'
            payment.save()
            print(f"❌ Payment {payment.id} marked as failed")


class ManyChatPaymentCheck(APIView):
    """Check payment status for ManyChat integration"""
    
    def get(self, request, fb_id):
        try:
            payment = PaymentModel.objects.filter(
                fb_id=fb_id,
                manychat_payment=False
            ).latest('updated_at')
            
            print(f"📋 Checking payment for fb_id={fb_id}: {payment}")
            
            # ✅ FIXED: Check if manychat_payment is FALSE (not TRUE)
            if not payment.manychat_payment:
                payment.manychat_payment = True
                payment.save()
                
                print(f"✅ ManyChat payment marked for fb_id={fb_id}, package={payment.package}")
                
                return Response({
                    'success': payment.package,
                    'payment_status': payment.payment_status,
                    'amount': payment.amount,
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'success': False, 'message': 'Payment already checked'}, 
                    status=status.HTTP_200_OK
                )
                
        except PaymentModel.DoesNotExist:
            print(f"❌ No payments found for fb_id={fb_id}")
            return Response(
                {'success': False, 'message': 'No payments found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"❌ Error in ManyChat check: {str(e)}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )