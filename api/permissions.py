from rest_framework import permissions

class HierarchicalPermission(permissions.BasePermission):
    """
    IT Admin -> God Mode (Full Access)
    Super Admin -> Global View Only
    Dept Head -> Dept View Only
    Event Coordinator -> Create/Edit Own Events
    Student Coordinator -> Edit Assigned Events
    """
    
    def has_permission(self, request, view):
        # Allow anyone to login/register
        if view.action in ['create'] and 'users' in request.path: 
            return True 
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        role = user.role.name if user.role else 'Student'

        # --- 👑 NEW: IT ADMIN (GOD MODE) ---
        # IT Admins can do ANYTHING (View, Edit, Delete)
        if role == 'IT Admin':
            return True 

        # 1. READ PERMISSIONS (Viewing - GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            if role == 'Super Admin':
                return True # Principal sees everything (View Only)
            if role == 'Department Head':
                return obj.department == user.department # View only my Dept
            if role == 'Department Coordinator':
                return obj.department == user.department
            if role == 'Event Coordinator':
                return obj.department == user.department
            if role == 'Student Coordinator':
                # Can view events in their dept OR events they are assigned to
                return obj.department == user.department or user in obj.student_coordinators.all()
            return True # Students can view public events

        # 2. WRITE PERMISSIONS (Editing/Deleting - POST, PUT, DELETE)
        
        # Event Coordinators can edit events they created
        if role == 'Event Coordinator':
            return obj.creator == user
            
        # Student Coordinators can edit events they are assigned to
        if role == 'Student Coordinator':
            # Check if this event has this user in its 'student_coordinators' list
            return hasattr(obj, 'student_coordinators') and user in obj.student_coordinators.all()

        return False # Super Admins & Dept Heads cannot edit