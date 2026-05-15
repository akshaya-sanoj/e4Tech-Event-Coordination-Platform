from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

# --- 1. Custom User Manager ---
class CustomUserManager(BaseUserManager):
    def create_user(self, email, name, password=None, **extra):
        if not email:
            raise ValueError('Users must have an email address')
        email = self.normalize_email(email)
        user = self.model(email=email, name=name, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('role', 'it_admin') # Superusers are IT Admin by default
        return self.create_user(email, name, password, **extra)


# --- 2. Department Model ---
class Department(models.Model):
    name = models.CharField(max_length=100)       # e.g., "Computer Science"
    code = models.CharField(max_length=10, unique=True) # e.g., "CS", "MECH"
    
    # Link a User as the Head (HOD) of this Department
    head = models.OneToOneField('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='headed_department')
    
    def __str__(self):
        return self.code


# --- 3. User Model ---
class User(AbstractBaseUser, PermissionsMixin):
    # UPDATED ROLES: Detailed Hierarchy
    ROLE_CHOICES = (
        ('student', 'Student'),                   # Can View/Buy
        ('student_coord', 'Student Coordinator'), # Works on specific event (Cannot Delete)
        ('event_coord', 'Event Coordinator'),     # Owns specific event (Full Control)
        ('dept_coord', 'Department Coordinator'), # Manages Dept Events
        ('hod', 'Head of Department'),            # Manages Dept Events & Approves
        ('it_admin', 'IT Admin'),                 # Super Admin (God Mode)
    )

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255)
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    
    # Link user to a department (Crucial for HODs, Coords, and Students)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return f"{self.name} ({self.role})"


# --- 4. Event Model (UPDATED FOR GPAY HYBRID & CAPACITY) ---
class Event(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    name = models.CharField(max_length=200)
    description = models.TextField()
    date = models.DateTimeField()
    venue = models.CharField(max_length=100, default="TBD")
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # NEW: Event Capacity Limit (Default 100 seats)
    capacity = models.PositiveIntegerField(default=100)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    # Coordinator's Payment Details
    upi_id = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., coord@oksbi")
    upi_qr_code = models.ImageField(upload_to='event_qrs/', blank=True, null=True)

    # Relationships
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_events')
    
    # --- ASSIGNMENTS ---
    # 1. Event Coordinator (Full Power for this event)
    coordinator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='coordinated_events')
    
    # 2. Student Coordinator (Worker Power: Edit but No Delete)
    student_coordinator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_coordinated_events')

    def __str__(self):
        return f"{self.name} ({self.status})"


# --- 5. Ticket/Registration Model (UPDATED FOR SCANNED LOGIC) ---
class Ticket(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='tickets')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='my_tickets')
    purchase_date = models.DateTimeField(auto_now_add=True)
    
    # NEW: To prevent double entry at the gate
    is_scanned = models.BooleanField(default=False)
    
    qr_code_hash = models.CharField(max_length=255, unique=True, null=True, blank=True)

    def __str__(self):
        return f"{self.owner.name} -> {self.event.name}"


# --- 6. Transaction Model (UPDATED FOR MANUAL VERIFICATION) ---
class Transaction(models.Model):
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # To store the UPI ID/UTR (e.g., student@oksbi or 3049XXXXX)
    payment_reference = models.CharField(max_length=100, default="CASH") 
    
    # Default is now PENDING because it requires manual approval
    status = models.CharField(max_length=20, default='PENDING')
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Txn: {self.payment_reference} - {self.status}"