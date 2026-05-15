from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, EventViewSet, DepartmentViewSet, TicketViewSet

# Create a router and register our viewsets with it.
router = DefaultRouter()

# 1. Users and Departments (Standard ViewSets)
router.register(r'users', UserViewSet)
router.register(r'departments', DepartmentViewSet)

# 2. Events and Tickets (Custom Logic ViewSets)
# We MUST add 'basename' here because we used get_queryset() in views.py
router.register(r'events', EventViewSet, basename='event')
router.register(r'tickets', TicketViewSet, basename='ticket')

urlpatterns = [
    path('', include(router.urls)),
]