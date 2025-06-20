from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic.edit import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy

from ..forms import RegistroUsuarioForm, PerfilProfissionalForm, PerfilPacienteForm
from ..models import PerfilProfissional, PerfilPaciente
from .utils import get_user_profile


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
            elif tipo_conta == 'PROFISSIONAL':
                PerfilProfissional.objects.create(user=user)  # type: ignore

            messages.success(request, f'Conta criada com sucesso para {user.username}! Você já pode fazer login.')
            return redirect('login')
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = RegistroUsuarioForm()

    return render(request, 'contas/registro.html', {'form': form})


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