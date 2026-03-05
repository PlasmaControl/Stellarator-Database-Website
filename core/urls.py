from django.urls import path
from . import views

urlpatterns = [
    # Main pages
    path('', views.home_view, name='home'),
    path('upload/', views.upload_view, name='upload'),
    path('query/', views.query_view, name='query'),
    path('data-description/', views.data_description_view, name='data_description'),

    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),

    # AJAX API
    path('api/columns/single/', views.api_columns_single, name='api_columns_single'),
    path('api/columns/', views.api_columns, name='api_columns'),
    path('api/query/', views.api_query, name='api_query'),
]
