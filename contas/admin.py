# contas/admin.py

from django.contrib import admin
from .models import (
    PerfilProfissional, PerfilPaciente, Especialidade, Agendamento,
    RegraDisponibilidade, Avaliacao  # <-- RegraDisponibilidade adicionado
    # Remova Disponibilidade e DisponibilidadeAvulsa dos imports se estiverem aqui
)
from django.utils import timezone

@admin.register(Especialidade)
class EspecialidadeAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)

@admin.register(PerfilProfissional)
class PerfilProfissionalAdmin(admin.ModelAdmin):
    list_display = ('user', 'tipo_profissional', 'numero_registro', 'valor_consulta')
    list_filter = ('tipo_profissional',)
    search_fields = ('user__username', 'numero_registro', 'especialidades__nome')
    filter_horizontal = ('especialidades',)

@admin.register(PerfilPaciente)
class PerfilPacienteAdmin(admin.ModelAdmin):
    list_display = ('user', 'data_nascimento', 'telefone_contato')
    search_fields = ('user__username', 'telefone_contato')

@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = ('data_hora', 'paciente', 'profissional', 'status', 'status_pagamento', 'criado_em')
    list_filter = ('status', 'status_pagamento', 'profissional', 'paciente', 'data_hora')
    search_fields = ('paciente__user__username', 'profissional__user__username', 'notas_paciente', 'notas_profissional')
    date_hierarchy = 'data_hora'
    raw_id_fields = ('paciente', 'profissional') # Útil para muitos usuários

@admin.register(RegraDisponibilidade)
class RegraDisponibilidadeAdmin(admin.ModelAdmin):
    list_display = (
        'profissional', 'tipo_regra', 'get_dia_semana_formatado',
        'hora_inicio_recorrente_formatada', 'hora_fim_recorrente_formatada',
        'data_hora_inicio_especifica_formatada', 'data_hora_fim_especifica_formatada',
        'criado_em'
    )
    list_filter = ('profissional', 'tipo_regra', 'dia_semana')
    search_fields = ('profissional__user__username',)
    raw_id_fields = ('profissional',)

    # REMOVA OU COMENTE ESTA SEÇÃO 'fields':
    # fields = (
    #     'profissional', 'tipo_regra',
    #     ('dia_semana', 'hora_inicio_recorrente', 'hora_fim_recorrente'),
    #     ('data_hora_inicio_especifica', 'data_hora_fim_especifica')
    # )

    # MANTENHA ESTA SEÇÃO 'fieldsets':
    fieldsets = (
        (None, { # Seção principal, sem título específico
            'fields': ('profissional', 'tipo_regra')
        }),
        ('Detalhes para Regra Semanal Recorrente', {
            'classes': ('collapse',), # Começa recolhido para limpar a interface
            'fields': ('dia_semana', 'hora_inicio_recorrente', 'hora_fim_recorrente'),
            'description': "Preencha estes campos APENAS se o 'Tipo de Regra' for 'Semanal Recorrente'."
        }),
        ('Detalhes para Regra de Data/Hora Específica', {
            'classes': ('collapse',), # Começa recolhido
            'fields': ('data_hora_inicio_especifica', 'data_hora_fim_especifica'),
            'description': "Preencha estes campos APENAS se o 'Tipo de Regra' for 'Data/Hora Específica'."
        }),
    )

    # Métodos para formatar a exibição na lista (como antes)
    def get_dia_semana_formatado(self, obj):
        return obj.get_dia_semana_display() if obj.tipo_regra == 'SEMANAL' and obj.dia_semana is not None else "-"
    get_dia_semana_formatado.admin_order_field = 'dia_semana'
    get_dia_semana_formatado.short_description = 'Dia (Semanal)'

    def hora_inicio_recorrente_formatada(self, obj):
        return obj.hora_inicio_recorrente.strftime('%H:%M') if obj.tipo_regra == 'SEMANAL' and obj.hora_inicio_recorrente else "-"
    hora_inicio_recorrente_formatada.admin_order_field = 'hora_inicio_recorrente'
    hora_inicio_recorrente_formatada.short_description = 'Início (Semanal)'

    def hora_fim_recorrente_formatada(self, obj):
        return obj.hora_fim_recorrente.strftime('%H:%M') if obj.tipo_regra == 'SEMANAL' and obj.hora_fim_recorrente else "-"
    hora_fim_recorrente_formatada.admin_order_field = 'hora_fim_recorrente'
    hora_fim_recorrente_formatada.short_description = 'Fim (Semanal)'

    def data_hora_inicio_especifica_formatada(self, obj):
        return timezone.localtime(obj.data_hora_inicio_especifica).strftime('%d/%m/%y %H:%M') if obj.tipo_regra == 'ESPECIFICA' and obj.data_hora_inicio_especifica else "-"
    data_hora_inicio_especifica_formatada.admin_order_field = 'data_hora_inicio_especifica'
    data_hora_inicio_especifica_formatada.short_description = 'Início (Específico)'

    def data_hora_fim_especifica_formatada(self, obj):
        return timezone.localtime(obj.data_hora_fim_especifica).strftime('%d/%m/%y %H:%M') if obj.tipo_regra == 'ESPECIFICA' and obj.data_hora_fim_especifica else "-"
    data_hora_fim_especifica_formatada.admin_order_field = 'data_hora_fim_especifica'
    data_hora_fim_especifica_formatada.short_description = 'Fim (Específico)'

# --- NOVA CLASSE ADICIONADA ---
@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ('agendamento', 'avaliador', 'avaliado', 'nota', 'data_criacao')
    list_filter = ('nota', 'avaliado')
    search_fields = ('avaliador__user__username', 'avaliado__user__username', 'comentario')
    # raw_id_fields é útil quando há muitos usuários, para não carregar um dropdown gigante
    raw_id_fields = ('agendamento', 'avaliador', 'avaliado')
    readonly_fields = ('data_criacao',) # Não permite editar a data de criação