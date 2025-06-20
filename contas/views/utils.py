from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse


def get_user_profile(user):
    """
    Retorna o perfil do usuário (paciente ou profissional).
    """
    try:
        return user.perfil_paciente
    except ObjectDoesNotExist:
        try:
            return user.perfil_profissional
        except ObjectDoesNotExist:
            return None


def validate_agendamento_permission(user, agendamento):
    """
    Valida se o usuário tem permissão para acessar o agendamento.
    """
    is_paciente = hasattr(user, 'perfil_paciente') and agendamento.paciente == user.perfil_paciente
    is_profissional = hasattr(user, 'perfil_profissional') and agendamento.profissional == user.perfil_profissional
    return is_paciente or is_profissional


def api_success_response(data=None, status_code=200):
    """
    Gera uma resposta JSON padronizada para sucesso.
    """
    response = {'status': 'success'}
    if data is not None:
        response['data'] = data
    return JsonResponse(response, status=status_code)


def api_error_response(message, error_code=None, status_code=400):
    """
    Gera uma resposta JSON padronizada para erro.
    """
    response = {'status': 'error', 'message': message}
    if error_code is not None:
        response['error_code'] = error_code
    return JsonResponse(response, status=status_code) 