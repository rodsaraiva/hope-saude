from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic.edit import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib.auth import login
import os
from django.conf import settings

from ..forms import RegistroUsuarioForm, RegistroProfissionalForm, PerfilProfissionalForm, PerfilPacienteForm
from ..models import PerfilProfissional, PerfilPaciente
from .utils import get_user_profile, ensure_media_directories


def index(request):
    """View para a página inicial"""
    return render(request, 'contas/index.html')


def registro(request):
    """View para a página de registro"""
    if request.method == 'POST':
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid():
            user = form.save()
            tipo_conta = form.cleaned_data.get('tipo_conta')

            # Cria o perfil apropriado ligado ao usuário recém-criado
            if tipo_conta == 'PACIENTE':
                PerfilPaciente.objects.create(user=user)  # type: ignore
                messages.success(request, f'Conta criada com sucesso para {user.username}! Você já pode fazer login.')
                return redirect('login')
            elif tipo_conta == 'PROFISSIONAL':
                # Para profissionais, redireciona para página adicional de registro
                PerfilProfissional.objects.create(user=user)  # type: ignore
                # Faz login do usuário para manter a sessão
                login(request, user)
                messages.success(request, f'Conta criada com sucesso! Agora complete seu cadastro profissional.')
                return redirect('contas:registro_profissional')
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = RegistroUsuarioForm()

    return render(request, 'contas/registro.html', {'form': form})


def registro_profissional(request):
    """View para completar o registro de profissionais"""
    if not request.user.is_authenticated:
        messages.error(request, 'Você precisa estar logado para acessar esta página.')
        return redirect('login')
    
    # Verifica se o usuário já tem um perfil profissional
    if not hasattr(request.user, 'perfil_profissional'):
        messages.error(request, 'Acesso negado. Esta página é apenas para profissionais.')
        return redirect('contas:meu_perfil')
    
    # Garantir que as pastas de mídia existam
    ensure_media_directories()
    
    if request.method == 'POST':
        form = RegistroProfissionalForm(request.POST, request.FILES, instance=request.user.perfil_profissional)
        if form.is_valid():
            try:
                # Verificar se há arquivo sendo enviado
                if 'documento_registro' in request.FILES:
                    print(f"Arquivo recebido: {request.FILES['documento_registro'].name}")
                    
                form.save()
                messages.success(request, 'Cadastro profissional completado com sucesso!')
                return redirect('contas:meu_perfil')
            except Exception as e:
                print(f"Erro ao salvar: {e}")
                messages.error(request, f'Erro ao salvar o cadastro: {str(e)}')
        else:
            print(f"Formulário inválido: {form.errors}")
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = RegistroProfissionalForm(instance=request.user.perfil_profissional)

    return render(request, 'contas/registro_profissional.html', {'form': form})


@login_required
def meu_perfil(request):
    """View para a página 'Meu Perfil' do usuário logado"""
    user = request.user
    perfil = get_user_profile(user)
    
    contexto = {
        'user': user,
        'perfil': perfil
    }
    
    if perfil is None:
        contexto['erro_perfil'] = "Não foi possível encontrar um perfil associado à sua conta."

    return render(request, 'contas/meu_perfil.html', contexto)


class EditarPerfilView(LoginRequiredMixin, UpdateView):
    """View para editar o perfil do usuário"""
    template_name = 'contas/editar_perfil.html'
    success_url = reverse_lazy('contas:meu_perfil')

    def get_object(self, queryset=None):
        """
        Retorna o objeto de perfil (Profissional ou Paciente)
        que o usuário está autorizado a editar.
        """
        if hasattr(self.request.user, 'perfil_profissional'):
            return self.request.user.perfil_profissional
        elif hasattr(self.request.user, 'perfil_paciente'):
            return self.request.user.perfil_paciente
        return None

    def get_form_class(self):
        """
        Retorna a classe do formulário apropriada baseada no tipo de perfil.
        """
        if hasattr(self.request.user, 'perfil_profissional'):
            return PerfilProfissionalForm
        elif hasattr(self.request.user, 'perfil_paciente'):
            return PerfilPacienteForm
        return None

    def get(self, request, *args, **kwargs):
        # Sobrescrevemos o get para tratar o caso de usuário sem perfil
        self.object = self.get_object()
        if self.object is None:
            messages.error(self.request, "Não foi possível encontrar um perfil para editar.")
            return redirect('contas:meu_perfil')
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        # Adiciona a mensagem de sucesso antes de redirecionar
        messages.success(self.request, "Perfil atualizado com sucesso!")
        return super().form_valid(form)

    def form_invalid(self, form):
        # Adiciona uma mensagem de erro genérica
        messages.error(self.request, "Erro ao atualizar o perfil. Verifique os campos.")
        return super().form_invalid(form) 