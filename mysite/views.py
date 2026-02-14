from django.shortcuts import render
from product.models import Product

def home(request):
    products = Product.objects.all().filter(is_available=True)

    context = {
        'products': products,
        # 'reviews': reviews,
    }
    return render(request, 'home.html', context)    