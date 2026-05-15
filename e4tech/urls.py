from django.contrib import admin
from django.urls import path, include
from django.conf import settings  # NEW: Import settings
from django.conf.urls.static import static  # NEW: Import static file server
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Connects to your API app
    path('api/', include('api.urls')),  
    
    # --- JWT LOGIN ENDPOINTS ---
    # These match the fetch('${API_BASE}/token/') call in your frontend
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

# NEW: Serve media files (like uploaded QR codes) during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)