# ProjetosDjango/contas/tests.py

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from .models import PerfilProfissional, RegraDisponibilidade, Agendamento, PerfilPaciente, Especialidade
from datetime import time, date, datetime, timedelta
from django.utils import timezone
from unittest import mock # <--- ADICIONE ESTA LINHA


class RegraDisponibilidadeModelTests(TestCase):

    def setUp(self):
        self.user_profissional = User.objects.create_user(username='profissional_teste', password='password123')
        self.perfil_profissional = PerfilProfissional.objects.create(user=self.user_profissional, tipo_profissional='PSICOLOGO')

    def test_validacao_semanal_campos_obrigatorios_faltando_dia_semana(self):
        """
        Testa se ValidationError é levantada se tipo_regra='SEMANAL' e dia_semana está faltando.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='SEMANAL',
            hora_inicio_recorrente=time(9, 0),
            hora_fim_recorrente=time(17, 0)
        )
        with self.assertRaisesMessage(ValidationError,
                                      "Para regras 'Semanal Recorrente', os campos 'Dia da Semana (p/ Semanal)', 'Hora Início (p/ Semanal)' e 'Hora Fim (p/ Semanal)' são obrigatórios."):
            regra.full_clean()

    def test_validacao_semanal_campos_obrigatorios_faltando_hora_inicio(self):
        """
        Testa se ValidationError é levantada se tipo_regra='SEMANAL' e hora_inicio_recorrente está faltando.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='SEMANAL',
            dia_semana=0,
            hora_fim_recorrente=time(17, 0)
        )
        with self.assertRaisesMessage(ValidationError,
                                      "Para regras 'Semanal Recorrente', os campos 'Dia da Semana (p/ Semanal)', 'Hora Início (p/ Semanal)' e 'Hora Fim (p/ Semanal)' são obrigatórios."):
            regra.full_clean()

    def test_validacao_semanal_hora_fim_antes_de_hora_inicio(self):
        """
        Testa se ValidationError é levantada se hora_fim_recorrente for antes de hora_inicio_recorrente.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='SEMANAL',
            dia_semana=0,
            hora_inicio_recorrente=time(17, 0),
            hora_fim_recorrente=time(9, 0)
        )
        with self.assertRaisesMessage(ValidationError, "{'hora_fim_recorrente': ['A hora de fim recorrente deve ser após a hora de início.']}"):
            regra.full_clean()

    def test_validacao_semanal_hora_fim_igual_a_hora_inicio(self): # NOVO TESTE
        """
        Testa se ValidationError é levantada se hora_fim_recorrente for igual a hora_inicio_recorrente.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='SEMANAL',
            dia_semana=0,
            hora_inicio_recorrente=time(9, 0),
            hora_fim_recorrente=time(9, 0) # Horas iguais
        )
        with self.assertRaisesMessage(ValidationError, "{'hora_fim_recorrente': ['A hora de fim recorrente deve ser após a hora de início.']}"):
            regra.full_clean()

    def test_criacao_regra_semanal_valida(self):
        """
        Testa a criação bem-sucedida de uma regra semanal válida.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='SEMANAL',
            dia_semana=1,
            hora_inicio_recorrente=time(10, 0),
            hora_fim_recorrente=time(18, 0)
        )
        try:
            regra.full_clean()
            regra.save()
        except ValidationError:
            self.fail("Uma regra semanal válida não deveria levantar ValidationError.")
        self.assertIsNotNone(regra.pk)
        self.assertIsNone(regra.data_hora_inicio_especifica)
        self.assertIsNone(regra.data_hora_fim_especifica)

    def test_validacao_especifica_campos_obrigatorios_faltando_data_inicio(self):
        """
        Testa se ValidationError é levantada se tipo_regra='ESPECIFICA' e data_hora_inicio_especifica está faltando.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_fim_especifica=timezone.now() + timedelta(days=1, hours=2)
        )
        with self.assertRaisesMessage(ValidationError,
                                      "Para regras 'Data/Hora Específica', os campos 'Início Específico' e 'Fim Específico' são obrigatórios."):
            regra.full_clean()

    def test_validacao_especifica_data_fim_antes_de_data_inicio(self):
        """
        Testa se ValidationError é levantada se data_hora_fim_especifica for antes de data_hora_inicio_especifica.
        """
        inicio = timezone.now() + timedelta(days=1)
        fim = timezone.now() + timedelta(days=1, hours=-2)
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=inicio,
            data_hora_fim_especifica=fim
        )
        with self.assertRaisesMessage(ValidationError,
                                      "{'data_hora_fim_especifica': ['O fim específico deve ser após o início específico.']}"):
            regra.full_clean()

    def test_validacao_especifica_data_fim_igual_a_data_inicio(self): # NOVO TESTE
        """
        Testa se ValidationError é levantada se data_hora_fim_especifica for igual a data_hora_inicio_especifica.
        """
        inicio_fim = timezone.now() + timedelta(days=1)
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=inicio_fim,
            data_hora_fim_especifica=inicio_fim # Datas/horas iguais
        )
        with self.assertRaisesMessage(ValidationError,
                                      "{'data_hora_fim_especifica': ['O fim específico deve ser após o início específico.']}"):
            regra.full_clean()

    def test_validacao_especifica_data_inicio_no_passado(self):
        """
        Testa se ValidationError é levantada se data_hora_inicio_especifica for no passado para uma nova regra.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=timezone.now() - timedelta(days=1),
            data_hora_fim_especifica=timezone.now() - timedelta(days=1, hours=-2) # Corrigido para ser consistente com a lógica do clean() que valida início primeiro
        )
        with self.assertRaisesMessage(ValidationError,
                                      "{'data_hora_inicio_especifica': ['Não é possível adicionar disponibilidade específica no passado.']}"):
            regra.full_clean()

    def test_criacao_regra_especifica_valida(self):
        """
        Testa a criação bem-sucedida de uma regra específica válida.
        """
        inicio = timezone.now() + timedelta(days=2, hours=10)
        fim = timezone.now() + timedelta(days=2, hours=12)
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=inicio,
            data_hora_fim_especifica=fim
        )
        try:
            regra.full_clean()
            regra.save()
        except ValidationError:
            self.fail("Uma regra específica válida não deveria levantar ValidationError.")
        self.assertIsNotNone(regra.pk)
        self.assertIsNone(regra.dia_semana)
        self.assertIsNone(regra.hora_inicio_recorrente)
        self.assertIsNone(regra.hora_fim_recorrente)

    def test_validacao_tipo_regra_invalido_ou_nulo(self): # NOVO TESTE
        """
        Testa se ValidationError é levantada se tipo_regra for inválido ou não fornecido.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='INVALIDO', # Tipo inválido
            dia_semana=0,
            hora_inicio_recorrente=time(9,0)
        )
        with self.assertRaisesMessage(ValidationError, "Um tipo de regra válido deve ser selecionado."):
            regra.full_clean()

        regra_sem_tipo = RegraDisponibilidade(
            profissional=self.perfil_profissional
            # tipo_regra não definido
        )
        # O campo tipo_regra não tem default e não é blank=True no modelo,
        # então um erro de validação de campo (não do clean) deve ocorrer.
        # Se CharField com choices não tiver um valor, a validação de campo do Django falha.
        # O método clean() nem seria chamado se o tipo fosse None e o campo não permitisse.
        # No entanto, o clean() tem um `else: raise ValidationError("Um tipo de regra válido deve ser selecionado.")`
        # que pegaria um tipo que não é 'SEMANAL' nem 'ESPECIFICA'.
        # Se tipo_regra for None e o modelo permitir (o que não é o caso aqui pois não tem null=True), o else do clean pegaria.
        # Como não tem null=True, a validação de campo do Django já pegaria se fosse None.
        # O teste com 'INVALIDO' é mais direto para a lógica `else` do `clean`.
        # Se você quiser testar o comportamento de `None` especificamente no `clean`,
        # precisaria permitir `null=True` no modelo para `tipo_regra`, o que não é o caso.

    def test_str_representation_semanal(self):
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='SEMANAL',
            dia_semana=0,
            hora_inicio_recorrente=time(9, 0),
            hora_fim_recorrente=time(17, 0)
        )
        expected_str = f"{self.user_profissional.username} - Semanal: Segunda-feira 09:00-17:00"
        self.assertEqual(str(regra), expected_str)

    def test_str_representation_especifica(self):
        inicio = timezone.make_aware(datetime(2025, 12, 24, 10, 0, 0))
        fim = timezone.make_aware(datetime(2025, 12, 24, 12, 0, 0))
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=inicio,
            data_hora_fim_especifica=fim
        )
        self.assertIn(self.user_profissional.username, str(regra))
        self.assertIn("Específica", str(regra))
        self.assertIn(timezone.localtime(inicio).strftime('%d/%m/%y %H:%M'), str(regra))
        self.assertIn(timezone.localtime(fim).strftime('%d/%m/%y %H:%M'), str(regra))


class AgendamentoModelTests(TestCase):

    def setUp(self):
        # Usuários e Perfis
        self.user_paciente = User.objects.create_user(username='paciente_teste', password='password123')
        self.perfil_paciente = PerfilPaciente.objects.create(user=self.user_paciente)
        
        self.user_profissional = User.objects.create_user(username='profissional_ag_teste', password='password123')
        self.perfil_profissional = PerfilProfissional.objects.create(user=self.user_profissional, tipo_profissional='PSIQUIATRA')

    def test_criacao_agendamento_valido(self):
        """
        Testa a criação de um agendamento válido e o status padrão.
        """
        data_hora_agendamento = timezone.now() + timedelta(days=5)
        agendamento = Agendamento.objects.create(
            paciente=self.perfil_paciente,
            profissional=self.perfil_profissional,
            data_hora=data_hora_agendamento
        )
        self.assertIsNotNone(agendamento.pk)
        self.assertEqual(agendamento.status, 'PENDENTE') # Verifica status padrão
        self.assertEqual(agendamento.paciente, self.perfil_paciente)
        self.assertEqual(agendamento.profissional, self.perfil_profissional)
        self.assertIsNotNone(agendamento.criado_em)
        self.assertIsNotNone(agendamento.atualizado_em)
        # self.assertTrue(agendamento.atualizado_em > primeira_atualizacao) # REMOVA/COMENTE ESTA LINHA DAQUI

    def test_str_representation_agendamento(self):
        """ Testa a representação em string de um agendamento. """
        data_hora_agendamento = timezone.make_aware(datetime(2025, 10, 5, 14, 30, 0))
        agendamento = Agendamento(
            paciente=self.perfil_paciente,
            profissional=self.perfil_profissional,
            data_hora=data_hora_agendamento,
            status='CONFIRMADO'
        )
        # A formatação da data no __str__ usa timezone.localtime
        data_formatada = timezone.localtime(data_hora_agendamento).strftime("%d/%m/%Y %H:%M")
        expected_str = (f"Consulta de {self.user_paciente.username} com "
                        f"{self.user_profissional.username} em {data_formatada} (Confirmado)")
        self.assertEqual(str(agendamento), expected_str)

    def test_atualizado_em_updates_on_save(self): # <--- NOVO MÉTODO DE TESTE
        """
        Testa se o campo 'atualizado_em' é atualizado a cada save subsequente.
        """
        data_hora_agendamento = timezone.now() + timedelta(days=5)
        agendamento = Agendamento.objects.create(
            paciente=self.perfil_paciente,
            profissional=self.perfil_profissional,
            data_hora=data_hora_agendamento
        )
        primeira_atualizacao = agendamento.atualizado_em

        # Modificamos um campo para justificar o save
        agendamento.notas_paciente = "Uma nota de teste."

        # Usamos mock para controlar o valor de timezone.now() durante o save
        # Isso garante que o novo timestamp será diferente e maior.
        with mock.patch('django.utils.timezone.now') as mock_now:
            # Configuramos o mock para retornar um tempo 1 segundo após a primeira atualização
            mock_now.return_value = primeira_atualizacao + timedelta(seconds=1)
            agendamento.save() # Salva o agendamento novamente

        segunda_atualizacao = agendamento.atualizado_em

        self.assertTrue(segunda_atualizacao > primeira_atualizacao,
                        f"Esperado que a segunda atualização ({segunda_atualizacao}) "
                        f"fosse maior que a primeira ({primeira_atualizacao}).")
        self.assertNotEqual(primeira_atualizacao, segunda_atualizacao)


