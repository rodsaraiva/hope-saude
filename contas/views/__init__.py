# contas/views/__init__.py

# Importações das views de autenticação
from .auth import (
    index,
    registro,
    meu_perfil,
    EditarPerfilView,
)

# Importações das views de profissionais
from .profissionais import (
    lista_profissionais,
    perfil_profissional_detail,
)

# Importações das views de agendamentos
from .agendamentos import (
    meus_agendamentos,
    cancelar_agendamento,
    criar_agendamento,
    confirmar_agendamento,
    marcar_realizado,
    sala_videochamada,
)

# Importações das views de calendário
from .calendario import (
    calendario_profissional,
)

# Importações das views de pagamento
from .pagamento import (
    processar_pagamento,
    stripe_webhook,
)

# Importações das views de API
from .api import (
    api_criar_disp_avulsa,
    api_editar_regra_disponibilidade,
    api_excluir_regras_disponibilidade_lista,
    api_obter_ou_criar_sala_video,
    api_submeter_avaliacao,
)

# Importações dos mixins e utils
from .mixins import (
    ProfissionalRequiredMixin,
    PacienteRequiredMixin,
    AgendamentoPermissionMixin,
)

from .utils import (
    get_user_profile,
    validate_agendamento_permission,
    api_success_response,
    api_error_response,
)

__all__ = [
    # Views de autenticação
    'index',
    'registro',
    'meu_perfil',
    'EditarPerfilView',
    
    # Views de profissionais
    'lista_profissionais',
    'perfil_profissional_detail',
    
    # Views de agendamentos
    'meus_agendamentos',
    'cancelar_agendamento',
    'criar_agendamento',
    'confirmar_agendamento',
    'marcar_realizado',
    'sala_videochamada',
    
    # Views de calendário
    'calendario_profissional',
    
    # Views de pagamento
    'processar_pagamento',
    'stripe_webhook',
    
    # Views de API
    'api_criar_disp_avulsa',
    'api_editar_regra_disponibilidade',
    'api_excluir_regras_disponibilidade_lista',
    'api_obter_ou_criar_sala_video',
    'api_submeter_avaliacao',
    
    # Mixins e utils
    'ProfissionalRequiredMixin',
    'PacienteRequiredMixin',
    'AgendamentoPermissionMixin',
    'get_user_profile',
    'validate_agendamento_permission',
    'api_success_response',
    'api_error_response',
] 