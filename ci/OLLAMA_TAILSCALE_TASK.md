# Ollama por Tailscale

MIST corre en `saravault`; Ollama corre en la laptop Linux `sara` para no cargar el servidor.

- Laptop Linux `sara`: `100.90.208.85`
- Servicio de Ollama nativo en la laptop:

```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

- Ver modelos locales:

```bash
ollama list
```

- Descargar modelo inicial si falta:

```bash
ollama pull tinyllama:latest
```

- En el `.env` de MIST en `saravault`:

```bash
OLLAMA_URL=http://100.90.208.85:11434
OLLAMA_FAST_MODEL=tinyllama:latest
OLLAMA_FAST_MODELS=tinyllama:latest
```

- Verificar desde `saravault`:

```bash
curl http://100.90.208.85:11434/api/tags
```

- Si se quiere usar un modelo más grande después:

```bash
ollama pull llama3:latest
```

- Si Ollama no responde, MIST debe seguir funcionando con musica/listas; solo fallan `/chat` y las respuestas IA.
