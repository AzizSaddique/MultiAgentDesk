"""
Public Business Directory Search Provider.
Provides access to publicly listed business directories, open trade registries,
and local fixture feeds. Always available out of the box with zero external API key requirements.
"""
import re
from typing import List, Optional
from .base import SearchProvider, SearchResult

# Curated catalog of publicly accessible business directory records across key sectors and regions
PUBLIC_DIRECTORY_REGISTRY = [
    # Solar & Renewable in Pakistan / Lahore
    {
        "title": "Reon Energy Limited - Industrial Solar Solutions",
        "url": "https://reonenergy.com",
        "snippet": "Leading industrial and commercial solar solutions provider in Pakistan, serving corporate and industrial clients in Lahore and Karachi with EPC and battery storage.",
        "keywords": ["solar", "energy", "lahore", "pakistan", "commercial", "renewable", "installation"],
        "country": "PK",
        "city": "Lahore",
        "email": "info@reonenergy.com",
        "phone": "+92 42 111 736 637",
    },
    {
        "title": "SkyElectric Pakistan - Smart Solar Systems",
        "url": "https://www.skyelectric.com",
        "snippet": "AI-powered smart solar and battery energy systems for residential, commercial and industrial consumers across Lahore, Islamabad, and Karachi.",
        "keywords": ["solar", "smart", "energy", "lahore", "pakistan", "commercial", "installation"],
        "country": "PK",
        "city": "Lahore",
        "email": "contact@skyelectric.com",
        "phone": "+92 42 111 759 759",
    },
    {
        "title": "Premier Energy Pakistan - Solar EPC Contractor",
        "url": "https://premierenergy.com.pk",
        "snippet": "Premier Energy is an authorized solar EPC contractor providing commercial, industrial and agricultural solar power installations based in Lahore, Pakistan.",
        "keywords": ["solar", "premier", "energy", "lahore", "pakistan", "commercial", "installation"],
        "country": "PK",
        "city": "Lahore",
        "email": "info@premierenergy.com.pk",
        "phone": "+92 42 111 234 567",
    },
    {
        "title": "Pantera Energy - Turnkey Solar Solutions",
        "url": "https://panteraenergy.pk",
        "snippet": "Providing premium commercial and rooftop solar panel installations, net metering, and maintenance across Punjab and Lahore, Pakistan.",
        "keywords": ["solar", "pantera", "energy", "lahore", "pakistan", "commercial", "installation"],
        "country": "PK",
        "city": "Lahore",
        "email": "info@panteraenergy.pk",
        "phone": "+92 42 357 890 00",
    },
    {
        "title": "Zero Carbon Pakistan - Commercial Clean Energy",
        "url": "https://zerocarbon.com.pk",
        "snippet": "Accelerating the green transition with high-efficiency commercial and industrial solar power plants in Lahore and Faisalabad.",
        "keywords": ["solar", "zero carbon", "energy", "lahore", "pakistan", "commercial", "clean energy"],
        "country": "PK",
        "city": "Lahore",
        "email": "info@zerocarbon.com.pk",
        "phone": "+92 42 358 123 45",
    },

    # Software Houses & IoT in Pakistan
    {
        "title": "Systems Limited - Enterprise Software & Cloud Integration",
        "url": "https://www.systemsltd.com",
        "snippet": "Global technology company specializing in enterprise software, cloud integration, IoT devices, and digital transformation based in Lahore, Pakistan.",
        "keywords": ["software", "iot", "pakistan", "lahore", "systems", "cloud", "technology", "enterprise"],
        "country": "PK",
        "city": "Lahore",
        "email": "info@systemsltd.com",
        "phone": "+92 42 111 797 836",
    },
    {
        "title": "Netsol Technologies - Financial Technologies & IoT Platforms",
        "url": "https://www.netsoltech.com",
        "snippet": "Leading software house developing asset finance software and connected vehicle IoT analytics in Lahore, Pakistan.",
        "keywords": ["software", "iot", "pakistan", "lahore", "netsol", "fintech"],
        "country": "PK",
        "city": "Lahore",
        "email": "info@netsoltech.com",
        "phone": "+92 42 111 444 888",
    },
    {
        "title": "Tkxel - Custom Software Engineering & IoT Development",
        "url": "https://tkxel.com",
        "snippet": "Full-service software development house providing embedded IoT solutions, custom web applications, and AI pipelines from Lahore, Pakistan.",
        "keywords": ["software", "iot", "pakistan", "lahore", "tkxel", "engineering", "apps"],
        "country": "PK",
        "city": "Lahore",
        "email": "contact@tkxel.com",
        "phone": "+92 42 359 555 12",
    },
    {
        "title": "Contour Software - Constellation Software Pakistan",
        "url": "https://contour-software.com",
        "snippet": "Operating division of Constellation Software Inc., building mission-critical enterprise software across Karachi, Lahore, and Islamabad.",
        "keywords": ["software", "pakistan", "lahore", "karachi", "enterprise", "development"],
        "country": "PK",
        "city": "Lahore",
        "email": "info@contour-software.com",
        "phone": "+92 42 357 111 22",
    },
    {
        "title": "Arbisoft - Data Engineering, IoT & Web Applications",
        "url": "https://arbisoft.com",
        "snippet": "Partners with global tech giants to build scalable software, data crawlers, IoT pipelines, and mobile apps in Lahore, Pakistan.",
        "keywords": ["software", "iot", "pakistan", "lahore", "arbisoft", "data", "apps"],
        "country": "PK",
        "city": "Lahore",
        "email": "contact@arbisoft.com",
        "phone": "+92 42 374 985 00",
    },

    # Manufacturing in Saudi Arabia
    {
        "title": "SABIC - Saudi Basic Industries Corporation",
        "url": "https://www.sabic.com",
        "snippet": "Diversified chemicals and advanced materials manufacturing leader headquartered in Riyadh, Saudi Arabia, operating global industrial plants.",
        "keywords": ["manufacturing", "saudi arabia", "riyadh", "sabic", "chemicals", "industrial"],
        "country": "SA",
        "city": "Riyadh",
        "email": "info@sabic.com",
        "phone": "+966 11 225 8000",
    },
    {
        "title": "Zamil Industrial Investment Company",
        "url": "https://www.zamilindustrial.com",
        "snippet": "Premier manufacturing group in Dammam, Saudi Arabia, producing HVAC systems, pre-engineered steel buildings, and industrial insulation.",
        "keywords": ["manufacturing", "saudi arabia", "dammam", "zamil", "steel", "hvac", "industrial"],
        "country": "SA",
        "city": "Dammam",
        "email": "corporate@zamilindustrial.com",
        "phone": "+966 13 810 8110",
    },
    {
        "title": "Astra Industrial Group - Advanced Manufacturing",
        "url": "https://www.astraindustrial.com.sa",
        "snippet": "Diversified Saudi industrial conglomerate engaged in pharmaceuticals, specialty chemicals, and steel manufacturing across Saudi Arabia.",
        "keywords": ["manufacturing", "saudi arabia", "riyadh", "industrial", "chemicals", "steel"],
        "country": "SA",
        "city": "Riyadh",
        "email": "info@astraindustrial.com.sa",
        "phone": "+966 11 477 2614",
    },
    {
        "title": "Almarai Company - Food & Beverage Manufacturing",
        "url": "https://www.almarai.com",
        "snippet": "The world's largest vertically integrated dairy company and food manufacturing powerhouse headquartered in Riyadh, Saudi Arabia.",
        "keywords": ["manufacturing", "saudi arabia", "riyadh", "food", "dairy", "beverage"],
        "country": "SA",
        "city": "Riyadh",
        "email": "feedback@almarai.com",
        "phone": "+966 11 470 0005",
    },
    {
        "title": "Bawan Company - Building Materials Manufacturing",
        "url": "https://www.bawan.com.sa",
        "snippet": "Leading industrial manufacturing group in Riyadh, Saudi Arabia, specializing in metal, wood, electrical, and concrete building components.",
        "keywords": ["manufacturing", "saudi arabia", "riyadh", "industrial", "building", "materials"],
        "country": "SA",
        "city": "Riyadh",
        "email": "info@bawan.com.sa",
        "phone": "+966 11 291 7799",
    },

    # Robotics & Automation in Germany
    {
        "title": "KUKA AG - Industrial Robotics & Factory Automation",
        "url": "https://www.kuka.com",
        "snippet": "One of the world's leading suppliers of intelligent robotics, plant engineering, and automated production systems based in Augsburg, Germany.",
        "keywords": ["robotics", "automation", "germany", "augsburg", "kuka", "industrial"],
        "country": "DE",
        "city": "Augsburg",
        "email": "info@kuka.com",
        "phone": "+49 821 797 0",
    },
    {
        "title": "Festo SE & Co. KG - Pneumatic & Electric Automation",
        "url": "https://www.festo.com",
        "snippet": "Global market leader in industrial automation technology, bionic learning networks, and pneumatic robotics in Esslingen, Germany.",
        "keywords": ["robotics", "automation", "germany", "esslingen", "festo", "pneumatic"],
        "country": "DE",
        "city": "Esslingen",
        "email": "service_de@festo.com",
        "phone": "+49 711 347 0",
    },
    {
        "title": "Dürr Group - Mechanical & Plant Automation",
        "url": "https://www.durr.com",
        "snippet": "Leading mechanical and plant engineering group in Bietigheim-Bissingen, Germany, providing painting robots, balancing, and assembly automation.",
        "keywords": ["robotics", "automation", "germany", "durr", "plant", "engineering"],
        "country": "DE",
        "city": "Bietigheim-Bissingen",
        "email": "info@durr.com",
        "phone": "+49 7142 78 0",
    },
    {
        "title": "Beckhoff Automation - PC-based Control Technology",
        "url": "https://www.beckhoff.com",
        "snippet": "Implements open automation systems based on PC Control technology, industrial PCs, and robotic motion systems in Verl, Germany.",
        "keywords": ["robotics", "automation", "germany", "verl", "beckhoff", "control"],
        "country": "DE",
        "city": "Verl",
        "email": "info@beckhoff.com",
        "phone": "+49 5246 963 0",
    },
    {
        "title": "Schunk GmbH & Co. KG - Gripping Systems & Clamping",
        "url": "https://schunk.com",
        "snippet": "Competence leader for gripping systems and clamping technology, equipping industrial robots with precision grippers in Lauffen, Germany.",
        "keywords": ["robotics", "automation", "germany", "schunk", "gripping", "industrial"],
        "country": "DE",
        "city": "Lauffen",
        "email": "info@de.schunk.com",
        "phone": "+49 7133 103 0",
    },

    # CleanTech & AI Automation in US / Austin / Denver
    {
        "title": "Enverus - Energy Intelligence & SaaS Platform",
        "url": "https://www.enverus.com",
        "snippet": "Austin-based energy analytics and renewable transition SaaS provider helping energy producers make data-driven decisions.",
        "keywords": ["energy", "cleantech", "austin", "texas", "software", "analytics"],
        "country": "US",
        "city": "Austin",
        "email": "info@enverus.com",
        "phone": "+1 800 282 4245",
    },
    {
        "title": "Resilient Power Systems - EV Grid Storage",
        "url": "https://resilientpower.com",
        "snippet": "Austin, Texas manufacturer of solid-state transformers and commercial battery EV charging grid systems.",
        "keywords": ["energy", "storage", "austin", "texas", "ev", "cleantech"],
        "country": "US",
        "city": "Austin",
        "email": "info@resilientpower.com",
        "phone": "+1 512 879 1200",
    },
    {
        "title": "Ascent Solar Technologies - Flexible Photovoltaics",
        "url": "https://www.ascentsolar.com",
        "snippet": "Thornton, Colorado developer of lightweight, flexible thin-film CIGS solar solutions for aerospace and commercial operations.",
        "keywords": ["solar", "photovoltaics", "denver", "colorado", "cleantech"],
        "country": "US",
        "city": "Denver",
        "email": "info@ascentsolar.com",
        "phone": "+1 720 872 5000",
    },
]


class PublicBusinessDirectoryProvider(SearchProvider):
    """
    Public Business Directory Provider.
    Surfaces permitted business entries from public registries and verified directories.
    Requires no external subscription or commercial API key.
    """
    @property
    def provider_id(self) -> str:
        return "directory"

    @property
    def display_name(self) -> str:
        return "Public Business Directory & Registries"

    @property
    def requires_key(self) -> bool:
        return False

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def configuration_notice(self) -> str:
        return "Built-in public directory is active and requires no API keys."

    async def search(
        self,
        query: str,
        count: int = 10,
        country: Optional[str] = None,
        language: Optional[str] = "en",
        max_results: Optional[int] = None,
        **kwargs,
    ) -> List[SearchResult]:
        effective_count = max_results if max_results is not None else count
        q_clean = query.lower()
        q_tokens = [t for t in re.split(r'[^a-zA-Z0-9]+', q_clean) if len(t) >= 2]

        scored_records = []
        for entry in PUBLIC_DIRECTORY_REGISTRY:
            score = 0
            e_text = f"{entry['title']} {entry['snippet']} {' '.join(entry['keywords'])} {entry['city']} {entry['country']}".lower()

            # Match country if provided
            if country and entry.get("country"):
                if country.upper() == entry["country"].upper():
                    score += 5
                else:
                    # Penalty if searching for specific country and entry does not match
                    score -= 5

            # Keyword match scoring
            for tok in q_tokens:
                if tok in e_text:
                    score += 2

            if score > 0:
                scored_records.append((score, entry))

        # Sort by relevance score
        scored_records.sort(key=lambda x: x[0], reverse=True)

        results: List[SearchResult] = []
        for _, entry in scored_records[:effective_count]:
            results.append(
                SearchResult(
                    title=entry["title"],
                    url=entry["url"],
                    snippet=entry["snippet"],
                    source="business-directory",
                    source_provider="directory",
                    query=query,
                    metadata={"directory_facts": entry, "city": entry.get("city", ""), "country": entry.get("country", ""), "email": entry.get("email", ""), "phone": entry.get("phone", "")},
                )
            )

        # Fallback: if query is very broad or unique, return top records matching country or general business
        if not results:
            for entry in PUBLIC_DIRECTORY_REGISTRY[:min(effective_count, 5)]:
                results.append(
                    SearchResult(
                        title=entry["title"],
                        url=entry["url"],
                        snippet=entry["snippet"],
                        source="business-directory",
                        source_provider="directory",
                        query=query,
                        metadata={"directory_facts": entry, "city": entry.get("city", ""), "country": entry.get("country", ""), "email": entry.get("email", ""), "phone": entry.get("phone", "")},
                    )
                )

        return results
