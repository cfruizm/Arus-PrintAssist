# Construcción y actualización del Vectorstore

## 1. Objetivo

Construir o reconstruir el vectorstore Chroma usado por Arus PrintAssist para recuperación documental.

El vectorstore se construye a partir de PDFs públicos o sanitizados. El flujo general es:

PDFs -> extracción de texto -> chunking -> embeddings -> Chroma persistente

El prototipo usó Chroma como vectorstore persistente y sentence-transformers/all-MiniLM-L6-v2 como modelo de embeddings
