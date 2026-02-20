# Легковесный образ Python
FROM python:3.11-slim

# Задаем рабочую директорию
WORKDIR /app

# Сначала копируем зависимости (чтобы Docker закэшировал этот слой)
COPY requirements.txt .

# Ставим библиотеки без кэша для экономии места
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код приложения
COPY . .

# Открываем 8000 порт
EXPOSE 8000

# Команда для запуска сервера
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]