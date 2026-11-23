"""robosats URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from decouple import config
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.utils.translation import gettext_lazy as _

from api.views_docs import coordinator_docs_view

VERSION = settings.VERSION

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("coordinator/docs/<str:doc_id>/", coordinator_docs_view, name="coordinator_docs"),
    path("coordinator/docs/", coordinator_docs_view, name="coordinator_docs_default"),
    path("coordinator/", admin.site.urls),
    path("api/", include("api.urls")),
    # path('chat/', include('chat.urls')),
    path("", include("frontend.urls")),
]

admin.site.site_header = _("RoboSats Coordinator Administration")
admin.site.index_title = _("Coordinator administration")
admin.site.site_title = _("RoboSats Coordinator Admin")
