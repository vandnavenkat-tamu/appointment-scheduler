from datetime import datetime
from flask import Flask, request, jsonify
import threading
from collections import defaultdict

app = Flask(__name__)

# Dictionary to store provider details
providers = {}

# Dictionary to store scheduled appointments
appointments = {}

# Mapping of available slots to providers for prioritization
availability_map = defaultdict(list)

# Provider-specific locks to ensure concurrency control
provider_locks = defaultdict(threading.Lock)


class Provider:
    def __init__(self, provider_id, availability, max_daily_appointments):
        self.id = provider_id
        # Convert availability time to minutes and sort slots by start time
        self.availability = sorted(
            [(self._convert_to_minutes(slot['start']), self._convert_to_minutes(slot['end']))
             for slot in availability], key=lambda x: x[0]
        )
        self.max_daily_appointments = max_daily_appointments
        self.scheduled_appointments = []
        self.available_slots = max_daily_appointments

        # Insert provider into availability map based on available slots
        if self.available_slots > 0:
            availability_map[self.available_slots].append(self)

    def _convert_to_minutes(self, time_str):
        """Convert HH:MM time format to minutes since midnight."""
        t = datetime.strptime(time_str, "%H:%M")
        return t.hour * 60 + t.minute

    def _convert_from_minutes(self, minutes):
        """Convert minutes since midnight back to HH:MM format."""
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    def find_least_fragmenting_slot(self, duration, preferred_start, preferred_end):
        """Finds an available slot that minimizes fragmentation."""
        for i, (slot_start, slot_end) in enumerate(self.availability):
            if slot_end <= preferred_start or slot_start >= preferred_end:
                continue
            adjusted_start = max(slot_start, preferred_start)
            adjusted_end = min(slot_end, preferred_end)
            if adjusted_end - adjusted_start < duration:
                continue
            left_fragment = adjusted_start - slot_start
            right_fragment = slot_end - adjusted_end
            proposed_start = adjusted_start if left_fragment <= right_fragment else adjusted_end - duration
            return proposed_start, i
        return None, -1

    def schedule(self, request_id, start_time, duration, slot_index):
        """Schedules an appointment and updates availability slots."""
        if self.available_slots == 0:
            return None

        # Add appointment to scheduled list
        self.scheduled_appointments.append((request_id, start_time, start_time + duration))
        self.available_slots -= 1

        # Update availability slots
        slot_start, slot_end = self.availability[slot_index]
        new_slots = []
        if slot_start < start_time:
            new_slots.append((slot_start, start_time))
        if start_time + duration < slot_end:
            new_slots.append((start_time + duration, slot_end))
        self.availability[slot_index:slot_index + 1] = new_slots

        # Update provider prioritization in availability map
        availability_map[self.available_slots + 1].remove(self)
        if self.available_slots > 0:
            availability_map[self.available_slots].insert(0, self)

        return {
            "request_id": request_id,
            "provider_id": self.id,
            "time_slot": {
                "start": self._convert_from_minutes(start_time),
                "end": self._convert_from_minutes(start_time + duration)
            }
        }

    def update_scheduled_appointments(self, to_cancel):
        """Removes canceled appointments and updates available slots."""
        self.scheduled_appointments = [(req_id, start, end) for req_id, start, end in self.scheduled_appointments if req_id not in to_cancel]
        self.available_slots = self.max_daily_appointments - len(self.scheduled_appointments)


@app.route("/providers", methods=["POST"])
def add_provider():
    """Registers a new provider with their availability and max daily appointments."""
    data = request.json
    provider_id = data['id']
    with provider_locks[provider_id]:
        providers[provider_id] = Provider(provider_id, data['availability'], data['max_daily_appointments'])
    return jsonify({"message": "Provider added successfully."})


@app.route("/appointments", methods=["POST"])
def schedule_appointment():
    """Schedules an appointment for a user, considering provider preferences and availability."""
    data = request.json
    request_id = data['id']
    duration = data['duration']

    # Convert preferred time range to minutes
    preferred_start = datetime.strptime(data['preferred_range']['start'], "%H:%M").hour * 60 + datetime.strptime(data['preferred_range']['start'], "%H:%M").minute
    preferred_end = datetime.strptime(data['preferred_range']['end'], "%H:%M").hour * 60 + datetime.strptime(data['preferred_range']['end'], "%H:%M").minute
    preferred_provider = data.get("preferred_provider")

    # Check if user has a provider preference
    if preferred_provider:
        if preferred_provider not in providers:
            return jsonify({"error": "Preferred provider not available"})

        with provider_locks[preferred_provider]:
            provider = providers[preferred_provider]
            start_time, slot_index = provider.find_least_fragmenting_slot(duration, preferred_start, preferred_end)
            if slot_index != -1:
                appointment = provider.schedule(request_id, start_time, duration, slot_index)
                if appointment:
                    appointments[request_id] = appointment
                    return jsonify(appointment)
            return jsonify({"error": "No available time slot within preferred range for the selected provider."})

    # If no preferred provider, prioritize providers with more available slots
    available_slots_copy = sorted(availability_map.keys(), reverse=True)  # Iterate in descending order
    for available_slots in available_slots_copy:
        providers_copy = list(availability_map[available_slots])  # Make a copy to avoid modification issues
        for provider in providers_copy:
            with provider_locks[provider.id]:
                start_time, slot_index = provider.find_least_fragmenting_slot(duration, preferred_start, preferred_end)
                if slot_index != -1:
                    appointment = provider.schedule(request_id, start_time, duration, slot_index)
                    if appointment:
                        appointments[request_id] = appointment
                        return jsonify(appointment)

    return jsonify({"error": "No available time slot within preferred range."})


@app.route("/providers/<provider_id>/availability", methods=["PUT"])
def update_provider_availability(provider_id):
    """Updates provider availability and cancels conflicting appointments."""
    if provider_id not in providers:
        return jsonify({"error": "Provider not found."})

    data = request.json
    with provider_locks[provider_id]:
        # Convert new availability times to minutes
        providers[provider_id].availability = sorted(
            [(providers[provider_id]._convert_to_minutes(slot['start']), providers[provider_id]._convert_to_minutes(slot['end']))
             for slot in data['availability']], key=lambda x: x[0]
        )

        # Identify appointments that need to be canceled
        to_cancel = [req_id for req_id, start, end in providers[provider_id].scheduled_appointments
                     if not any(slot_start <= start and end <= slot_end for slot_start, slot_end in providers[provider_id].availability)]

        # Update appointments status
        for req_id in to_cancel:
            appointments[req_id]['status'] = "Cancelled"

        providers[provider_id].update_scheduled_appointments(to_cancel)

    return jsonify({"message": "Availability updated, affected appointments cancelled."})


@app.route("/appointments", methods=["GET"])
def get_appointments():
    """Returns a list of all scheduled appointments."""
    return jsonify({"scheduled": list(appointments.values())})


if __name__ == "__main__":
    app.run(debug=True, threaded=True)  # Enable multi-threading to handle parallel requests
