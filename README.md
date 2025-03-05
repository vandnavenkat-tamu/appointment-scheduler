# Appointment Scheduling System  

## Overview  
This is a **Flask-based appointment scheduling system** that efficiently assigns appointment slots to users based on provider availability. The system prioritizes providers with the most available slots to ensure fair distribution while enabling parallel API requests with **multithreading and provider-level locking**.  

## Features & Implementation Details  
- **Provider Availability Management**: Providers can define their availability and daily appointment limits.  
- **Optimized Slot Selection**: Slots are allocated with minimal fragmentation to maximize scheduling efficiency. If multiple slots are available, the one causing the least fragmentation is picked.  
- **Fair Provider Selection**: When no provider preference is given, the system prioritizes providers with more available slots to balance workload. The system assumes equal probability of appointment requests for each provider. If a provider is explicitly requested and has no slots, no appointment is scheduled.  
- **Concurrency Handling**: Multithreading is enabled to handle concurrent requests, and per-provider locks prevent race conditions when modifying provider schedules.  
- **Rescheduling on Availability Change**: Existing appointments are retained where possible, and conflicting ones are canceled.  
- **Efficient Data Structure Usage**: A mapping of available slots to providers allows quick selection based on priority. Heap-based selection was discarded since locking the heap would hinder parallelism, and random provider selection was avoided due to increased computational overhead.

---

## API Endpoints  

### 1. Add a Provider  
**Endpoint:** `POST /providers`  
Registers a provider with availability slots and a daily appointment limit.  

#### Request  
```json
{
  "id": "provider_1",
  "availability": [
    {"start": "09:00", "end": "12:00"},
    {"start": "13:00", "end": "17:00"}
  ],
  "max_daily_appointments": 8
}
```

#### Response  
```json
{"message": "Provider added successfully."}
```

#### cURL Example  
```sh
curl -X POST http://127.0.0.1:5000/providers \
     -H "Content-Type: application/json" \
     -d '{
           "id": "provider_1",
           "availability": [
             {"start": "09:00", "end": "12:00"},
             {"start": "13:00", "end": "17:00"}
           ],
           "max_daily_appointments": 8
         }'
```

---

### 2. Schedule an Appointment  
**Endpoint:** `POST /appointments`  
Schedules an appointment with an available provider based on preferred time and duration.  

#### Request  
```json
{
  "id": "req_1",
  "preferred_range": {"start": "09:30", "end": "11:30"},
  "duration": 30,
  "preferred_provider": "provider_1"
}
```

#### Response  
```json
{
  "request_id": "req_1",
  "provider_id": "provider_1",
  "time_slot": {
    "start": "09:30",
    "end": "10:00"
  }
}
```

#### cURL Example  
```sh
curl -X POST http://127.0.0.1:5000/appointments \
     -H "Content-Type: application/json" \
     -d '{
           "id": "req_1",
           "preferred_range": {"start": "09:30", "end": "11:30"},
           "duration": 30,
           "preferred_provider": "provider_1"
         }'
```

---

### 3. Update Provider Availability  
**Endpoint:** `PUT /providers/<provider_id>/availability`  
Modifies a provider’s available slots and cancels conflicting appointments.  

#### Request  
```json
{
  "availability": [
    {"start": "08:00", "end": "12:00"},
    {"start": "14:00", "end": "18:00"}
  ]
}
```

#### Response  
```json
{"message": "Availability updated, affected appointments cancelled."}
```

#### cURL Example  
```sh
curl -X PUT http://127.0.0.1:5000/providers/provider_1/availability \
     -H "Content-Type: application/json" \
     -d '{
           "availability": [
             {"start": "08:00", "end": "12:00"},
             {"start": "14:00", "end": "18:00"}
           ]
         }'
```

---

### 4. Get Scheduled Appointments  
**Endpoint:** `GET /appointments`  
Fetches a list of all scheduled appointments.  

#### Response  
```json
{
  "scheduled": [
    {
      "request_id": "req_1",
      "provider_id": "provider_1",
      "time_slot": {
        "start": "09:30",
        "end": "10:00"
      }
    }
  ]
}
```

#### cURL Example  
```sh
curl -X GET http://127.0.0.1:5000/appointments
```

---

## Running the Application  

### **Requirements**  
- Python 3.x  
- Flask  

### **Installation & Execution**  
1. Clone the repository:  
   ```sh
   git clone <repo-url>
   cd <repo-folder>
   ```
2. Install dependencies:  
   ```sh
   pip install Flask
   ```
3. Run the server:  
   ```sh
   python app.py
   ```
4. The API will be available at `http://127.0.0.1:5000`.  

