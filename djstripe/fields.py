# -*- coding: utf-8 -*-
"""
.. module:: djstripe.fields
   :synopsis: dj-stripe - Define some custom fields

.. moduleauthor:: Bill Huneke (@wahuneke)
"""
import decimal
from django.core.exceptions import ImproperlyConfigured


from django.db import models
from jsonfield import JSONField

from djstripe.utils import dict_nested_accessor, convert_tstamp


# Custom fields for all Stripe data. This allows keeping track of which database fields are suitable for sending
# to or receiving from Stripe. Also, allows a few handy extra parameters
class StripeFieldMixin(object):
    # Used if the name at stripe is different from the name in our database
    # Include a . in name if value is nested in dict in Stripe's object
    # (e.g.  stripe_name = "data.id"  -->  obj["data"]["id"])
    stripe_name = None

    # If stripe_name is None, this can also be used to specify a nested value, but
    # the final value is assumed to be the database field name
    # (e.g.    nested_name = "data"    -->  obj["data"][db_field_name]
    nested_name = None

    # This indicates that this field will always appear in a stripe object. It will be
    # an Exception if we try to parse a stripe object that does not include this field
    # in the data. If set to False then null=True attribute will be automatically set
    stripe_required = True

    # If a field was populated in previous API versions but we don't want to drop the old
    # data for some reason, mark it as deprecated. This will make sure we never try to send
    # it to Stripe or expect in Stripe data received
    # This setting automatically implies Null=True
    deprecated = False

    def __init__(self, *args, **kwargs):
        self.stripe_name = kwargs.pop('stripe_name', self.stripe_name)
        self.nested_name = kwargs.pop('nested_name', self.nested_name)
        self.stripe_required = kwargs.pop('stripe_required', self.stripe_required)
        self.deprecated = kwargs.pop('deprecated', self.deprecated)
        if not self.stripe_required:
            kwargs["null"] = True

        if self.deprecated:
            kwargs["null"] = True
            kwargs["default"] = None
        super(StripeFieldMixin, self).__init__(*args, **kwargs)

    def stripe_to_db(self, data):
        if not self.deprecated:
            try:
                if self.stripe_name:
                    result = dict_nested_accessor(data, self.stripe_name)
                elif self.nested_name:
                    result = dict_nested_accessor(data, self.nested_name + "." + self.name)
                else:
                    result = data[self.name]
            except KeyError:
                if self.stripe_required:
                    raise
                else:
                    result = None

            return result


class StripeCurrencyField(StripeFieldMixin, models.DecimalField):
    """
    Stripe is always in cents. djstripe stores everything in dollars.
    """
    def __init__(self, *args, **kwargs):
        defaults = {
            'decimal_places': 2,
            'max_digits': 7,
        }
        defaults.update(kwargs)
        super(StripeCurrencyField, self).__init__(*args, **defaults)

    def stripe_to_db(self, data):
        val = super(StripeCurrencyField, self).stripe_to_db(data)
        if val is not None:
            return val / decimal.Decimal("100")


class StripeBooleanField(StripeFieldMixin, models.BooleanField):
    def __init__(self, *args, **kwargs):
        if kwargs.get("deprecated", False):
            raise ImproperlyConfigured("Boolean field cannot be deprecated. Change field type "
                                       "StripeNullBooleanField")
        super(StripeBooleanField, self).__init__(*args, **kwargs)


class StripeNullBooleanField(StripeFieldMixin, models.NullBooleanField):
    pass


class StripeCharField(StripeFieldMixin, models.CharField):
    pass


class StripeIdField(StripeCharField):
    """
    A field with enough space to hold any stripe ID
    """
    def __init__(self, *args, **kwargs):
        defaults = {
            'max_length': 50,
            'blank': False,
            'null': False,
        }
        defaults.update(kwargs)
        super(StripeIdField, self).__init__(*args, **defaults)


class StripeTextField(StripeFieldMixin, models.TextField):
    pass


class StripeDateTimeField(StripeFieldMixin, models.DateTimeField):
    def stripe_to_db(self, data):
        if not self.deprecated:
            return convert_tstamp(super(StripeDateTimeField, self).stripe_to_db(data))


class StripeIntegerField(StripeFieldMixin, models.IntegerField):
    pass


class StripePositiveIntegerField(StripeFieldMixin, models.PositiveIntegerField):
    pass


class StripeJSONField(StripeFieldMixin, JSONField):
    def stripe_to_db(self, data):
        if self.stripe_name:
            # If this is defined, then we grab the value at that location
            return super(StripeJSONField, self).stripe_to_db(data)
        else:
            # Otherwise, we use the whole data block
            return data
