from django.contrib import messages
from django.shortcuts import redirect
from django.core.exceptions import ObjectDoesNotExist
from django.views import View
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse
    from ..models import Agendamento


class ProfissionalRequiredMixin:
    """
    Mixin para garantir que apenas profissionais podem acessar a view.
    """
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'perfil_profissional'):
            messages.error(request, "Apenas profissionais podem acessar esta página.")
            return redirect('contas:index')
        return super().dispatch(request, *args, **kwargs)  # type: ignore


class PacienteRequiredMixin:
    """
    Mixin para garantir que apenas pacientes podem acessar a view.
    """
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'perfil_paciente'):
            messages.error(request, "Apenas pacientes podem acessar esta página.")
            return redirect('contas:index')
        return super().dispatch(request, *args, **kwargs)  # type: ignore


class AgendamentoPermissionMixin:
    """
    Mixin para validar permissões em agendamentos.
    """
    def has_agendamento_permission(self, user, agendamento):
        """
        Verifica se o usuário tem permissão para acessar/modificar o agendamento.
        """
        is_paciente = hasattr(user, 'perfil_paciente') and agendamento.paciente == user.perfil_paciente
        is_profissional = hasattr(user, 'perfil_profissional') and agendamento.profissional == user.perfil_profissional
        return is_paciente or is_profissional 