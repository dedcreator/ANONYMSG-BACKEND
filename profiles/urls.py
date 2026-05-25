from django.urls import path
from .views import ProfileDetailView, PublicProfileView

urlpatterns = [
    path('', ProfileDetailView.as_view(), name='profile-detail'),
    path('public/<str:username>/', PublicProfileView.as_view(), name='public-profile'),
]