FROM python:3.13-slim

# 1️⃣ Librerías del sistema que WeasyPrint necesita
RUN apt-get update && apt-get install -y \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2️⃣ Carpeta de trabajo
WORKDIR /app

# 3️⃣ Copiar proyecto
COPY . .

# 4️⃣ Instalar dependencias Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 5️⃣ Variables de entorno
ENV PYTHONUNBUFFERED=1

# 6️⃣ Ejecutar Daphne (ASGI)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "djangocrud.asgi:application"]
