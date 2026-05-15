from rest_framework import serializers
from .models import User, Event, Ticket, Department

# --- 1. User Management Serializer ---
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'role', 'department']
        extra_kwargs = {'password': {'write_only': True}} 

# --- 2. Department Serializer ---
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'code', 'head']

# --- 3. User Registration Serializer ---
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    # Allow looking up department by code (e.g., "CS") or ID
    department = serializers.SlugRelatedField(
        slug_field='code', 
        queryset=Department.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = User
        fields = ['email', 'name', 'password', 'role', 'department']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

# --- 4. Event Serializer (UPDATED FOR GPAY) ---
class EventSerializer(serializers.ModelSerializer):
    # Handle Department via Code (e.g., "CS")
    department = serializers.SlugRelatedField(
        slug_field='code',
        queryset=Department.objects.all()
    )

    # Read-only names for display
    creator_name = serializers.ReadOnlyField(source='creator.name')
    coordinator_name = serializers.ReadOnlyField(source='coordinator.name')
    student_coordinator_name = serializers.ReadOnlyField(source='student_coordinator.name')

    # Coordinator Assignments
    coordinator = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True
    )
    
    # Student Coordinator Assignment
    student_coordinator = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = Event
        fields = [
            'id', 
            'name', 
            'description', 
            'date', 
            'venue', 
            'fee', 
            'status', 
            'department', 
            'creator', 
            'creator_name', 
            'coordinator', 
            'coordinator_name',
            'student_coordinator',
            'student_coordinator_name',
            'upi_id',        # <--- NEW: Added for GPay
            'upi_qr_code'    # <--- NEW: Added for GPay Image
        ]
        read_only_fields = ['creator'] 

    def create(self, validated_data):
        # Automatically assign the creator to the logged-in user
        validated_data['creator'] = self.context['request'].user
        user_role = self.context['request'].user.role
        
        # --- AUTO APPROVAL LOGIC ---
        # IT Admin, HOD, and Dept Coord get instant approval
        if user_role in ['it_admin', 'hod', 'dept_coord']:
            validated_data['status'] = 'approved'
        else:
            # Event Coord, Student Coord, Students -> PENDING
            validated_data['status'] = 'pending'

        return super().create(validated_data)

# --- 5. Ticket Serializer ---
class TicketSerializer(serializers.ModelSerializer):
    event_name = serializers.ReadOnlyField(source='event.name')
    owner_name = serializers.ReadOnlyField(source='owner.name')

    class Meta:
        model = Ticket
        fields = ['id', 'event', 'event_name', 'owner', 'owner_name', 'purchase_date', 'qr_code_hash']
        read_only_fields = ['purchase_date', 'qr_code_hash']