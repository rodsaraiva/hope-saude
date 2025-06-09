# contas/models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

class Especialidade(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nome

    class Meta:
        ordering = ['nome']
        verbose_name = "Especialidade"
        verbose_name_plural = "Especialidades"

class PerfilProfissional(models.Model):
    TIPO_PROFISSIONAL_CHOICES = [
        ('PSICOLOGO', 'Psicólogo(a)'),
        ('PSIQUIATRA', 'Psiquiatra'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_profissional')
    tipo_profissional = models.CharField(max_length=15, choices=TIPO_PROFISSIONAL_CHOICES, null=True, blank=True)
    numero_registro = models.CharField(max_length=20, unique=True, help_text='Número do CRP ou CRM', null=True, blank=True)
    especialidades = models.ManyToManyField(Especialidade, blank=True, related_name='profissionais')
    bio = models.TextField(blank=True, help_text='Breve descrição sobre sua abordagem, experiência, etc.')
    telefone_contato = models.CharField(max_length=20, blank=True)
    endereco_consultorio = models.TextField(blank=True)
    anos_experiencia = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"Profissional: {self.user.username}"

    class Meta:
        verbose_name = "Perfil Profissional"
        verbose_name_plural = "Perfis Profissionais"

class PerfilPaciente(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_paciente')
    data_nascimento = models.DateField(null=True, blank=True)
    telefone_contato = models.CharField(max_length=20, blank=True)
    endereco = models.TextField(blank=True)
    contato_emergencia = models.CharField(max_length=100, blank=True, help_text='Nome e telefone do contato de emergência')

    def __str__(self):
        return f"Paciente: {self.user.username}"

    class Meta:
        verbose_name = "Perfil Paciente"
        verbose_name_plural = "Perfis Pacientes"

class RegraDisponibilidade(models.Model):
    TIPO_REGRA_CHOICES = [
        ('SEMANAL', 'Semanal Recorrente'),
        ('ESPECIFICA', 'Data/Hora Específica'),
    ]
    DIA_SEMANA_CHOICES = [ # Python's weekday(): Monday=0, Sunday=6
        (0, 'Segunda-feira'), (1, 'Terça-feira'), (2, 'Quarta-feira'),
        (3, 'Quinta-feira'), (4, 'Sexta-feira'), (5, 'Sábado'), (6, 'Domingo'),
    ]

    profissional = models.ForeignKey(
        PerfilProfissional,
        on_delete=models.CASCADE,
        related_name='regras_disponibilidade' # <-- related_name para buscar a partir do perfil
    )
    tipo_regra = models.CharField(
        max_length=10,
        choices=TIPO_REGRA_CHOICES,
        verbose_name="Tipo de Regra"
    )

    # Campos para tipo_regra == 'SEMANAL'
    dia_semana = models.IntegerField(
        choices=DIA_SEMANA_CHOICES,
        null=True, blank=True,
        verbose_name="Dia da Semana (p/ Semanal)"
    )
    hora_inicio_recorrente = models.TimeField(
        null=True, blank=True,
        verbose_name="Hora Início (p/ Semanal)"
    )
    hora_fim_recorrente = models.TimeField(
        null=True, blank=True,
        verbose_name="Hora Fim (p/ Semanal)"
    )

    # Campos para tipo_regra == 'ESPECIFICA'
    data_hora_inicio_especifica = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Início Específico (Data e Hora)"
    )
    data_hora_fim_especifica = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Fim Específico (Data e Hora)"
    )

    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        nome_profissional = self.profissional.user.username
        if self.tipo_regra == 'SEMANAL' and self.dia_semana is not None and self.hora_inicio_recorrente and self.hora_fim_recorrente:
            return (f"{nome_profissional} - Semanal: "
                    f"{self.get_dia_semana_display()} "
                    f"{self.hora_inicio_recorrente.strftime('%H:%M')}-"
                    f"{self.hora_fim_recorrente.strftime('%H:%M')}")
        elif self.tipo_regra == 'ESPECIFICA' and self.data_hora_inicio_especifica and self.data_hora_fim_especifica:
            return (f"{nome_profissional} - Específica: "
                    f"{timezone.localtime(self.data_hora_inicio_especifica).strftime('%d/%m/%y %H:%M')} a "
                    f"{timezone.localtime(self.data_hora_fim_especifica).strftime('%d/%m/%y %H:%M')}")
        return f"Regra ({self.get_tipo_regra_display()}) para {nome_profissional}"

    class Meta:
        ordering = ['profissional', 'tipo_regra', 'dia_semana', 'data_hora_inicio_especifica', 'hora_inicio_recorrente']
        verbose_name = "Regra de Disponibilidade"
        verbose_name_plural = "Regras de Disponibilidade"

    def clean(self):
        super().clean()
        if self.tipo_regra == 'SEMANAL':
            if self.dia_semana is None or not self.hora_inicio_recorrente or not self.hora_fim_recorrente:
                raise ValidationError(
                    "Para regras 'Semanal Recorrente', os campos 'Dia da Semana (p/ Semanal)', "
                    "'Hora Início (p/ Semanal)' e 'Hora Fim (p/ Semanal)' são obrigatórios."
                )
            if self.hora_inicio_recorrente >= self.hora_fim_recorrente:
                raise ValidationError({
                    'hora_fim_recorrente': "A hora de fim recorrente deve ser após a hora de início."
                })
            self.data_hora_inicio_especifica = None
            self.data_hora_fim_especifica = None
        elif self.tipo_regra == 'ESPECIFICA':
            if not self.data_hora_inicio_especifica or not self.data_hora_fim_especifica:
                raise ValidationError(
                    "Para regras 'Data/Hora Específica', os campos 'Início Específico' e "
                    "'Fim Específico' são obrigatórios."
                )
            if self.data_hora_inicio_especifica >= self.data_hora_fim_especifica:
                raise ValidationError({
                    'data_hora_fim_especifica': "O fim específico deve ser após o início específico."
                })
            if not self.pk and self.data_hora_inicio_especifica < timezone.now():
                raise ValidationError({
                     'data_hora_inicio_especifica': 'Não é possível adicionar disponibilidade específica no passado.'
                })
            self.dia_semana = None
            self.hora_inicio_recorrente = None
            self.hora_fim_recorrente = None
        else:
            raise ValidationError("Um tipo de regra válido deve ser selecionado.")

class Agendamento(models.Model):
    
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'), ('CONFIRMADO', 'Confirmado'),
        ('CANCELADO', 'Cancelado'), ('REALIZADO', 'Realizado'),
    ]
    paciente = models.ForeignKey(PerfilPaciente, on_delete=models.CASCADE, related_name='agendamentos_como_paciente') # Nome mais específico
    profissional = models.ForeignKey(
        PerfilProfissional,
        on_delete=models.CASCADE,
        related_name='agendamentos' # <-- related_name para buscar a partir do perfil
    )
    data_hora = models.DateTimeField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDENTE')
    notas_paciente = models.TextField(blank=True, null=True, help_text="Obs. paciente")
    notas_profissional = models.TextField(blank=True, null=True, help_text="Obs. profissional")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    url_videochamada = models.URLField(max_length=500, null=True, blank=True, verbose_name="URL da Videochamada")
    
    def __str__(self):
        data_formatada = timezone.localtime(self.data_hora).strftime("%d/%m/%Y %H:%M") if self.data_hora else "[Data não def]"
        return (f"Consulta de {self.paciente.user.username} com "
                f"{self.profissional.user.username} em {data_formatada} ({self.get_status_display()})")

    class Meta:
        ordering = ['data_hora']
        verbose_name = "Agendamento"
        verbose_name_plural = "Agendamentos"