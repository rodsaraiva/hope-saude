# meuprojeto/urls.py

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from contas.forms import CustomAuthenticationForm
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

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

# --- CONFIGURAÇÃO DE MÍDIA ---
# Em desenvolvimento, usa o servidor de desenvolvimento do Django
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Em produção, adiciona uma rota para servir arquivos de mídia
    # Esta é uma solução temporária - em produção real, considere usar um CDN ou servidor web
    urlpatterns += [
        path('media/<path:path>', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
    ]