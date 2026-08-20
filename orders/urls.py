from django.urls import path
from . import views

urlpatterns = [
    path('place_order/', views.place_order, name='place_order'),
    path('payments/', views.payments, name='payments'),
    path('test-paypal/', views.test_paypal, name='test_paypal'),
    path("create-order/", views.create_order, name='create_order'),
    path("capture-order/<str:order_id>/", views.capture_order, name="capture_order"),
    path('order_complete/', views.order_complete, name='order_complete'),
    path('paypal-api/auth/browser-safe-client-token/',views.browser_safe_client_token,name='browser_safe_client_token'),
]