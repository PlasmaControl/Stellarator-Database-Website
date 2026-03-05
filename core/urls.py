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

    # Details page (opens in new tab from query results)
    path('details/<str:run_type>/<int:run_id>/', views.details_view, name='details'),

    # Downloads
    path('download-all/', views.download_all_view, name='download_all'),

    # AJAX API
    path('api/columns/single/', views.api_columns_single, name='api_columns_single'),
    path('api/columns/', views.api_columns, name='api_columns'),
    path('api/query/', views.api_query, name='api_query'),
]
