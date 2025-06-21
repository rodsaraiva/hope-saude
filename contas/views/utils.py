from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
import os


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


def ensure_media_directories():
    """
    Garante que as pastas de mídia necessárias existam.
    """
    try:
        from django.conf import settings
        media_root = getattr(settings, 'MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'media'))
        
        # Lista de pastas que precisam existir
        directories = [
            media_root,
            os.path.join(media_root, 'documentos'),
            os.path.join(media_root, 'fotos_perfil'),
            os.path.join(media_root, 'fotos_perfil', 'profissionais'),
            os.path.join(media_root, 'fotos_perfil', 'pacientes'),
        ]
        
        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory, mode=0o755, exist_ok=True)
                print(f"Pasta criada: {directory}")
            else:
                print(f"Pasta já existe: {directory}")
                
        return True
    except Exception as e:
        print(f"Erro ao criar pastas de mídia: {e}")
        # Tentar com permissões mais permissivas
        try:
            for directory in directories:
                os.makedirs(directory, mode=0o777, exist_ok=True)
                print(f"Pasta criada com permissões especiais: {directory}")
            return True
        except Exception as e2:
            print(f"Erro crítico ao criar pastas de mídia: {e2}")
            return False


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