# MIST

![MIST logo](docs/assets/mist.png)

Bot de Discord para música y listas guardadas.

## Requisitos

- Python 3.12
- Poetry
- Un bot de Discord configurado

## Ejecutar

```bash
poetry install
poetry run python -m app.bot
```

## Comandos

### Música
- `/join`
- `/leave`
- `/play`
- `/pause`
- `/resume`
- `/stop`
- `/skip`
- `/queue`
- `/repeat`
- `/nowplaying`
- `/shuffle`
- `/search`
- `/play_result`
- `/voice_mist`

### Listas
- `/list_create`
- `/list_add`
- `/list_add_bulk`
- `/list_add_playlist`
- `/list_add_current`
- `/list_delete`
- `/list_show`
- `/list_play`
- `/persist_status`

### IA con Ollama
- `/mist_status`
- `/chat`
- `/mist_logs`

### Moderacion
- `/purge`

Ollama es opcional. Si no responde, el bot debe seguir funcionando para musica y listas.

Variables utiles:

```bash
OLLAMA_URL=http://localhost:11434
OLLAMA_FAST_MODEL=llama3:latest
OLLAMA_FAST_MODELS=llama3:latest,tinyllama:latest,phi:latest
OLLAMA_TIMEOUT=90
OLLAMA_HEALTH_TIMEOUT=5
OLLAMA_NUM_CTX=1024
OLLAMA_NUM_PREDICT=96
OLLAMA_TEMPERATURE=0.3
MIST_DEFAULT_PERSONALITY=mist
MIST_VOICE_ENABLED=true
MIST_VOICE=es-MX-DaliaNeural
```

Para correr Ollama en otra maquina, por ejemplo la PC local, apunta `OLLAMA_URL` a la IP o nombre accesible desde el servidor:

```bash
OLLAMA_URL=http://IP_DE_LA_PC:11434
```
