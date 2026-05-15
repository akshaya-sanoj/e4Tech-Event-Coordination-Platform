from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Department, Event, Ticket, Transaction

# 1. Register User (Using default UserAdmin is safer)
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ('email', 'name', 'role', 'department', 'is_staff')
    list_filter = ('role', 'department', 'is_staff')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('name', 'role', 'department')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    ordering = ('email',)

admin.site.register(User, CustomUserAdmin)

# 2. Register Department
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')

# 3. Register Event
@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'status', 'fee', 'date')
    list_filter = ('status', 'department')

# 4. Register Ticket
@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('owner', 'event', 'purchase_date')

# 5. Register Transaction
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'amount', 'status', 'timestamp')