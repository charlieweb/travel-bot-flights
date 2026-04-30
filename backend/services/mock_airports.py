"""Mock airport data for development and when API keys are unavailable."""

from schemas.airport import Airport

# Common airports database
MOCK_AIRPORTS = [
    Airport(code="ATL", name="Hartsfield-Jackson Atlanta International Airport", city="Atlanta", country="US"),
    Airport(code="LAX", name="Los Angeles International Airport", city="Los Angeles", country="US"),
    Airport(code="ORD", name="O'Hare International Airport", city="Chicago", country="US"),
    Airport(code="DFW", name="Dallas/Fort Worth International Airport", city="Dallas", country="US"),
    Airport(code="DEN", name="Denver International Airport", city="Denver", country="US"),
    Airport(code="JFK", name="John F. Kennedy International Airport", city="New York", country="US"),
    Airport(code="SFO", name="San Francisco International Airport", city="San Francisco", country="US"),
    Airport(code="SEA", name="Seattle-Tacoma International Airport", city="Seattle", country="US"),
    Airport(code="LAS", name="Harry Reid International Airport", city="Las Vegas", country="US"),
    Airport(code="MCO", name="Orlando International Airport", city="Orlando", country="US"),
    Airport(code="MIA", name="Miami International Airport", city="Miami", country="US"),
    Airport(code="PHX", name="Phoenix Sky Harbor International Airport", city="Phoenix", country="US"),
    Airport(code="BOS", name="Logan International Airport", city="Boston", country="US"),
    Airport(code="IAH", name="George Bush Intercontinental Airport", city="Houston", country="US"),
    Airport(code="EWR", name="Newark Liberty International Airport", city="Newark", country="US"),
    Airport(code="MSP", name="Minneapolis-Saint Paul International Airport", city="Minneapolis", country="US"),
    Airport(code="DTW", name="Detroit Metropolitan Airport", city="Detroit", country="US"),
    Airport(code="PHL", name="Philadelphia International Airport", city="Philadelphia", country="US"),
    Airport(code="CLT", name="Charlotte Douglas International Airport", city="Charlotte", country="US"),
    Airport(code="LGA", name="LaGuardia Airport", city="New York", country="US"),
    Airport(code="SLC", name="Salt Lake City International Airport", city="Salt Lake City", country="US"),
    Airport(code="DCA", name="Ronald Reagan Washington National Airport", city="Washington", country="US"),
    Airport(code="BWI", name="Baltimore/Washington International Airport", city="Baltimore", country="US"),
    Airport(code="MDW", name="Chicago Midway International Airport", city="Chicago", country="US"),
    Airport(code="TPA", name="Tampa International Airport", city="Tampa", country="US"),
    Airport(code="SAN", name="San Diego International Airport", city="San Diego", country="US"),
    Airport(code="PDX", name="Portland International Airport", city="Portland", country="US"),
    Airport(code="HNL", name="Daniel K. Inouye International Airport", city="Honolulu", country="US"),
    Airport(code="AUS", name="Austin-Bergstrom International Airport", city="Austin", country="US"),
    Airport(code="DAL", name="Dallas Love Field", city="Dallas", country="US"),
    Airport(code="BNA", name="Nashville International Airport", city="Nashville", country="US"),
    Airport(code="SMF", name="Sacramento International Airport", city="Sacramento", country="US"),
    Airport(code="MSY", name="Louis Armstrong New Orleans International Airport", city="New Orleans", country="US"),
    Airport(code="SAT", name="San Antonio International Airport", city="San Antonio", country="US"),
    Airport(code="PIT", name="Pittsburgh International Airport", city="Pittsburgh", country="US"),
    Airport(code="CLE", name="Cleveland Hopkins International Airport", city="Cleveland", country="US"),
    Airport(code="STL", name="St. Louis Lambert International Airport", city="St. Louis", country="US"),
    Airport(code="MCI", name="Kansas City International Airport", city="Kansas City", country="US"),
    Airport(code="IND", name="Indianapolis International Airport", city="Indianapolis", country="US"),
    Airport(code="CMH", name="John Glenn Columbus International Airport", city="Columbus", country="US"),
    Airport(code="CVG", name="Cincinnati/Northern Kentucky International Airport", city="Cincinnati", country="US"),
    Airport(code="RDU", name="Raleigh-Durham International Airport", city="Raleigh", country="US"),
    Airport(code="SJC", name="Norman Y. Mineta San Jose International Airport", city="San Jose", country="US"),
    Airport(code="OAK", name="Oakland International Airport", city="Oakland", country="US"),
    Airport(code="FLL", name="Fort Lauderdale-Hollywood International Airport", city="Fort Lauderdale", country="US"),
    Airport(code="SNA", name="John Wayne Airport", city="Santa Ana", country="US"),
    Airport(code="SJU", name="Luis Muñoz Marín International Airport", city="San Juan", country="PR"),
    Airport(code="ANC", name="Ted Stevens Anchorage International Airport", city="Anchorage", country="US"),
    Airport(code="ABQ", name="Albuquerque International Sunport", city="Albuquerque", country="US"),
    Airport(code="TUS", name="Tucson International Airport", city="Tucson", country="US"),
    Airport(code="OGG", name="Kahului Airport", city="Kahului", country="US"),
    Airport(code="KOA", name="Ellison Onizuka Kona International Airport", city="Kailua-Kona", country="US"),
    # International
    Airport(code="LHR", name="Heathrow Airport", city="London", country="GB"),
    Airport(code="CDG", name="Charles de Gaulle Airport", city="Paris", country="FR"),
    Airport(code="AMS", name="Amsterdam Airport Schiphol", city="Amsterdam", country="NL"),
    Airport(code="FRA", name="Frankfurt Airport", city="Frankfurt", country="DE"),
    Airport(code="MAD", name="Adolfo Suárez Madrid–Barajas Airport", city="Madrid", country="ES"),
    Airport(code="FCO", name="Leonardo da Vinci–Fiumicino Airport", city="Rome", country="IT"),
    Airport(code="MUC", name="Munich Airport", city="Munich", country="DE"),
    Airport(code="BCN", name="Barcelona–El Prat Airport", city="Barcelona", country="ES"),
    Airport(code="DUB", name="Dublin Airport", city="Dublin", country="IE"),
    Airport(code="ZRH", name="Zurich Airport", city="Zurich", country="CH"),
    Airport(code="VIE", name="Vienna International Airport", city="Vienna", country="AT"),
    Airport(code="CPH", name="Copenhagen Airport", city="Copenhagen", country="DK"),
    Airport(code="ARN", name="Stockholm Arlanda Airport", city="Stockholm", country="SE"),
    Airport(code="OSL", name="Oslo Airport, Gardermoen", city="Oslo", country="NO"),
    Airport(code="HEL", name="Helsinki Airport", city="Helsinki", country="FI"),
    Airport(code="PRG", name="Václav Havel Airport Prague", city="Prague", country="CZ"),
    Airport(code="WAW", name="Warsaw Chopin Airport", city="Warsaw", country="PL"),
    Airport(code="ATH", name="Athens International Airport", city="Athens", country="GR"),
    Airport(code="IST", name="Istanbul Airport", city="Istanbul", country="TR"),
    Airport(code="DXB", name="Dubai International Airport", city="Dubai", country="AE"),
    Airport(code="DOH", name="Hamad International Airport", city="Doha", country="QA"),
    Airport(code="SIN", name="Singapore Changi Airport", city="Singapore", country="SG"),
    Airport(code="HKG", name="Hong Kong International Airport", city="Hong Kong", country="HK"),
    Airport(code="NRT", name="Narita International Airport", city="Tokyo", country="JP"),
    Airport(code="HND", name="Haneda Airport", city="Tokyo", country="JP"),
    Airport(code="ICN", name="Incheon International Airport", city="Seoul", country="KR"),
    Airport(code="PEK", name="Beijing Capital International Airport", city="Beijing", country="CN"),
    Airport(code="PVG", name="Shanghai Pudong International Airport", city="Shanghai", country="CN"),
    Airport(code="BKK", name="Suvarnabhumi Airport", city="Bangkok", country="TH"),
    Airport(code="KUL", name="Kuala Lumpur International Airport", city="Kuala Lumpur", country="MY"),
    Airport(code="MNL", name="Ninoy Aquino International Airport", city="Manila", country="PH"),
    Airport(code="CGK", name="Soekarno–Hatta International Airport", city="Jakarta", country="ID"),
    Airport(code="SYD", name="Sydney Kingsford Smith Airport", city="Sydney", country="AU"),
    Airport(code="MEL", name="Melbourne Airport", city="Melbourne", country="AU"),
    Airport(code="BNE", name="Brisbane Airport", city="Brisbane", country="AU"),
    Airport(code="PER", name="Perth Airport", city="Perth", country="AU"),
    Airport(code="AKL", name="Auckland Airport", city="Auckland", country="NZ"),
    Airport(code="GRU", name="São Paulo/Guarulhos International Airport", city="São Paulo", country="BR"),
    Airport(code="GIG", name="Rio de Janeiro/Galeão International Airport", city="Rio de Janeiro", country="BR"),
    Airport(code="EZE", name="Ministro Pistarini International Airport", city="Buenos Aires", country="AR"),
    Airport(code="SCL", name="Arturo Merino Benítez International Airport", city="Santiago", country="CL"),
    Airport(code="LIM", name="Jorge Chávez International Airport", city="Lima", country="PE"),
    Airport(code="BOG", name="El Dorado International Airport", city="Bogotá", country="CO"),
    Airport(code="MEX", name="Mexico City International Airport", city="Mexico City", country="MX"),
    Airport(code="CUN", name="Cancún International Airport", city="Cancún", country="MX"),
    Airport(code="PTY", name="Tocumen International Airport", city="Panama City", country="PA"),
    Airport(code="SJO", name="Juan Santamaría International Airport", city="San José", country="CR"),
    Airport(code="GUA", name="La Aurora International Airport", city="Guatemala City", country="GT"),
    Airport(code="SAP", name="Ramón Villeda Morales International Airport", city="San Pedro Sula", country="HN"),
    Airport(code="MGA", name="Augusto C. Sandino International Airport", city="Managua", country="NI"),
    Airport(code="SAL", name="El Salvador International Airport", city="San Salvador", country="SV"),
    Airport(code="LIR", name="Daniel Oduber Quirós International Airport", city="Liberia", country="CR"),
    Airport(code="PTY", name="Tocumen International Airport", city="Panama City", country="PA"),
    Airport(code="UIO", name="Mariscal Sucre International Airport", city="Quito", country="EC"),
    Airport(code="GYE", name="José Joaquín de Olmedo International Airport", city="Guayaquil", country="EC"),
    Airport(code="LIM", name="Jorge Chávez International Airport", city="Lima", country="PE"),
    Airport(code="CWB", name="Afonso Pena International Airport", city="Curitiba", country="BR"),
    Airport(code="BSB", name="Brasília International Airport", city="Brasília", country="BR"),
    Airport(code="MAO", name="Eduardo Gomes International Airport", city="Manaus", country="BR"),
    Airport(code="REC", name="Recife/Guararapes–Gilberto Freyre International Airport", city="Recife", country="BR"),
    Airport(code="SSA", name="Salvador International Airport", city="Salvador", country="BR"),
    Airport(code="FOR", name="Pinto Martins – Fortaleza International Airport", city="Fortaleza", country="BR"),
    Airport(code="NAT", name="São Gonçalo do Amarante–Governador Aluízio Alves International Airport", city="Natal", country="BR"),
    Airport(code="BEL", name="Val de Cans International Airport", city="Belém", country="BR"),
    Airport(code="FLN", name="Hercílio Luz International Airport", city="Florianópolis", country="BR"),
    Airport(code="VIX", name="Eurico de Aguiar Salles Airport", city="Vitória", country="BR"),
    Airport(code="GYN", name="Santa Genoveva Airport", city="Goiânia", country="BR"),
    Airport(code="CGB", name="Marechal Rondon International Airport", city="Cuiabá", country="BR"),
]


def search_mock_airports(query: str, limit: int = 10) -> list[Airport]:
    """Search mock airports by query string."""
    query_lower = query.lower()
    results = []
    
    for airport in MOCK_AIRPORTS:
        if (
            query_lower in airport.code.lower()
            or query_lower in airport.name.lower()
            or query_lower in airport.city.lower()
            or query_lower in airport.country.lower()
        ):
            results.append(airport)
            if len(results) >= limit:
                break
    
    return results


def get_all_mock_airports(limit: int = 50) -> list[Airport]:
    """Return all mock airports up to limit."""
    return MOCK_AIRPORTS[:limit]
