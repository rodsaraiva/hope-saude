# --- CONFIGURAÇÕES DE MÍDIA ROBUSTAS ---
# URL base para servir os arquivos de mídia enviados pelos usuários
MEDIA_URL = '/media/'

def get_media_root():
    """
    Determina o melhor diretório para armazenar arquivos de mídia.
    Prioriza configurações seguras e persistentes.
    """
    
    # 1. Primeira opção: variável de ambiente (mais flexível)
    env_media = os.environ.get('MEDIA_ROOT')
    if env_media:
        print(f"📁 Usando MEDIA_ROOT da variável de ambiente: {env_media}")
        return env_media
    
    # 2. Segunda opção: diretório local do projeto (desenvolvimento)
    if DEBUG:
        local_media = os.path.join(BASE_DIR, 'media')
        print(f"📁 Desenvolvimento: usando diretório local: {local_media}")
        return local_media
    
    # 3. Terceira opção: diretórios comuns em produção
    production_options = [
        '/workspace/media',  # EasyPanel/containers
        '/app/media',        # Docker containers
        '/var/www/media',    # Servidores web tradicionais
        os.path.join(BASE_DIR, 'media'),  # Fallback para o projeto
    ]
    
    for media_dir in production_options:
        try:
            # Tenta criar o diretório se não existir
            os.makedirs(media_dir, exist_ok=True)
            
            # Testa se consegue escrever no diretório
            test_file = os.path.join(media_dir, '.test_write')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            
            print(f"✅ Produção: usando diretório {media_dir}")
            return media_dir
            
        except (PermissionError, OSError) as e:
            print(f"❌ Não foi possível usar {media_dir}: {e}")
            continue
    
    # 4. Se nenhum funcionar, levanta erro com instruções claras
    error_msg = """
🚨 ERRO: Não foi possível configurar um diretório de mídia válido!

Para resolver este problema, você pode:

1. Configurar a variável de ambiente MEDIA_ROOT:
   export MEDIA_ROOT=/caminho/para/diretorio/com/permissao

2. Configurar permissões no diretório /workspace/media:
   chmod 755 /workspace/media
   chown www-data:www-data /workspace/media

3. Usar um storage externo (recomendado para produção):
   - Amazon S3
   - Google Cloud Storage
   - Azure Blob Storage

4. Configurar um volume persistente se estiver usando containers.

Diretórios testados: {}
""".format(', '.join(production_options))
    
    raise ImproperlyConfigured(error_msg)

# Define o diretório de mídia
try:
    MEDIA_ROOT = get_media_root()
except ImproperlyConfigured as e:
    print(e)
    # Em caso de erro, usa o diretório local como último recurso
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
    print(f"⚠️ Usando diretório local como fallback: {MEDIA_ROOT}")

# Configuração de storage para arquivos de mídia
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# --- FIM DAS CONFIGURAÇÕES DE MÍDIA --- 