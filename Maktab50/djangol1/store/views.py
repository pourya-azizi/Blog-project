import weasyprint
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView
from inventory import models as inventory_models
from rest_framework import viewsets, permissions
from rest_framework.exceptions import NotAuthenticated

from . import models, serializers
from .models import logger


def add_to_cart(request, product_id):
    product_instance = get_object_or_404(inventory_models.Product, pk=product_id)

    # 1- Check if product is in stock
    if not product_instance.can_be_sold():
        messages.error(request, 'این محصول امکان فروش ندارد.')
        return redirect('inventory:list')

    # 2- Check if product can be sold
    if not product_instance.is_in_stock(1):
        messages.error(request, 'این محصول به تعداد مورد نظر موجود نیست.')
        return redirect('inventory:list')

    if 'cart' not in request.session.keys():
        request.session['cart'] = {
            # '1': 1
            # Product ID : Qty
        }

    # Method1
    if str(product_instance.pk) in request.session['cart'].keys():
        request.session['cart'][str(product_instance.pk)] += 1
    else:
        request.session['cart'][str(product_instance.pk)] = 1

    # Save the session!
    request.session.save()
    # request.session.is_modified.save

    # Method 2
    # try:
    #     print(request.session['cart'][str(product_instance.pk)])
    #     request.session['cart'][str(product_instance.pk)] += 1
    # except KeyError:
    #     request.session['cart'][str(product_instance.pk)] = 1

    print(request.session['cart'])
    messages.success(
        request,
        f'کالای '
        f'{product_instance.name}'
        f' به سبد افزوده شد.'
    )
    return redirect('inventory:list')


def view_cart(request):
    """
    Renders the cart items (the basket)
    """
    object_list = []
    for item in request.session.get('cart', []):
        object_list += [
            {
                'product': inventory_models.Product.objects.get(pk=int(item)),
                'qty': request.session['cart'][item]
            }
        ]

    return render(
        request, 'store/view_cart.html', context={'object_list': object_list}
    )


def delete_row(request, product_id):
    """
    delete a product row from cart
    """
    request.session['cart'].pop(str(product_id), None)
    request.session.modified = True
    messages.success(request, 'حذف شد')
    return redirect('store:view-cart')


@require_POST
@csrf_exempt
def deduct_from_cart(request):
    product_id = request.POST.get('product_id', None)
    if not product_id:
        return JsonResponse({'success': False, 'error': 'invalid data.'}, status=400)

    product_id = str(product_id)

    try:
        request.session['cart'][product_id] -= 1
        request.session.modified = True
        return JsonResponse({'success': True, 'qty': request.session['cart'][product_id]}, status=202)
    except KeyError:
        return JsonResponse({'success': False, 'error': 'invalid data. Not in the cart.'}, status=400)


@require_POST
@csrf_exempt
def adding(request):
    product_id = request.POST.get('product_id', None)
    if not product_id:
        return JsonResponse({'success': False, 'error': 'invalid data.'}, status=400)

    product_id = str(product_id)

    try:
        request.session['cart'][product_id] += 1
        request.session.modified = True
        return JsonResponse({'success': True, 'qty': request.session['cart'][product_id]}, status=202)
    except KeyError:
        return JsonResponse({'success': False, 'error': 'invalid data. Not in the cart.'}, status=400)


"""
DRF Views
"""


class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for store.Order
    """
    queryset = models.Order.objects.all()
    serializer_class = serializers.OrderSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.in_anonymous:
            raise NotAuthenticated('You need to be logged on')
        return qs.filter(owner=self.request.user)


@login_required
def finalize_order(request):

    cart = request.session.get('cart', None)

    if not cart:
        messages.error(request, 'سبد شما خالی است')
        return redirect('inventory:list')

    order_instance = models.Order.objects.create(owner=request.user)

    for product_id in cart:
        product = inventory_models.Product.objects.get(pk=product_id)
        qty = cart[product_id]

        if not product.is_in_stock(qty):
            messages.error(request, 'کالا به تعداد درخواست شده موجود نیست.')
            return redirect('store:view-cart')

        order_item_instance = models.OrderItem.objects.create(
            order=order_instance,
            qty=qty,
            product=product,
            price=product.price
        )

        # Deduct from stock
        product.deduct_from_stock(qty)

    messages.success(request, 'سفارش با موفقیت ثبت شد.')
    request.session.pop('cart')
    logger.info(f"User #{request.user.pk} placed an order #{order_instance.pk}.")

    request.session.modified = True
    return redirect('inventory:list')


class ListOrdersView(LoginRequiredMixin, ListView):
    model = models.Order
    paginate_by = 5

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(owner=self.request.user)
        return qs


class PrintOrder(LoginRequiredMixin, DetailView):
    model = models.Order

    def get(self, request, *args, **kwargs):
        g = super(PrintOrder, self).get(request, *args, **kwargs)

        rendered_content = g.rendered_content
        pdf = weasyprint.HTML(string=rendered_content).write_pdf()

        # Create a new http response with pdf mime type
        response = HttpResponse(pdf, content_type='application/pdf')
        return response
