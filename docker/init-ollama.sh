#!/bin/bash

echo "Checking Ollama model: ${OLLAMA_MODEL:-llama3}..."

# Wait for Ollama to be ready
until curl -s http://ollama:11434/api/tags > /dev/null; do
  echo "Waiting for Ollama service to start..."
  sleep 5
done

# Check if model exists
if curl -s http://ollama:11434/api/tags | grep -q "${OLLAMA_MODEL:-llama3}"; then
  echo "Model ${OLLAMA_MODEL:-llama3} already exists."
else
  echo "Pulling model ${OLLAMA_MODEL:-llama3}..."
  curl -X POST http://ollama:11434/api/pull -d "{\"name\": \"${OLLAMA_MODEL:-llama3}\"}"
fi

echo "Initialization complete."
