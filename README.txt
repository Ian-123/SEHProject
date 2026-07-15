## License

This project is dual-licensed:

- **Community Edition**: **AGPL-3.0-only**. See `LICENSE-AGPL-3.0.txt`.
  If you run a modified version over a network, you must make the source
  available to users of that service.
- **Commercial Edition**: a proprietary **Commercial License (EULA)** for teams
  who don’t want copyleft obligations or want redistribution/SaaS rights.
  Contact: <idnjugun@asu.edu>.

SPDX: `AGPL-3.0-only OR LicenseRef-Commercial`

### Third-party components
- Streamlit (Apache-2.0), pandas (BSD-3-Clause), geopy (MIT), openpyxl (MIT),
  pydeck (Apache-2.0). See `THIRD_PARTY_LICENSES.txt` for details. :contentReference[oaicite:4]{index=4}

### Geocoding
Community build uses OpenStreetMap **Nominatim**. The public endpoint has an
Acceptable Use Policy (rate limits, user-agent, etc.). For production/commercial
use, self-host Nominatim or switch to a paid geocoder. :contentReference[oaicite:5]{index=5}
