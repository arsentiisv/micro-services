# Схема БД (ER-диаграмма)

```mermaid
erDiagram
    %% --- FLIGHT SERVICE DB ---
    FLIGHT {
        int id PK
        string flight_number "UNIQUE_COMPOSITE"
        string airline
        string origin "IATA_CODE"
        string destination "IATA_CODE"
        timestamp departure_time "UNIQUE_COMPOSITE"
        timestamp arrival_time
        int total_seats "CHECK > 0"
        int available_seats "CHECK >= 0"
        decimal price "CHECK > 0"
        string status "ENUM"
    }

    SEAT_RESERVATION {
        int id PK
        int flight_id FK
        uuid booking_id "UNIQUE (External)"
        int seat_count
        string status "ACTIVE/RELEASED/EXPIRED"
    }

    %% --- BOOKING SERVICE DB ---
    BOOKING {
        uuid id PK
        int user_id
        int flight_id "External_ID"
        string passenger_name
        string passenger_email
        int seat_count
        decimal total_price
        string status "CONFIRMED/CANCELLED"
    }

    %% Relationships
    FLIGHT ||--o{ SEAT_RESERVATION : "has"
    
    %% Пунктир показывает логическую связь между микросервисами (через код/gRPC)
    SEAT_RESERVATION ||..|| BOOKING : "1-to-1 syncs_with (gRPC)"
    BOOKING }o..|| FLIGHT : "references"
