from rest_framework.exceptions import PermissionDenied
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator # --- NEW IMPORT FOR RESET PASSWORD ---

from .models import Event, Ticket, Department, User, Transaction
from .serializers import (
    EventSerializer, 
    TicketSerializer, 
    DepartmentSerializer, 
    RegisterSerializer,
    UserSerializer
)

# --- Custom Permission Class ---
class IsCoordinatorOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not request.user.is_authenticated:
            return False
            
        if request.method == 'POST' and request.user.role in ['student', 'student_coord']:
            return False
            
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        if user.role == 'it_admin':
            return True
        if user.role in ['hod', 'dept_coord'] and user.department == obj.department:
            return True
        if user.role == 'event_coord' and (obj.creator == user or obj.coordinator == user):
            return True
        if user.role == 'student_coord' and obj.student_coordinator == user:
            if request.method == 'DELETE':
                return False 
            return True 
        return False


# --- 1. User Management View ---
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return RegisterSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ['create', 'forgot_password', 'reset_password']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        user = serializer.save()
        try:
            send_mail(
                subject=f"Welcome to e4Tech 2026, {user.name}!",
                message=f"Hi {user.name},\n\nYour account has been successfully created.\nRole: {user.get_role_display()}\n\nGet ready to Innovate, Create, and Dominate!\n\nRegards,\ne4Tech Team",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Email failed: {e}")

    def update(self, request, *args, **kwargs):
        if 'role' in request.data:
            if request.user.role != 'it_admin':
                return Response({"error": "Permission Denied."}, status=status.HTTP_403_FORBIDDEN)
        
        response = super().update(request, *args, **kwargs)

        if 'role' in request.data and response.status_code == 200:
            updated_user = self.get_object()
            try:
                send_mail(
                    subject="Your e4Tech Role has been Updated!",
                    message=f"Hello {updated_user.name},\n\nYour role is now: {updated_user.get_role_display().upper()}.\n\nRegards,\ne4Tech IT Team",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[updated_user.email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Role update email failed: {e}")

        return response

    # --- NEW: FORGOT PASSWORD ENDPOINT ---
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def forgot_password(self, request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
            # Generate a secure token for this specific user
            token = default_token_generator.make_token(user)
            
            # Send the email
            send_mail(
                subject="e4Tech - Password Reset Request",
                message=f"Hi {user.name},\n\nYou requested a password reset. Here is your security token:\n\n{token}\n\nCopy and paste this token into the website to set a new password. If you did not request this, please ignore this email.\n\ne4Tech Team",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            return Response({"message": "Reset token sent to your email."})
            
        except User.DoesNotExist:
            # For security reasons, don't tell the hacker if the email exists or not
            return Response({"message": "If that email exists, a reset token has been sent."})

    # --- NEW: RESET PASSWORD ENDPOINT ---
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def reset_password(self, request):
        email = request.data.get('email')
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        
        try:
            user = User.objects.get(email=email)
            
            # Verify the token is valid and hasn't expired
            if default_token_generator.check_token(user, token):
                user.set_password(new_password)
                user.save()
                return Response({"message": "Password successfully reset! You can now login."})
            else:
                return Response({"error": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)
                
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)


# --- 2. Event Management View ---
class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsCoordinatorOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Event.objects.filter(status='approved')
        if user.role == 'it_admin':
            return Event.objects.all()
        if user.role in ['hod', 'dept_coord'] and user.department:
            return Event.objects.filter(department=user.department)
        if user.role in ['event_coord', 'student_coord']:
            return Event.objects.filter(
                Q(creator=user) | Q(coordinator=user) | Q(student_coordinator=user) | Q(status='approved')
            ).distinct()
        return Event.objects.filter(status='approved')

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        if 'status' in self.request.data:
            new_status = self.request.data['status']
            old_status = serializer.instance.status
            
            if new_status == 'approved' and old_status != 'approved':
                user = self.request.user
                event = serializer.instance
                if user.role not in ['it_admin', 'hod', 'dept_coord']:
                    raise PermissionDenied("You do not have permission to approve events.")
                if user.role in ['hod', 'dept_coord'] and user.department != event.department:
                    raise PermissionDenied("You can only approve events that belong to your own department.")
        serializer.save()

    # --- EXPORT PARTICIPANTS ENDPOINT ---
    @action(detail=True, methods=['get'])
    def participants(self, request, pk=None):
        event = self.get_object()
        user = request.user
        
        # 1. Security Check
        if user.role in ['student', 'student_coord']:
            return Response({"error": "Unauthorized. Only Event/Dept Coordinators can view participant lists."}, status=status.HTTP_403_FORBIDDEN)
            
        if user.role != 'it_admin':
            if user.role in ['hod', 'dept_coord'] and user.department != event.department:
                return Response({"error": "You can only view participants for your own department."}, status=status.HTTP_403_FORBIDDEN)
            elif user.role == 'event_coord' and user not in [event.creator, event.coordinator]:
                return Response({"error": "You can only view participants for your assigned events."}, status=status.HTTP_403_FORBIDDEN)

        # 2. Fetch all COMPLETED tickets for this event
        tickets = Ticket.objects.filter(event=event, transaction__status='COMPLETED').select_related('owner', 'transaction')
        
        # 3. Format data for the CSV
        data = []
        for t in tickets:
            data.append({
                "Ticket ID": f"#{t.id}",
                "Student Name": t.owner.name,
                "Email": t.owner.email,
                "Payment UTR": t.transaction.payment_reference,
                "Purchase Date": t.purchase_date.strftime("%Y-%m-%d %H:%M")
            })
            
        return Response(data)


# --- 3. Ticket View ---
class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Ticket.objects.filter(owner=self.request.user)

    @action(detail=False, methods=['post'])
    def buy(self, request):
        event_id = request.data.get('event_id')
        upi_id = request.data.get('payment_reference', 'CASH') 
        user = request.user

        try:
            with transaction.atomic():
                event = Event.objects.select_for_update().get(id=event_id)

                if event.status != 'approved':
                    return Response({"error": "Registration is not open for this event."}, status=400)

                if Ticket.objects.filter(event=event, owner=user).exists():
                    return Response({"error": "You already have a ticket."}, status=400)

                # --- SECURITY: Check UTR Uniqueness ---
                if upi_id != 'CASH' and Transaction.objects.filter(payment_reference=upi_id).exists():
                    return Response({"error": "Fraud Alert: This UTR / Transaction ID has already been used."}, status=400)

                # --- LOGISTICS: Check Event Capacity ---
                approved_tickets_count = Ticket.objects.filter(event=event, transaction__status='COMPLETED').count()
                if hasattr(event, 'capacity') and approved_tickets_count >= event.capacity:
                    return Response({"error": "Sorry! This event is completely Sold Out."}, status=400)

                ticket = Ticket.objects.create(event=event, owner=user)
                
                Transaction.objects.create(
                    ticket=ticket, 
                    amount=event.fee,
                    payment_reference=upi_id,
                    status='PENDING' 
                )

                try:
                    send_mail(
                        subject=f"Payment Pending Verification: {event.name}",
                        message=f"Hello {user.name},\n\nWe have received your UTR number ({upi_id}) for '{event.name}'.\nYour ticket is PENDING verification by the coordinator.\n\nYou will receive another email once it is approved.\n\ne4Tech Team",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    print(f"Email failed: {e}")
                
                return Response(TicketSerializer(ticket).data, status=201)
                
        except Event.DoesNotExist:
            return Response({"error": "Event not found"}, status=404)

    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        user = request.user
        if user.role == 'student':
            return Response({"error": "Unauthorized"}, status=403)
            
        pending_tickets = Ticket.objects.filter(transaction__status='PENDING').select_related('transaction', 'event', 'owner')
        
        if user.role != 'it_admin':
            pending_tickets = pending_tickets.filter(
                Q(event__coordinator=user) | Q(event__creator=user) | Q(event__department=user.department)
            )

        data = []
        for ticket in pending_tickets:
            data.append({
                "ticket_id": ticket.id,
                "event_name": ticket.event.name,
                "student_name": ticket.owner.name,
                "amount": ticket.transaction.amount,
                "utr_number": ticket.transaction.payment_reference,
                "date": ticket.purchase_date
            })
            
        return Response(data)

    @action(detail=False, methods=['post'])
    def approve_payment(self, request):
        user = request.user
        
        # --- FIXED: Blocked HODs from approving payments ---
        if user.role in ['student', 'student_coord', 'hod']:
            return Response({"error": "Unauthorized. HODs do not process payments."}, status=status.HTTP_403_FORBIDDEN)

        ticket_id = request.data.get('ticket_id')
        try:
            ticket = Ticket.objects.select_related('transaction', 'owner', 'event').get(id=ticket_id)
            
            # Security Check: Ensure Dept Coord and Event Coord only approve their own events
            if user.role != 'it_admin':
                if user.role == 'dept_coord' and user.department != ticket.event.department:
                    return Response({"error": "You can only approve payments for your own department."}, status=status.HTTP_403_FORBIDDEN)
                elif user.role == 'event_coord' and user not in [ticket.event.creator, ticket.event.coordinator]:
                    return Response({"error": "You can only approve payments for your assigned events."}, status=status.HTTP_403_FORBIDDEN)

            transaction = ticket.transaction
            
            if transaction.status == 'COMPLETED':
                return Response({"error": "Already approved."}, status=400)

            transaction.status = 'COMPLETED'
            transaction.save()

            try:
                send_mail(
                    subject=f"Ticket Confirmed: {ticket.event.name}",
                    message=f"Hi {ticket.owner.name},\n\nGood news! Your payment of Rs. {transaction.amount} (UTR: {transaction.payment_reference}) has been verified.\n\nYour ticket #{ticket.id} is now CONFIRMED. Check your dashboard for the QR Code.\n\ne4Tech Team",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[ticket.owner.email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Approval email failed: {e}")

            return Response({"message": "Payment Approved!"})
            
        except Ticket.DoesNotExist:
            return Response({"error": "Invalid Ticket"}, status=404)

    @action(detail=False, methods=['post'])
    def verify(self, request):
        # --- FIXED: Blocked HODs from scanning tickets ---
        if request.user.role in ['student', 'student_coord', 'hod']:
             return Response({"error": "Unauthorized. HODs cannot verify tickets at the gate."}, status=status.HTTP_403_FORBIDDEN)

        ticket_id = request.data.get('ticket_id')
        
        try:
            # Fetch ticket and linked transaction
            ticket = Ticket.objects.select_related('owner', 'event').get(id=ticket_id)
            
            # 1. Check if the payment was actually approved by a coordinator
            if not hasattr(ticket, 'transaction') or ticket.transaction.status != 'COMPLETED':
                return Response({
                    "valid": False, 
                    "error": "Payment for this ticket is still PENDING or missing."
                })

            # 2. Check if it was already scanned at the gate!
            if getattr(ticket, 'is_scanned', False):
                return Response({
                    "valid": False,
                    "error": "ALREADY USED! This ticket was already scanned at the gate.",
                    "owner": ticket.owner.name,
                    "event": ticket.event.name
                })

            # 3. If valid and not used yet, MARK IT AS SCANNED!
            ticket.is_scanned = True
            ticket.save()

            # Return success to the frontend
            return Response({
                "valid": True,
                "ticket_id": ticket.id,
                "event": ticket.event.name,
                "owner": ticket.owner.name,
                "payment_status": "PAID (COMPLETED)",
                "upi_reference": ticket.transaction.payment_reference
            })
            
        except Ticket.DoesNotExist:
            return Response({"valid": False, "error": "Invalid Ticket ID. Fake Ticket detected."}, status=404)


# --- 4. Department View ---
class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]