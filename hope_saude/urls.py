# meuprojeto/urls.py

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from contas.forms import CustomAuthenticationForm

urlpatterns = [
    path('admin/', admin.site.urls),

    # URLs de autenticação padrão do Django e nosso login customizado FICAM com /contas/
    path('contas/login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        authentication_form=CustomAuthenticationForm
    ), name='login'),
    path('contas/', include('django.contrib.auth.urls')), # Para logout, password_reset, etc.

    # URLs do app 'contas' (exceto as de autenticação acima) são incluídas na raiz
    path('', include('contas.urls')),
]