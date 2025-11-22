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
    """
    Render the payment page
    URL: /payment/
    """
    return render(request, 'payment.html')


def payment_success_page(request):
    """
    Render the payment success page
    URL: /payment-success.html
    """
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
            print(fb_id, amount, package, currency, description)
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
            
            return Response({
                'success': True,
                'client_secret': payment_intent.client_secret,
                'payment_intent_id': payment_intent.id,
                'payment_id': payment.id,
                'publishable_key': config('STRIPE_PUBLIC_KEY', default='')
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            print(f"Error creating payment intent: {str(e)}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



class PaymentSuccessView(APIView):
    """
    Update payment status after successful payment
    """
    def post(self, request):
        try:
            payment_intent_id = request.data.get('payment_intent_id')
            
            if not payment_intent_id:
                return Response(
                    {'error': 'payment_intent_id is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
    
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
          
            payment = PaymentModel.objects.filter(
                stripe_payment_intent_id=payment_intent_id
            ).first()
            
            if not payment:
                return Response(
                    {'error': 'Payment not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if payment_intent.charges.data:
                charge = payment_intent.charges.data[0]
                payment_method_details = charge.payment_method_details
                
                if payment_method_details.type == 'card':
                    if payment_method_details.card.wallet:
                        wallet_type = payment_method_details.card.wallet.type
                        if wallet_type == 'google_pay':
                            payment.payment_method = 'google_pay'
                        elif wallet_type == 'apple_pay':
                            payment.payment_method = 'apple_pay'
                        else:
                            payment.payment_method = 'card'
                    else:
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
            
        except Exception as e:
            print(f"Error confirming payment: {str(e)}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )




@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
   
    
    def post(self, request):
        payload = request.body
        # print(payload)
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        webhook_secret = config('STRIPE_WEBHOOK_SECRET', default='')
        
        if not webhook_secret:
            
            return HttpResponse(status=200)
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError:
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            return HttpResponse(status=400)
        
     
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            self.handle_payment_success(payment_intent)
            
        elif event['type'] == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            self.handle_payment_failed(payment_intent)
        
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
            print(f"✅ Payment {payment.id} marked as completed")
    
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
   
    def get(self, request, fb_id):
        try:
            
            payment = PaymentModel.objects.filter(
                fb_id=fb_id,
                manychat_payment=False
            ).latest('updated_at')
            print(payment)
            if payment.manychat_payment:
                
                payment.manychat_payment = True
                payment.save()
                
                return Response({
                    'success': payment.package,
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'success': False, 'message': 'No new payments found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except PaymentModel.DoesNotExist:
            return Response(
                {'success': False, 'message': 'No payments found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )