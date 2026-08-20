from django.contrib.sites import requests
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from carts.models import CartItem
from mysite import settings
from .forms import OrderForm
import datetime
from .models import Order, Payment, OrderProduct
import json
from store.models import Product
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
import requests

def payments(request):
    body = json.loads(request.body)
    order = Order.objects.get(user=request.user, is_ordered=False, order_number=body['orderID'])

    # Store transaction details inside Payment model
    payment = Payment(
        user = request.user,
        payment_id = body['transID'],
        payment_method = body['payment_method'],
        amount_paid = order.order_total,
        status = body['status'],
    )
    payment.save()

    order.payment = payment
    order.is_ordered = True
    order.save()

    # Move the cart items to Order Product table
    cart_items = CartItem.objects.filter(user=request.user)

    for item in cart_items:
        orderproduct = OrderProduct()
        orderproduct.order_id = order.id
        orderproduct.payment = payment
        orderproduct.user_id = request.user.id
        orderproduct.product_id = item.product_id
        orderproduct.quantity = item.quantity
        orderproduct.product_price = item.product.price
        orderproduct.ordered = True
        orderproduct.save()

        cart_item = CartItem.objects.get(id=item.id)
        product_variation = cart_item.variations.all()
        orderproduct = OrderProduct.objects.get(id=orderproduct.id)
        orderproduct.variations.set(product_variation)
        orderproduct.save()


        # Reduce the quantity of the sold products
        product = Product.objects.get(id=item.product_id)
        product.stock -= item.quantity
        product.save()

    # Clear cart
    CartItem.objects.filter(user=request.user).delete()

    # Send order recieved email to customer
    mail_subject = 'Thank you for your order!'
    message = render_to_string('orders/order_recieved_email.html', {
        'user': request.user,
        'order': order,
    })
    to_email = request.user.email
    send_email = EmailMessage(mail_subject, message, to=[to_email])
    send_email.send()

    # Send order number and transaction id back to sendData method via JsonResponse
    data = {
        'order_number': order.order_number,
        'transID': payment.payment_id,
    }
    return JsonResponse(data)

def browser_safe_client_token(request):
    try:
        client_token = get_paypal_client_token()

        return JsonResponse({
            "success": True,
            "clientToken": client_token,
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e),
        }, status=500)
def get_paypal_access_token():
    url = f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token"

    response = requests.post(
        url,
        auth=(
            settings.PAYPAL_CLIENT_ID,
            settings.PAYPAL_CLIENT_SECRET,
        ),
        headers={
            "Accept": "application/json",
            "Accept-Language": "en_US",
        },
        data={
            "grant_type": "client_credentials",
        },
    )

    response.raise_for_status()

    return response.json()["access_token"]

def get_paypal_client_token():
    url = f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token"

    response = requests.post(
        url,
        auth=(
            settings.PAYPAL_CLIENT_ID,
            settings.PAYPAL_CLIENT_SECRET,
        ),
        headers={
            "Accept": "application/json",
            "Accept-Language": "en_US",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "client_credentials",
            "response_type": "client_token",
            "intent": "sdk_init",
        },
    )

    print("PAYPAL STATUS:", response.status_code)
    print("PAYPAL RESPONSE:", response.text)

    response.raise_for_status()

    return response.json()["access_token"]




def test_paypal(request):
    try:
        token = get_paypal_access_token()

        return JsonResponse({
            "success": True,
            "message": "PayPal connection successful"
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)
def create_paypal_order(amount):
    access_token = get_paypal_access_token()

    url = f"{settings.PAYPAL_BASE_URL}/v2/checkout/orders"

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "amount": {
                    "currency_code": "USD",
                    "value": str(amount),
                }
            }
        ],
    }

    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
        json=payload,
    )

    response.raise_for_status()

    return response.json()
def create_order(request):

    if request.method != 'POST':
        return JsonResponse({
            "success": False,
            "error": "POST request required"
        }, status=405)

    try:

        # --------------------------------------------------
        # 1. Read Django order number sent from payments.html
        # --------------------------------------------------

        body = json.loads(request.body)

        order_number = body.get("order_number")

        print(
            "PAYPAL CREATE ORDER - RECEIVED:",
            body
        )

        print(
            "PAYPAL CREATE ORDER - ORDER NUMBER:",
            order_number
        )

        if not order_number:
            return JsonResponse({
                "success": False,
                "error": "Order number is required."
            }, status=400)


        # --------------------------------------------------
        # 2. Find the exact Django Order
        # --------------------------------------------------

        order = Order.objects.get(
            user=request.user,
            order_number=order_number,
            is_ordered=False
        )


        # --------------------------------------------------
        # 3. Get amount from Django Order
        # --------------------------------------------------

        grand_total = order.order_total


        # --------------------------------------------------
        # 4. Create PayPal Order
        # --------------------------------------------------

        paypal_order = create_paypal_order(
            grand_total
        )


        # --------------------------------------------------
        # 5. Return PayPal Order ID
        # --------------------------------------------------

        return JsonResponse({

            "success": True,

            "id": paypal_order["id"],

            "status": paypal_order["status"],

            "amount": str(grand_total),

            "order_number": order.order_number,

        })


    except Order.DoesNotExist:

        return JsonResponse({
            "success": False,
            "error": "Django order not found."
        }, status=404)


    except Exception as e:

        return JsonResponse({

            "success": False,

            "error": str(e)

        }, status=500)
def place_order(request):
    current_user = request.user
    
    cart_items = CartItem.objects.filter(user=current_user)

    if not cart_items.exists():
        return redirect('store')

    total = 0
    quantity = 0

    for cart_item in cart_items:
        total += cart_item.product.price * cart_item.quantity
        quantity += cart_item.quantity

    tax = (2 * total) / 100
    grand_total = total + tax

    if request.method != 'POST':
        return redirect('checkout')

    form = OrderForm(request.POST)

    if not form.is_valid():
        print("FORM ERRORS:", form.errors)

        return render(request, 'orders/checkout.html', {
            'form': form,
            'cart_items': cart_items,
            'total': total,
            'tax': tax,
            'grand_total': grand_total,
        })

    # Create Order
    data = Order()
    data.user = current_user
    data.first_name = form.cleaned_data['first_name']
    data.last_name = form.cleaned_data['last_name']
    data.phone = form.cleaned_data['phone']
    data.email = form.cleaned_data['email']
    data.address_line_1 = form.cleaned_data['address_line_1']
    data.address_line_2 = form.cleaned_data['address_line_2']
    data.country = form.cleaned_data['country']
    data.state = form.cleaned_data['state']
    data.city = form.cleaned_data['city']
    data.order_note = form.cleaned_data['order_note']

    data.order_total = grand_total
    data.tax = tax
    data.ip = request.META.get('REMOTE_ADDR')

    data.save()

    # Generate order number
    current_date = datetime.date.today().strftime("%Y%m%d")
    data.order_number = current_date + str(data.id)
    data.save()

    order = Order.objects.get(
        user=current_user,
        is_ordered=False,
        order_number=data.order_number
    )

    context = {
        'order': order,
        'cart_items': cart_items,
        'total': total,
        'tax': tax,
        'grand_total': grand_total,
    }

    return render(request, 'orders/payments.html', context)


def capture_paypal_order(order_id):
    access_token = get_paypal_access_token()

    url = (
        f"{settings.PAYPAL_BASE_URL}"
        f"/v2/checkout/orders/{order_id}/capture"
    )

    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
    )

    response.raise_for_status()

    return response.json()
def capture_order(request, order_id):

    if request.method != 'POST':
        return JsonResponse({
            "success": False,
            "error": "POST request required"
        }, status=405)

    try:

        # --------------------------------------------------
        # 1. Capture payment through PayPal
        # --------------------------------------------------

        paypal_response = capture_paypal_order(
            order_id
        )

        print(
            "PAYPAL CAPTURE RESPONSE:",
            paypal_response
        )


        # --------------------------------------------------
        # 2. Make sure payment was completed
        # --------------------------------------------------

        if paypal_response.get("status") != "COMPLETED":

            return JsonResponse({
                "success": False,
                "error": "PayPal payment was not completed.",
            }, status=400)


        # --------------------------------------------------
        # 3. Get PayPal capture information
        # --------------------------------------------------

        purchase_unit = (
            paypal_response
            ["purchase_units"][0]
        )

        capture = (
            purchase_unit
            ["payments"]
            ["captures"][0]
        )

        capture_id = capture["id"]

        captured_amount = float(
            capture["amount"]["value"]
        )


        # --------------------------------------------------
        # 4. Find the Django Order
        # --------------------------------------------------

        # We need the Django order number.
        # It was stored when create_order() created
        # the PayPal order.

        body = json.loads(request.body)

        order_number = body.get("order_number")

        print("CAPTURE RECEIVED:", body)
        print("CAPTURE ORDER NUMBER:", order_number)

        if not order_number:
            return JsonResponse({
                "success": False,
                "error": "Order number is required."
            }, status=400)


        order = Order.objects.get(
            user=request.user,
            order_number=order_number,
            is_ordered=False
        )


        # --------------------------------------------------
        # 5. Verify amount
        # --------------------------------------------------

        if round(captured_amount, 2) != round(
            order.order_total,
            2
        ):

            return JsonResponse({
                "success": False,
                "error": "Payment amount does not match order amount."
            }, status=400)


        # --------------------------------------------------
        # 6. Create Payment
        # --------------------------------------------------

        payment = Payment.objects.create(

            user=request.user,

            payment_id=capture_id,

            payment_method="PayPal",

            amount_paid=str(
                captured_amount
            ),

            status="COMPLETED",

        )


        # --------------------------------------------------
        # 7. Attach Payment to Order
        # --------------------------------------------------

        order.payment = payment

        order.is_ordered = True

        order.save()


        # --------------------------------------------------
        # 8. Move CartItems → OrderProduct
        # --------------------------------------------------

        cart_items = CartItem.objects.filter(
            user=request.user
        )


        for item in cart_items:

            orderproduct = OrderProduct.objects.create(

                order=order,

                payment=payment,

                user=request.user,

                product=item.product,

                quantity=item.quantity,

                product_price=item.product.price,

                ordered=True,

            )


            # Copy variations

            product_variation = (
                item.variations.all()
            )

            orderproduct.variations.set(
                product_variation
            )


            # --------------------------------------------------
            # Reduce product stock
            # --------------------------------------------------

            product = Product.objects.get(
                id=item.product_id
            )

            product.stock -= item.quantity

            product.save()


        # --------------------------------------------------
        # 9. Clear cart
        # --------------------------------------------------

        CartItem.objects.filter(
            user=request.user
        ).delete()


        # --------------------------------------------------
        # 10. Send order email
        # --------------------------------------------------

        mail_subject = 'Thank you for your order!'

        message = render_to_string(
            'orders/order_recieved_email.html',
            {
                'user': request.user,
                'order': order,
            }
        )

        to_email = request.user.email

        # send_email = EmailMessage(
        #     mail_subject,
        #     message,
        #     to=[to_email]
        # )

        # send_email.send()


        # --------------------------------------------------
        # 11. Return order information
        # --------------------------------------------------

        return JsonResponse({

            "success": True,

            "status": "COMPLETED",

            "order_number":
                order.order_number,

            "transID":
                payment.payment_id,

            "payment_id":
                payment.payment_id,

        })


    except Order.DoesNotExist:

        return JsonResponse({
            "success": False,
            "error": "Django order not found."
        }, status=404)


    except Exception as e:

        print(
            "PAYPAL CAPTURE ERROR:",
            e
        )

        return JsonResponse({

            "success": False,

            "error": str(e)

        }, status=500)
def order_complete(request):
    order_number = request.GET.get('order_number')
    transID = request.GET.get('payment_id')

    try:
        order = Order.objects.get(
            order_number=order_number,
            is_ordered=True
        )

        ordered_products = OrderProduct.objects.filter(
            order_id=order.id
        )

        subtotal = 0

        for i in ordered_products:
            subtotal += i.product_price * i.quantity

        payment = Payment.objects.get(
            payment_id=transID
        )

        context = {
            'order': order,
            'ordered_products': ordered_products,
            'order_number': order.order_number,
            'transID': payment.payment_id,
            'payment': payment,
            'subtotal': subtotal,
        }

        return render(
            request,
            'orders/order_complete.html',
            context
        )

    except (Payment.DoesNotExist, Order.DoesNotExist):
        return redirect('home')