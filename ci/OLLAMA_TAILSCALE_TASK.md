# Pendiente: Ollama por Tailscale

Cuando MIST vuelva al servidor, configurar Ollama corriendo en la laptop Linux `sara`.

- Laptop Linux `sara`: `100.90.208.85`
- En el `.env` del servidor:

```bash
OLLAMA_URL=http://100.90.208.85:11434
```

- En la laptop, Ollama debe escuchar por Tailscale:

```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

- Verificar desde el servidor:

```bash
curl http://100.90.208.85:11434/api/tags
```
