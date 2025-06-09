# contas/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import (
    PerfilProfissional, PerfilPaciente, Especialidade, Agendamento,
    RegraDisponibilidade # Modelos existentes e o novo
    # REMOVA Disponibilidade e DisponibilidadeAvulsa dos imports
)

# --- Formulários de Usuário e Perfil ---
TIPO_CONTA_CHOICES = [
    ('PACIENTE', 'Sou Paciente'),
    ('PROFISSIONAL', 'Sou Profissional'),
]

class RegistroUsuarioForm(UserCreationForm):
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'seuemail@exemplo.com'})
    )
    first_name = forms.CharField(
        label="Primeiro Nome",
        max_length=30,
        required=False, # Tornando opcional
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu nome'})
    )
    last_name = forms.CharField(
        label="Sobrenome",
        max_length=150,
        required=False, # Tornando opcional
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu sobrenome'})
    )
    tipo_conta = forms.ChoiceField(
        choices=TIPO_CONTA_CHOICES,
        required=True,
        label="Tipo de Conta",
        widget=forms.RadioSelect # Para melhor estilização com Bootstrap, renderizar manualmente no template
    )

    class Meta(UserCreationForm.Meta):
        model = User
        # Mantém os campos padrão (username, password1, password2) e adiciona os nossos
        fields = UserCreationForm.Meta.fields + ('email', 'first_name', 'last_name', 'tipo_conta')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Adiciona classe 'form-control' aos campos herdados
        for field_name in ['username', 'password1', 'password2']:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({'class': 'form-control'})
                self.fields[field_name].help_text = None # Remove help_text padrão se desejar

        # Ajusta labels se necessário
        if 'username' in self.fields:
            self.fields['username'].label = "Nome de Usuário"
            self.fields['username'].widget.attrs.update({'placeholder': 'Crie um nome de usuário'})
        if 'password1' in self.fields:
            self.fields['password1'].label = "Senha"
            self.fields['password1'].widget.attrs.update({'placeholder': 'Crie uma senha'})
        if 'password2' in self.fields:
            self.fields['password2'].label = "Confirmação de Senha"
            self.fields['password2'].widget.attrs.update({'placeholder': 'Confirme sua senha'})


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update(
            {'class': 'form-control mb-2', 'placeholder': 'Nome de Usuário ou E-mail'}
        )
        self.fields['username'].label = "Nome de Usuário ou E-mail"
        self.fields['password'].widget.attrs.update(
            {'class': 'form-control', 'placeholder': 'Senha'}
        )
        self.fields['password'].label = "Senha"


class PerfilProfissionalForm(forms.ModelForm):
    class Meta:
        model = PerfilProfissional
        fields = [
            'tipo_profissional', 'numero_registro', 'especialidades',
            'bio', 'telefone_contato', 'endereco_consultorio', 'anos_experiencia',
        ]
        widgets = {
            'tipo_profissional': forms.Select(attrs={'class': 'form-select'}),
            'numero_registro': forms.TextInput(attrs={'class': 'form-control'}),
            'especialidades': forms.CheckboxSelectMultiple, # Para ManyToManyField
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'telefone_contato': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(XX) XXXXX-XXXX'}),
            'endereco_consultorio': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'anos_experiencia': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }
        labels = { # Adicionando labels para melhor clareza
            'tipo_profissional': 'Tipo de Profissional',
            'numero_registro': 'Número de Registro (CRP/CRM)',
            'especialidades': 'Especialidades Atendidas',
            'bio': 'Sobre Mim / Abordagem Terapêutica',
            'telefone_contato': 'Telefone de Contato (Opcional)',
            'endereco_consultorio': 'Endereço do Consultório (Opcional)',
            'anos_experiencia': 'Anos de Experiência Clínica (Opcional)',
        }


class PerfilPacienteForm(forms.ModelForm):
    class Meta:
        model = PerfilPaciente
        fields = [
            'data_nascimento', 'telefone_contato', 'endereco', 'contato_emergencia',
        ]
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'telefone_contato': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(XX) XXXXX-XXXX'}),
            'endereco': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'contato_emergencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome e telefone'}),
        }
        labels = { # Adicionando labels
            'data_nascimento': 'Data de Nascimento',
            'telefone_contato': 'Telefone de Contato',
            'endereco': 'Endereço (Opcional)',
            'contato_emergencia': 'Contato de Emergência (Nome e Telefone - Opcional)',
        }


class RegraDisponibilidadeForm(forms.ModelForm):
    class Meta:
        model = RegraDisponibilidade
        fields = [
            'tipo_regra',
            'dia_semana', 'hora_inicio_recorrente', 'hora_fim_recorrente',
            'data_hora_inicio_especifica', 'data_hora_fim_especifica'
        ]
        widgets = {
            'tipo_regra': forms.RadioSelect(attrs={'class': 'form-check-input-stacked'}), # Classe para ajudar no JS
            'dia_semana': forms.Select(attrs={'class': 'form-select form-control-sm'}),
            'hora_inicio_recorrente': forms.TimeInput(
                format='%H:%M', attrs={'type': 'time', 'class': 'form-control form-control-sm'}
            ),
            'hora_fim_recorrente': forms.TimeInput(
                format='%H:%M', attrs={'type': 'time', 'class': 'form-control form-control-sm'}
            ),
            'data_hora_inicio_especifica': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'}
            ),
            'data_hora_fim_especifica': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'}
            ),
        }
        labels = {
            'tipo_regra': 'Qual tipo de disponibilidade você quer adicionar?',
            'dia_semana': 'Dia da Semana',
            'hora_inicio_recorrente': 'Das',
            'hora_fim_recorrente': 'Até',
            'data_hora_inicio_especifica': 'De (Data e Hora)',
            'data_hora_fim_especifica': 'Até (Data e Hora)',
        }
        help_texts = { # Adicionando help_texts para clareza
            'tipo_regra': 'Escolha "Semanal Recorrente" para horários que se repetem toda semana, ou "Data/Hora Específica" para um dia e período únicos.',
            'dia_semana': 'Se aplica apenas se o tipo for "Semanal Recorrente".',
            'hora_inicio_recorrente': 'Formato HH:MM. Se aplica apenas se o tipo for "Semanal Recorrente".',
            'hora_fim_recorrente': 'Formato HH:MM. Se aplica apenas se o tipo for "Semanal Recorrente".',
            'data_hora_inicio_especifica': 'Se aplica apenas se o tipo for "Data/Hora Específica".',
            'data_hora_fim_especifica': 'Se aplica apenas se o tipo for "Data/Hora Específica".',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Inicialmente, podemos deixar todos os campos visíveis,
        # o JavaScript no template cuidará de mostrar/ocultar.
        # Ou, se preferir, pode tentar ocultar aqui baseado na instância inicial (para edição),
        # mas a lógica JS é geralmente mais flexível para o usuário trocando o tipo_regra.

        # Opcional: Definir campos não-recorrentes como não-obrigatórios no formulário
        # A validação final será feita pelo clean() do modelo baseado no tipo_regra
        self.fields['dia_semana'].required = False
        self.fields['hora_inicio_recorrente'].required = False
        self.fields['hora_fim_recorrente'].required = False
        self.fields['data_hora_inicio_especifica'].required = False
        self.fields['data_hora_fim_especifica'].required = False

    # O método clean do ModelForm chamará automaticamente o clean do modelo RegraDisponibilidade,
    # que já tem a lógica para validar quais campos são obrigatórios baseado no tipo_regra.