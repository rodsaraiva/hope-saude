# ProjetosDjango/contas/urls.py

from django.urls import path
from . import views

app_name = 'contas'

urlpatterns = [
    path('', views.index, name='index'),
    path('profissionais/', views.lista_profissionais, name='lista_profissionais'),
    path('profissionais/<int:pk>/', views.perfil_profissional_detail, name='perfil_profissional_detail'),
    path('registro/', views.registro, name='registro'),

    path('meu-perfil/', views.meu_perfil, name='meu_perfil'),
    path('meu-perfil/editar/', views.EditarPerfilView.as_view(), name='editar_perfil'),
    path('meus-agendamentos/', views.meus_agendamentos, name='meus_agendamentos'),
    path('agendamentos/cancelar/<int:agendamento_id>/', views.cancelar_agendamento, name='cancelar_agendamento'),
    path('agendamentos/criar/<int:profissional_id>/<str:timestamp_str>/', views.criar_agendamento, name='criar_agendamento'),
    path('agendamentos/confirmar/<int:agendamento_id>/', views.confirmar_agendamento, name='confirmar_agendamento'),
    path('agendamentos/marcar-realizado/<int:agendamento_id>/', views.marcar_realizado, name='marcar_realizado'),

    path('agendamentos/<int:agendamento_id>/pagamento/', views.processar_pagamento, name='processar_pagamento'),
    path('agendamentos/<int:agendamento_id>/sala/', views.sala_videochamada, name='sala_videochamada'),

    path('webhooks/stripe/', views.stripe_webhook, name='stripe_webhook'),

    path('meu-calendario/', views.calendario_profissional, name='meu_calendario'),

    path('api/avaliacoes/submeter/', views.api_submeter_avaliacao, name='api_submeter_avaliacao'),

    # URLs de API
    path('api/disponibilidade-avulsa/criar/', views.api_criar_disp_avulsa, name='api_criar_disp_avulsa'),
    path('api/regras-disponibilidade/excluir-lista/', views.api_excluir_regras_disponibilidade_lista, name='api_excluir_regras_disponibilidade_lista'),
    path('api/regras-disponibilidade/editar/<int:regra_id>/', views.api_editar_regra_disponibilidade, name='api_editar_regra_disponibilidade'),
    path('api/agendamentos/<int:agendamento_id>/obter-sala-video/', views.api_obter_ou_criar_sala_video, name='api_obter_ou_criar_sala_video'),
]