# Use uma imagem base oficial do Python. É uma boa prática usar uma versão específica
# para garantir consistência. Escolha uma que corresponda à sua versão de Python.
# 'slim-buster' é uma versão menor e mais segura para produção.
FROM python:3.11-slim-bookworm

# Define o diretório de trabalho dentro do container. Todos os comandos subsequentes
# serão executados a partir deste diretório.
WORKDIR /app

# Define variáveis de ambiente. É útil para configurações específicas do Django.
# Defina DJANGO_SETTINGS_MODULE para o seu arquivo de settings.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE=meuprojeto.settings

# Instala as dependências do sistema operacional necessárias para o Python e alguns pacotes.
# 'gcc' e 'postgresql-client' são comuns para dependências de banco de dados como psycopg2.
# Certifique-se de que sua lista de dependências está atualizada.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo 'requirements.txt' primeiro. Isso aproveita o cache do Docker.
# Se o requirements.txt não mudar, esta camada não será reconstruída.
COPY requirements.txt /app/

# Instala as dependências Python. '--no-cache-dir' e '-U pip' são boas práticas.
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o restante do código da sua aplicação para o diretório de trabalho.
COPY . /app/

# Opcional: Coleta arquivos estáticos (se você estiver servindo-os com Django ou um servidor web).
# Este passo deve vir DEPOIS de copiar todo o código.
# Certifique-se de que collectstatic esteja configurado corretamente no seu settings.py.
# RUN python manage.py collectstatic --noinput

# Expõe a porta em que sua aplicação Django será executada dentro do container.
# Por padrão, Gunicorn (o servidor WSGI recomendado) usa a porta 8000.
EXPOSE 8000

# Comando para iniciar a aplicação.
# Recomendado: Usar Gunicorn como servidor WSGI de produção.
# 'meuprojeto.wsgi:application' deve ser o caminho para o seu arquivo WSGI.
# '-b 0.0.0.0:8000' faz o Gunicorn escutar em todas as interfaces na porta 8000.
CMD ["gunicorn", "--bind", "0.0.0.0:80", "meuprojeto.wsgi:application"]