# Flight Booking: gRPC + Redis

Система бронирования авиабилетов на основе микросервисной архитектуры.
Реализовано с использованием FastAPI, gRPC, PostgreSQL, Redis.

## Запуск

1. Сгенерируйте proto-файлы:
```bash
make proto
```

2. Запустите docker-compose:
```bash
docker-compose up --build
```

Сервисы будут доступны:
- Booking Service (REST API): http://localhost:8000/docs
- Flight Service (gRPC): localhost:50051

## Функциональность

- Базовая архитектура (2 микросервиса, 2 базы PostgreSQL)
- gRPC взаимодействие с генерацией из .proto
- Транзакционная целостность при бронировании (SELECT FOR UPDATE)
- Аутентификация gRPC (API Key)
- Кеширование (Redis) для чтения, инвалидация при записи
- Retry pattern для вызовов gRPC
- Circuit Breaker для отказоустойчивости