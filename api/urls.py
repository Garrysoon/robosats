from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView

from chat.views import ChatView

from .views import (
    BookView,
    FederationView,
    HistoricalView,
    InfoView,
    LimitView,
    MakerView,
    OrderView,
    PriceView,
    RewardView,
    RobotView,
    StealthView,
    TickView,
    ReviewView,
    NotificationsView,
    CoordinatorMonitoringView,
    TaprootEscrowView,
    F2FSecurityView,
)

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("make/", MakerView.as_view(), name="make"),
    path(
        "order/",
        OrderView.as_view({"get": "get", "post": "take_update_confirm_dispute_cancel"}),
        name="order",
    ),
    path("robot/", RobotView.as_view(), name="robot"),
    path("book/", BookView.as_view(), name="book"),
    path("info/", InfoView.as_view({"get": "get"}), name="info"),
    path("price/", PriceView.as_view(), name="price"),
    path("limits/", LimitView.as_view(), name="limits"),
    path("reward/", RewardView.as_view(), name="reward"),
    path("historical/", HistoricalView.as_view(), name="historical"),
    path("ticks/", TickView.as_view(), name="ticks"),
    path("stealth/", StealthView.as_view(), name="stealth"),
    path("chat/", ChatView.as_view({"get": "get", "post": "post"}), name="chat"),
    path("notifications/", NotificationsView.as_view(), name="notifications"),
    path("review/", ReviewView.as_view(), name="review"),
    path("federation/", FederationView.as_view({"get": "get"}), name="federation"),
    path(
        "monitoring/coordinators/",
        CoordinatorMonitoringView.as_view({"get": "get", "post": "post"}),
        name="coordinator_monitoring",
    ),
    path(
        "order/<int:pk>/escrow/create/",
        TaprootEscrowView.as_view({"post": "create_escrow"}),
        name="order_escrow_create",
    ),
    path(
        "order/<int:pk>/escrow/status/",
        TaprootEscrowView.as_view({"get": "get_status"}),
        name="order_escrow_status",
    ),
    path(
        "order/<int:pk>/escrow/sign/",
        TaprootEscrowView.as_view({"post": "submit_signature"}),
        name="order_escrow_sign",
    ),
    path(
        "order/<int:pk>/escrow/arbitrate/",
        TaprootEscrowView.as_view({"post": "arbitrate"}),
        name="order_escrow_arbitrate",
    ),
    path(
        "order/<int:pk>/f2f/status/",
        F2FSecurityView.as_view({"get": "get_status"}),
        name="order_f2f_status",
    ),
    path(
        "order/<int:pk>/f2f/arrived/",
        F2FSecurityView.as_view({"post": "arrived"}),
        name="order_f2f_arrived",
    ),
    path(
        "order/<int:pk>/f2f/verify_pin/",
        F2FSecurityView.as_view({"post": "verify_pin"}),
        name="order_f2f_verify_pin",
    ),
    path(
        "order/<int:pk>/f2f/setup/",
        F2FSecurityView.as_view({"post": "setup_pin"}),
        name="order_f2f_setup",
    ),
]
