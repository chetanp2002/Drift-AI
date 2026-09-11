from backend import run_travel_agent

result = run_travel_agent("Plan a 5 days Japan trip from India under 2 lakhs")

print("\n--- 1. FLIGHT RESULTS ---")
print(result["flight_results"])

print("\n--- 2. HOTEL RESULTS ---")
print(result["hotel_results"])

print("\n--- 3. WEATHER RESULTS ---")
print(result["weather_results"])

print("\n--- 4. BUDGET RESULTS ---")
print(result["budget_results"])

print("\n--- 5. DRAFT ITINERARY ---")
print(result["itinerary"])
