# contas/models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models import Avg
from datetime import timedelta

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
    valor_consulta = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        help_text="Valor da consulta em R$. Deixe em branco se for gratuito ou a combinar."
    )
    foto_perfil = models.ImageField(
        upload_to='fotos_perfil/profissionais/', # Onde as fotos serão salvas
        null=True, 
        blank=True,
        verbose_name="Foto de Perfil"
    )
        # --- PROPRIEDADES NOVAS ADICIONADAS ---
    @property
    def nota_media(self):
        """
        Calcula e retorna a média das notas das avaliações recebidas.
        """
        # Usamos o related_name 'avaliacoes_recebidas' que definimos no modelo Avaliacao
        # e a função de agregação Avg do Django para calcular a média diretamente no banco de dados.
        media = self.avaliacoes_recebidas.aggregate(Avg('nota')).get('nota__avg')
        
        # Se o profissional ainda não tem avaliações, a média será None. Retornamos 0 nesse caso.
        if media is None:
            return 0
        return round(media, 1) # Arredonda para uma casa decimal

    @property
    def total_avaliacoes(self):
        """
        Retorna o número total de avaliações recebidas.
        """
        return self.avaliacoes_recebidas.count()

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
    foto_perfil = models.ImageField(
        upload_to='fotos_perfil/pacientes/', # Subpasta diferente para organização
        null=True, 
        blank=True,
        verbose_name="Foto de Perfil"
    )

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
    
    # --- NOVAS OPÇÕES E CAMPOS ADICIONADOS ---
    STATUS_PAGAMENTO_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('PAGO', 'Pago'),
        ('FALHOU', 'Falhou'),
        ('REEMBOLSADO', 'Reembolsado'),
    ]

    paciente = models.ForeignKey(PerfilPaciente, on_delete=models.CASCADE, related_name='agendamentos_como_paciente')
    profissional = models.ForeignKey(
        PerfilProfissional,
        on_delete=models.CASCADE,
        related_name='agendamentos'
    )
    data_hora = models.DateTimeField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDENTE')
    
    # --- NOVOS CAMPOS ADICIONADOS ---
    status_pagamento = models.CharField(
        max_length=15,
        choices=STATUS_PAGAMENTO_CHOICES,
        default='PENDENTE'
    )
    pagamento_id = models.CharField(
        max_length=255, null=True, blank=True, unique=True,
        help_text="ID da transação no gateway de pagamento (ex: Stripe Payment Intent ID)"
    )
    
    notas_paciente = models.TextField(blank=True, null=True, help_text="Obs. paciente")
    notas_profissional = models.TextField(blank=True, null=True, help_text="Obs. profissional")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    url_videochamada = models.URLField(max_length=500, null=True, blank=True, verbose_name="URL da Videochamada")
    
    consulta_duracao = models.ForeignKey('ConsultaProfissionalDuracao', on_delete=models.PROTECT, null=True, blank=True, related_name='agendamentos', help_text='Duração e preço escolhidos para esta consulta')
    
    def __str__(self):
        data_formatada = timezone.localtime(self.data_hora).strftime("%d/%m/%Y %H:%M") if self.data_hora else "[Data não def]"
        return (f"Consulta de {self.paciente.user.username} com "
                f"{self.profissional.user.username} em {data_formatada} ({self.get_status_display()})")

    # O método obter_ou_criar_url_sala_com_token() que adicionamos anteriormente permanece aqui
    def obter_ou_criar_url_sala_com_token(self, user, is_owner):
        """
        Encapsula a lógica de interação com a API Daily.co para obter/criar sala e gerar token.
        Levanta exceções em caso de erro.
        """
        from django.conf import settings
        import requests

        if not settings.DAILY_CO_API_KEY:
            print("[API VÍDEO ERRO] Chave de API do Daily.co não configurada.")
            raise Exception('Serviço de vídeo indisponível (config).')

        url_base_da_sala = self.url_videochamada
        nome_da_sala_daily = None

        if not url_base_da_sala:
            print(f"[API VÍDEO] Criando nova sala para agendamento {self.id}...")
            headers_room = {'Authorization': f'Bearer {settings.DAILY_CO_API_KEY}', 'Content-Type': 'application/json'}
            nbf_unix = int((self.data_hora - timedelta(minutes=30)).timestamp())
            exp_unix = int((self.data_hora + timedelta(hours=1, minutes=30)).timestamp())
            
            room_payload = {
                'privacy': 'private',
                'properties': {
                    'nbf': nbf_unix, 'exp': exp_unix, 'max_participants': 2, 'eject_at_room_exp': True,
                    'enable_prejoin_ui': True, 'start_audio_off': False, 'start_video_off': False,
                    'enable_chat': False, 'enable_screenshare': False, 'enable_people_ui': False,
                }
            }
            response_room = requests.post('https://api.daily.co/v1/rooms', headers=headers_room, json=room_payload)
            response_room.raise_for_status() # Levanta HTTPError para respostas 4xx/5xx
            
            room_data = response_room.json()
            url_base_da_sala = room_data.get('url')
            if not url_base_da_sala:
                raise Exception("Não foi possível obter URL da sala da API Daily.co.")
            
            self.url_videochamada = url_base_da_sala
            self.save()
            print(f"[API VÍDEO] Sala criada: {url_base_da_sala}")

        partes_url = url_base_da_sala.strip('/').split('/')
        nome_da_sala_daily = partes_url[-1] if partes_url else None
        
        if not nome_da_sala_daily:
            raise Exception('Configuração da sala incompleta para gerar token de acesso.')

        print(f"[API VÍDEO] Gerando token para sala '{nome_da_sala_daily}'...")
        headers_token = {'Authorization': f'Bearer {settings.DAILY_CO_API_KEY}', 'Content-Type': 'application/json'}
        token_exp_unix = int((timezone.now() + timedelta(hours=1, minutes=15)).timestamp())
        
        token_payload = {
            'properties': {
                'room_name': nome_da_sala_daily,
                'user_name': user.username,
                'is_owner': is_owner,
                'exp': token_exp_unix,
                'start_audio_off': True,
                'start_video_off': True,
            }
        }
        response_token = requests.post('https://api.daily.co/v1/meeting-tokens', headers=headers_token, json=token_payload)
        response_token.raise_for_status()
        
        token_data = response_token.json()
        meeting_token = token_data.get('token')
        if not meeting_token:
            raise Exception("Token não retornado pela API Daily.co.")

        return f"{url_base_da_sala}?t={meeting_token}"
    
    class Meta:
        ordering = ['data_hora']
        verbose_name = "Agendamento"
        verbose_name_plural = "Agendamentos"


# --- NOVO MODELO ADICIONADO ---
class Avaliacao(models.Model):
    # Relaciona a avaliação a um único agendamento específico.
    # OneToOneField garante que cada agendamento só pode ser avaliado uma vez.
    agendamento = models.OneToOneField(
        Agendamento, 
        on_delete=models.CASCADE, 
        related_name='avaliacao'
    )
    # Quem está fazendo a avaliação (o paciente)
    avaliador = models.ForeignKey(
        PerfilPaciente, 
        on_delete=models.CASCADE, 
        related_name='avaliacoes_feitas'
    )
    # Quem está sendo avaliado (o profissional)
    avaliado = models.ForeignKey(
        PerfilProfissional, 
        on_delete=models.CASCADE, 
        related_name='avaliacoes_recebidas'
    )
    # A nota em estrelas, de 1 a 5
    nota = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    # O comentário textual (opcional)
    comentario = models.TextField(blank=True, null=True)
    
    # Data em que a avaliação foi criada
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_criacao']
        # Garante que um paciente só pode avaliar um profissional uma vez por agendamento (já coberto pelo OneToOneField, mas bom para clareza)
        unique_together = ('agendamento', 'avaliador', 'avaliado')
        verbose_name = "Avaliação"
        verbose_name_plural = "Avaliações"

    def __str__(self):
        return f'Avaliação de {self.avaliador.user.username} para {self.avaliado.user.username} (Nota: {self.nota})'

class ConsultaProfissionalDuracao(models.Model):
    DURACAO_CHOICES = [
        (30, '30 minutos'),
        (45, '45 minutos'),
        (60, '1 hora'),
        (75, '1h15min'),
        (90, '1h30min'),
    ]
    profissional = models.ForeignKey(PerfilProfissional, on_delete=models.CASCADE, related_name='consultas_duracao')
    duracao_minutos = models.PositiveIntegerField(choices=DURACAO_CHOICES)
    preco = models.DecimalField(max_digits=7, decimal_places=2, help_text='Preço para esta duração (R$)')

    class Meta:
        unique_together = ('profissional', 'duracao_minutos')
        verbose_name = 'Duração e Preço de Consulta'
        verbose_name_plural = 'Durações e Preços de Consulta'

    def __str__(self):
        return f"{self.profissional} - {self.get_duracao_minutos_display()} - R$ {self.preco}"
