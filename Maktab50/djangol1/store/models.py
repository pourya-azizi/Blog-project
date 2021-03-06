from django.contrib.auth import get_user_model
from django.db import models
from django.utils.functional import cached_property
from django_jalali.db import models as jmodels
from django.utils.translation import ugettext_lazy as _
from . import enums
from .signals import order_placed
import logging

logger = logging.getLogger(__name__)


class Order(models.Model):
    """
    Represents an order
    """
    owner = models.ForeignKey(get_user_model(), on_delete=models.PROTECT, verbose_name=_('سفارش دهنده'))
    created_on = jmodels.jDateTimeField(auto_now_add=True, verbose_name=_('تاریخ ثبت'))
    status = models.CharField(
        verbose_name=_('Status'),
        help_text='وضعیت سفارش',
        choices=enums.OrderStatuses.choices,
        default=enums.OrderStatuses.CREATED,
        max_length=100
    )

    def __str__(self):
        return f'Order #{self.pk} for {self.owner}'

    def get_formatted_date(self):
        return self.created_on.strftime('%Y-%m-%d')

    # @property
    @cached_property
    def formatted_date(self):
        return self.get_formatted_date()

    def set_as_canceled(self):
        """
        Sets the order as canceled
        """
        self.status = enums.OrderStatuses.CANCELED
        self.save()
        logger.info(f'Order #{self.pk} was set as CANCELED.')

    def save(self, **kwargs):
        # Is this object new or edited
        if self.pk is None:
            created = True
        else:
            created = False

        super().save(**kwargs)

        # Dispatch order_placed signed
        order_placed.send(
            sender=self.__class__,
            instance=self,
            created=created
        )
        logger.debug(f'order_placed signal was sent for Order #{self.pk}.')


class OrderItem(models.Model):
    order = models.ForeignKey('store.Order', on_delete=models.CASCADE)
    product = models.ForeignKey('inventory.Product', on_delete=models.PROTECT, verbose_name=_('محصول'))
    qty = models.PositiveIntegerField(default=1, verbose_name=_('تعداد'))
    discount = models.FloatField(default=0)
    price = models.PositiveIntegerField()

