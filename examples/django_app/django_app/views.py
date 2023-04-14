from django import forms
from django.conf.urls import include, url
from django.utils.translation import ugettext_lazy as _

from acceptable import AcceptableService

service = AcceptableService("django_app")


class TestForm(forms.Form):
    foo = forms.EmailField(required=True, label=_("foo"), help_text=_("foo help"))

    bar = forms.ChoiceField(
        required=False,
        label=_("bar"),
        help_text=_("bar help"),
        choices=[("A", "AAA"), ("B", "BBB"), ("C", "CCC")],
    )

    baz = forms.DecimalField(required=False, label=_("baz"), help_text=_("baz help"))

    multi = forms.MultipleChoiceField(
        label=_("multi"),
        required=False,
        help_text=_("multi help"),
        choices=[("A", "AAA"), ("B", "BBB"), ("C", "CCC")],
    )


api = service.django_api("test", introduced_at=1)
api.django_form = TestForm


@api.handler
class TestHandler(object):
    """Documentation.

    Multiline."""

    allowed_methods = ("POST",)

    def __call__(self, *args):
        raise Exception("test only method")


urlpatterns = [
    url("^test$", TestHandler(), name="test"),
    url("^test2/(.*)$", TestHandler(), name="test2"),
    url("^login$", TestHandler(), name="login"),
    url("^prefix1/", include(("django_app.urls", "admin"))),
    url("^prefix2/", include(("django_app.urls", "admin"), namespace="other")),
]
